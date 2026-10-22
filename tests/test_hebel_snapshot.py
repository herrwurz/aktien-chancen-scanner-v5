import json
from datetime import datetime

import pytest
from test_hebel_backtest_provider import history as source_history

from scanner.hebeltrader.market_snapshot import SnapshotStockProvider, main, snapshot_dataset


@pytest.fixture
def history(tmp_path):
    return source_history.__wrapped__(tmp_path)


def test_immutable_idempotent_and_metadata_versions(history):
    root, spec, _ = history
    frozen = snapshot_dataset(root, root / "cache", spec)
    assert snapshot_dataset(root, root / "cache", spec) == frozen
    original = (root / frozen["file"]).read_bytes()
    (root / spec["file"]).write_text("changed")
    assert (root / frozen["file"]).read_bytes() == original
    assert (
        snapshot_dataset(root, root / "cache", spec)["snapshot"]["version"]
        != frozen["snapshot"]["version"]
    )
    spec["license"] = "new license"
    assert (
        snapshot_dataset(root, root / "cache", spec)["snapshot"]["version"]
        != frozen["snapshot"]["version"]
    )


def test_existing_tampering_fails_closed(history):
    root, spec, _ = history
    frozen = snapshot_dataset(root, root / "cache", spec)
    (root / frozen["file"]).write_text("tampered")
    with pytest.raises(ValueError):
        snapshot_dataset(root, root / "cache", spec)
    assert not list((root / "cache").glob(".snapshot-*"))


def test_metadata_whitelist_and_secrets(history):
    root, spec, _ = history
    spec["archive_label"] = "private annotation"
    frozen = snapshot_dataset(root, root / "cache", spec)
    assert "private annotation" not in json.dumps(frozen)
    assert "private annotation" not in (root / frozen["snapshot"]["manifest_file"]).read_text()
    for key, value in [
        ("api_key", "sensitive-value"),
        ("source_reference", "https://vendor.test/data?token=sensitive-value"),
    ]:
        bad = dict(spec, **{key: value})
        with pytest.raises(ValueError) as error:
            snapshot_dataset(root, root / "cache", bad)
        assert "sensitive-value" not in str(error.value)


@pytest.mark.parametrize(
    "key", ["license", "retrieved_at", "timezone", "coverage_end", "identity_reference"]
)
def test_missing_or_invalid_metadata(history, key):
    root, spec, _ = history
    spec[key] = "bad" if key in ("retrieved_at", "timezone", "coverage_end") else ""
    with pytest.raises(ValueError):
        snapshot_dataset(root, root / "cache", spec)


def test_symlink_escape_and_traversal(history, tmp_path_factory):
    root, spec, _ = history
    outside = tmp_path_factory.mktemp("outside")
    (outside / "bars.csv").write_text("outside")
    (root / "escape").symlink_to(outside, target_is_directory=True)
    for path in ("escape/bars.csv", "../bars.csv"):
        with pytest.raises(ValueError):
            snapshot_dataset(root, root / "cache", dict(spec, file=path))
    with pytest.raises(ValueError):
        snapshot_dataset(root, root / "escape", spec)


def test_provider_checks_frozen_hashes_and_metadata(history):
    root, spec, _ = history
    frozen = snapshot_dataset(root, root / "cache", spec)
    provider = SnapshotStockProvider(root)
    kwargs = dict(
        instrument={"wkn": "ABC123", "currency": "EUR"},
        available_at=datetime.fromisoformat("2026-01-02T00:00:00+00:00"),
        as_of=datetime.fromisoformat("2026-01-05T20:00:00+00:00"),
    )
    assert provider.load(frozen, **kwargs).issues == []
    assert provider.load(spec, **kwargs).issues == []
    assert provider.load(dict(frozen, license="changed"), **kwargs).issues == [
        "snapshot_hash_mismatch"
    ]
    (root / frozen["file"]).write_text("tampered")
    assert provider.load(frozen, **kwargs).issues == ["snapshot_hash_mismatch"]


def test_cli_private_no_clobber(history):
    root, spec, _ = history
    (root / "spec.json").write_text(json.dumps(spec))
    args = [
        "--input-dir",
        str(root),
        "--spec",
        "spec.json",
        "--snapshot-dir",
        "cache",
        "--output",
        "frozen.json",
    ]
    assert main(args) == 0
    output = root / "frozen.json"
    assert output.stat().st_mode & 0o777 == 0o600
    original = output.read_bytes()
    with pytest.raises(SystemExit):
        main(args)
    assert output.read_bytes() == original


def test_identity_proof_is_frozen_and_preserved_on_load(history):
    root, spec, _ = history
    proof = dict(
        identity_status="verified",
        identity_evidence="reviewed master record",
        identity_reviewed_by="reviewer",
        identity_reviewed_at="2026-01-06T00:00:00+00:00",
    )
    spec.update(proof)
    frozen = snapshot_dataset(root, root / "cache", spec)
    assert {key: frozen[key] for key in proof} == proof
    manifest = json.loads((root / frozen["snapshot"]["manifest_file"]).read_text())
    assert {key: manifest["metadata"][key] for key in proof} == proof
    kwargs = dict(
        instrument={"wkn": "ABC123", "currency": "EUR"},
        available_at=datetime.fromisoformat("2026-01-02T00:00:00+00:00"),
        as_of=datetime.fromisoformat("2026-01-05T20:00:00+00:00"),
    )
    provider = SnapshotStockProvider(root)
    loaded = provider.load(frozen, **kwargs)
    assert loaded.issues == []
    assert {key: loaded.source[key] for key in proof} == proof
    assert provider.load(dict(frozen, identity_reviewed_by="another"), **kwargs).issues == [
        "snapshot_hash_mismatch"
    ]
    proposal = dict(spec)
    for key in proof:
        proposal.pop(key)
    unreviewed = snapshot_dataset(root, root / "cache", proposal)
    assert provider.load(dict(unreviewed, **proof), **kwargs).issues == ["snapshot_hash_mismatch"]


@pytest.mark.parametrize("value", [None, 1, "", "2026-01-06", "bad"])
def test_invalid_optional_review_timestamp(history, value):
    root, spec, _ = history
    with pytest.raises(ValueError):
        snapshot_dataset(root, root / "cache", dict(spec, identity_reviewed_at=value))


def test_provider_detects_change_between_verification_and_csv_read(history, monkeypatch):
    root, spec, _ = history
    frozen = snapshot_dataset(root, root / "cache", spec)
    provider = SnapshotStockProvider(root)
    csv_load = provider.csv.load

    def mutate_then_load(*args, **kwargs):
        path = root / frozen["file"]
        path.write_text(path.read_text().replace(",10,12,9,11,100", ",10,12,9,12,100"))
        return csv_load(*args, **kwargs)

    monkeypatch.setattr(provider.csv, "load", mutate_then_load)
    result = provider.load(
        frozen,
        instrument={"wkn": "ABC123", "currency": "EUR"},
        available_at=datetime.fromisoformat("2026-01-02T00:00:00+00:00"),
        as_of=datetime.fromisoformat("2026-01-05T20:00:00+00:00"),
    )
    assert result.bars == []
    assert "snapshot_hash_mismatch" in result.issues


@pytest.mark.parametrize(
    "manifest",
    [
        [],
        None,
        42,
        "invalid",
        {"format_version": 1, "files": [], "metadata": {}, "sha256": {}},
        {"format_version": 1, "files": {}, "metadata": None, "sha256": {}},
        {"format_version": 1, "files": {}, "metadata": {}, "sha256": []},
    ],
)
def test_malformed_canonical_manifest_fails_closed(history, manifest):
    import hashlib

    root, spec, _ = history
    raw = (
        json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
    ).encode()
    version = hashlib.sha256(raw).hexdigest()
    directory = root / "cache" / version
    directory.mkdir(parents=True)
    (directory / "manifest.json").write_bytes(raw)
    bad = dict(
        spec,
        snapshot=dict(
            version=version,
            manifest_file=str((directory / "manifest.json").relative_to(root)),
            expected_hashes={},
            source_sha256={},
        ),
    )
    result = SnapshotStockProvider(root).load(
        bad,
        instrument={"wkn": "ABC123", "currency": "EUR"},
        available_at=datetime.fromisoformat("2026-01-02T00:00:00+00:00"),
        as_of=datetime.fromisoformat("2026-01-05T20:00:00+00:00"),
    )
    assert result.bars == []
    assert result.issues == ["snapshot_hash_mismatch"]
