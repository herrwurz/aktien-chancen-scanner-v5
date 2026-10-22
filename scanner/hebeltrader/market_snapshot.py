"""Immutable, local-only market data snapshots and verified offline reads."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .backtest_provider import CsvStockProvider, MarketHistory, _at

FILES = ("file", "calendar_file", "corporate_actions_file")
REQUIRED = (
    *FILES,
    "symbol",
    "venue",
    "timezone",
    "currency",
    "adjustment",
    "source_reference",
    "license",
    "retrieved_at",
    "calendar_reference",
    "corporate_actions_reference",
    "coverage_start",
    "coverage_end",
    "identity_reference",
    "identity_valid_from",
    "identity_valid_until",
)
PROOF = ("identity_status", "identity_evidence", "identity_reviewed_by", "identity_reviewed_at")
ALLOWED = (*REQUIRED, "wkn", "isin", "instrument_wkn", "instrument_isin", "delisted_at", *PROOF)
_SECRET = re.compile(
    r"(?:password|passwd|secret|token|credential|authorization|api[_-]?key|access[_-]?key)", re.I
)


def _json(value):
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
    ).encode()


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _path(root, value):
    if not isinstance(value, (str, Path)):
        raise ValueError("invalid local path")
    candidate = Path(value)
    if ".." in candidate.parts:
        raise ValueError("invalid local path")
    resolved = (root / candidate).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError("local path escapes root")
    return resolved


def _credentials(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if _SECRET.search(str(key)):
                raise ValueError("credential metadata is forbidden")
            _credentials(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _credentials(child)
    elif isinstance(value, str):
        for match in re.finditer(r"https?://[^\s]+", value, re.I):
            parsed = urlsplit(match.group())
            # URL userinfo, queries and fragments can all carry credentials.
            if parsed.username or parsed.password or parsed.query or parsed.fragment:
                raise ValueError("credential-bearing URL metadata is forbidden")


def _metadata(spec):
    if not isinstance(spec, dict):
        raise ValueError("missing metadata")
    _credentials(spec)
    clean = {key: spec[key] for key in ALLOWED if key in spec}
    if any(not isinstance(clean.get(key), str) or not clean[key].strip() for key in REQUIRED):
        raise ValueError("missing metadata")
    if not any(clean.get(k) for k in ("wkn", "isin", "instrument_wkn", "instrument_isin")):
        raise ValueError("missing identity metadata")
    if any(not isinstance(v, str) for v in clean.values()):
        raise ValueError("invalid metadata")
    if any(key in clean and not clean[key].strip() for key in PROOF):
        raise ValueError("invalid identity proof metadata")
    try:
        ZoneInfo(clean["timezone"])
        dates = {
            k: _at(clean[k])
            for k in (
                "retrieved_at",
                "coverage_start",
                "coverage_end",
                "identity_valid_from",
                "identity_valid_until",
            )
        }
        if (
            dates["coverage_start"] > dates["coverage_end"]
            or dates["identity_valid_from"] > dates["identity_valid_until"]
        ):
            raise ValueError()
        if "delisted_at" in clean:
            _at(clean["delisted_at"])
        if "identity_reviewed_at" in clean:
            _at(clean["identity_reviewed_at"])
        for key in ("wkn", "isin"):
            if (
                clean.get(key)
                and clean.get("instrument_" + key)
                and clean[key] != clean["instrument_" + key]
            ):
                raise ValueError()
    except (ValueError, TypeError, ZoneInfoNotFoundError):
        raise ValueError("invalid metadata") from None
    return clean


def _verify(root, spec):
    snapshot = spec["snapshot"]
    if not isinstance(snapshot, dict):
        raise ValueError("invalid snapshot")
    version = snapshot["version"]
    if not isinstance(version, str) or not re.fullmatch(r"[0-9a-f]{64}", version):
        raise ValueError("invalid snapshot")
    manifest_path = _path(root, snapshot["manifest_file"])
    raw_manifest = manifest_path.read_bytes()
    manifest = json.loads(raw_manifest)
    if _json(manifest) != raw_manifest or _sha(raw_manifest) != version:
        raise ValueError("snapshot hash mismatch")
    if (
        not isinstance(manifest, dict)
        or set(manifest) != {"format_version", "files", "metadata", "sha256"}
        or any(not isinstance(manifest[key], dict) for key in ("files", "metadata", "sha256"))
    ):
        raise ValueError("invalid snapshot manifest")
    if any(
        not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value)
        for value in manifest["sha256"].values()
    ):
        raise ValueError("invalid snapshot hashes")
    _metadata({**manifest["metadata"], **manifest["files"]})
    if (
        type(manifest["format_version"]) is not int
        or manifest["format_version"] != 1
        or manifest["files"]
        != dict(zip(FILES, ("bars.csv", "calendar.csv", "corporate_actions.csv"), strict=True))
    ):
        raise ValueError("invalid snapshot manifest")
    if {p.name for p in manifest_path.parent.iterdir()} != {
        "manifest.json",
        *manifest["files"].values(),
    }:
        raise ValueError("unexpected snapshot contents")
    if manifest_path.parent.name != version:
        raise ValueError("snapshot hash mismatch")
    if (
        snapshot["expected_hashes"] != manifest["sha256"]
        or snapshot["source_sha256"] != manifest["sha256"]
    ):
        raise ValueError("snapshot hash mismatch")
    if set(manifest["sha256"]) != set(FILES):
        raise ValueError("snapshot hash mismatch")
    for key in FILES:
        path = _path(root, spec[key])
        if (
            path != manifest_path.parent / manifest["files"][key]
            or _sha(path.read_bytes()) != manifest["sha256"][key]
        ):
            raise ValueError("snapshot hash mismatch")
    if {key: spec[key] for key in ALLOWED if key in spec and key not in FILES} != manifest[
        "metadata"
    ]:
        raise ValueError("snapshot metadata mismatch")


def snapshot_dataset(root: Path, output_root: Path, spec: dict) -> dict:
    """Freeze one CSV provider spec beneath root; return a relative, verified spec."""
    root = Path(root).resolve()
    clean = _metadata(spec)
    output_root = _path(root, output_root)
    raw = {key: _path(root, clean[key]).read_bytes() for key in FILES}
    hashes = {key: _sha(value) for key, value in raw.items()}
    names = dict(zip(FILES, ("bars.csv", "calendar.csv", "corporate_actions.csv"), strict=True))
    metadata = {key: value for key, value in clean.items() if key not in FILES}
    manifest = {"format_version": 1, "metadata": metadata, "files": names, "sha256": hashes}
    manifest_raw = _json(manifest)
    version = _sha(manifest_raw)
    directory = output_root / version
    result = dict(metadata)
    result.update({key: str((directory / names[key]).relative_to(root)) for key in FILES})
    result["snapshot"] = {
        "version": version,
        "manifest_file": str((directory / "manifest.json").relative_to(root)),
        "expected_hashes": hashes,
        "source_sha256": hashes,
    }
    output_root.mkdir(parents=True, exist_ok=True)
    if directory.exists() or directory.is_symlink():
        _verify(root, result)
        return result
    temporary = Path(tempfile.mkdtemp(prefix=".snapshot-", dir=output_root))
    try:
        for key, content in raw.items():
            (temporary / names[key]).write_bytes(content)
        (temporary / "manifest.json").write_bytes(manifest_raw)
        # Serialize publishers without creating a persistent lock artifact.
        fd = os.open(output_root, os.O_RDONLY | os.O_DIRECTORY)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            if directory.exists() or directory.is_symlink():
                _verify(root, result)
            else:
                temporary.rename(directory)
                _verify(root, result)
        finally:
            os.close(fd)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return result


class SnapshotStockProvider:
    """Check frozen bytes and metadata before delegating CSV interpretation."""

    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.csv = CsvStockProvider(self.root)

    def load(self, spec: dict, *, instrument: dict, available_at, as_of) -> MarketHistory:
        if isinstance(spec, dict) and "snapshot" in spec:
            try:
                _verify(self.root, spec)
            except (OSError, ValueError, TypeError, KeyError):
                return MarketHistory([], {}, ["snapshot_hash_mismatch"])
        result = self.csv.load(spec, instrument=instrument, available_at=available_at, as_of=as_of)
        if isinstance(spec, dict) and "snapshot" in spec:
            if result.source.get("sha256") != spec["snapshot"]["expected_hashes"]:
                result.bars.clear()
                if "snapshot_hash_mismatch" not in result.issues:
                    result.issues.append("snapshot_hash_mismatch")
            result.source.update({key: spec[key] for key in PROOF if key in spec})
            result.source["snapshot"] = spec["snapshot"]
        return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", required=True, type=Path)
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--snapshot-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    root = args.input_dir.resolve()
    try:
        spec_path = _path(root, args.spec)
        output = _path(root, args.output)
        if output.exists() or output.is_symlink():
            raise ValueError("output already exists")
        spec = json.loads(spec_path.read_text())
        result = snapshot_dataset(root, args.snapshot_dir, spec)
        raw = _json(result)
        fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(raw)
        except BaseException:
            output.unlink(missing_ok=True)
            raise
    except (OSError, ValueError, TypeError, KeyError):
        parser.error("snapshot failed: invalid input, unsafe metadata, or existing output")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
