from datetime import UTC, datetime

import pytest

from scanner.hebeltrader.identity import LocalIdentityProvider

START = datetime(2025, 1, 1, tzinfo=UTC)
END = datetime(2025, 12, 31, tzinfo=UTC)


def spec(**updates):
    return dict(
        wkn="ABC123",
        symbol="OLD",
        venue="XETR",
        timezone="Europe/Berlin",
        currency="EUR",
        adjustment="raw",
        identity_status="verified",
        identity_reference="exchange archive",
        identity_evidence="archived listing",
        identity_reviewed_by="reviewer",
        identity_reviewed_at="2025-01-01T00:00:00Z",
        identity_valid_from="2020-01-01T00:00:00Z",
        identity_valid_until="2026-01-01T00:00:00Z",
        **updates,
    )


def resolve(mapping, instrument=None, start=START):
    return LocalIdentityProvider(mapping).resolve(
        instrument=instrument or {"wkn": "ABC123"}, start=start, end=END, reviewed_as_of=END
    )


def test_missing_isin_and_repeated_record_mapping():
    mapping = {"ABC123": spec()}
    assert resolve(mapping).selected["symbol"] == "OLD"
    assert resolve(mapping).selected == resolve(mapping).selected


def test_union_deduplicates_same_spec_only():
    old = spec()
    result = resolve({"ABC123": old, "DE000": old}, {"wkn": "ABC123", "isin": "DE000"})
    assert len(result.candidates) == 1
    assert result.selected


def test_old_symbol_selected_by_historical_window():
    new = spec()
    new.update(
        symbol="NEW",
        identity_valid_from="2026-01-01T00:00:00Z",
        identity_valid_until="2030-01-01T00:00:00Z",
    )
    assert resolve({"ABC123": [new, spec()]}).selected["symbol"] == "OLD"


def test_delisted_identity_preserved_and_unknown_fields_removed():
    entry = spec()
    entry.update(delisted_at="2025-10-01T00:00:00Z", secret="private", file="bars.csv")
    chosen = resolve({"ABC123": entry}).selected
    assert chosen["delisted_at"] and chosen["file"] == "bars.csv"
    assert "secret" not in chosen


@pytest.mark.parametrize(
    "updates,issue",
    [
        ({"identity_status": "proposal"}, "identity_unverified"),
        ({"identity_reviewed_at": "2026-01-01T00:00:00Z"}, "identity_review_in_future"),
        ({"identity_reviewed_at": "2025-01-01"}, "identity_unverified"),
        ({"identity_valid_until": "2025-01-02T00:00:00Z"}, "identity_outside_window"),
        ({"instrument_wkn": "WRONG"}, "instrument_mismatch"),
        ({"identity_evidence": []}, "identity_unverified"),
    ],
)
def test_invalid_candidate_fails_closed(updates, issue):
    entry = spec()
    entry.update(updates)
    result = resolve({"ABC123": entry})
    assert result.selected is None
    assert issue in result.issues


def test_currency_and_venue_ambiguity():
    other = spec()
    other.update(currency="USD", venue="XNYS")
    result = resolve({"ABC123": [spec(), other]}, {"wkn": "ABC123", "currency": "EUR"})
    assert result.issues == ["identity_ambiguous"]
    assert resolve({"ABC123": other}, {"wkn": "ABC123", "currency": "EUR"}).issues == [
        "currency_mismatch"
    ]


def test_missing_publication_date_and_malformed_entries():
    assert resolve({"ABC123": spec()}, start=None).selected is None
    assert "missing_publication_date" in resolve({"ABC123": spec()}, start=None).issues
    assert resolve({"ABC123": [None, [], 3]}).selected is None
    assert resolve({"ABC123": [None, spec()]}).selected


def snapshot():
    hashes = {key: "b" * 64 for key in ("file", "calendar_file", "corporate_actions_file")}
    return {
        "version": "a" * 64,
        "manifest_file": "snapshots/manifest.json",
        "expected_hashes": dict(hashes),
        "source_sha256": dict(hashes),
    }


def test_snapshot_preserved_copied_and_used_in_candidate_fingerprint():
    entry = spec()
    entry["snapshot"] = snapshot()
    result = resolve({"ABC123": entry})
    assert result.selected["snapshot"] == entry["snapshot"]
    entry["snapshot"]["expected_hashes"]["file"] = "c" * 64
    assert result.selected["snapshot"]["expected_hashes"]["file"] == "b" * 64
    other = spec()
    other["snapshot"] = snapshot()
    other["snapshot"]["version"] = "c" * 64
    assert resolve({"ABC123": [result.selected, other]}).issues == ["identity_ambiguous"]


@pytest.mark.parametrize(
    "bad",
    [
        None,
        [],
        {},
        {**snapshot(), "version": "invalid"},
        {**snapshot(), "manifest_file": "https://example.com/manifest.json"},
        {**snapshot(), "manifest_file": "../manifest.json"},
        {**snapshot(), "manifest_file": "/manifest.json"},
        {**snapshot(), "expected_hashes": {"file": "b" * 64}},
        {
            **snapshot(),
            "source_sha256": {
                key: "c" * 64 for key in ("file", "calendar_file", "corporate_actions_file")
            },
        },
        {**snapshot(), "extra": "untrusted"},
    ],
)
def test_malformed_snapshot_cannot_fall_back_to_plain_csv(bad):
    entry = spec()
    entry["snapshot"] = bad
    result = resolve({"ABC123": entry})
    assert result.selected is None
    assert "identity_invalid_candidate" in result.issues
