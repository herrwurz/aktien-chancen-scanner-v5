"""Append-only, integrity-checked execution journal for cross-asset scans."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path


def _canonical(value: dict) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def read_run_journal(path: Path) -> list[dict]:
    """Verify every record before returning any scan data."""
    if not path.exists():
        return []
    previous = "0" * 64
    runs = []
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            item = json.loads(line)
            if item["previous_sha256"] != previous:
                raise ValueError("Cross-asset journal chain discontinuity")
            digest = sha256((previous + item["payload"]).encode()).hexdigest()
            if item["record_sha256"] != digest:
                raise ValueError("Cross-asset journal checksum mismatch")
            payload = json.loads(item["payload"])
            if not isinstance(payload, dict) or not payload.get("run_id"):
                raise ValueError("Invalid run payload")
            runs.append(payload)
            previous = digest
    if len({run["run_id"] for run in runs}) != len(runs):
        raise ValueError("Duplicate run IDs in journal")
    return runs


def append_cross_asset_run(path: Path, run: dict) -> str:
    """Persist a finished run; never replace or silently deduplicate history.

    Caller must ensure single-writer access (for example a scheduled worker
    with a process lock). This function does not implement cross-process locks.
    """
    if not isinstance(run, dict) or not run.get("run_id"):
        raise ValueError("Missing run identity")
    if not run.get("started_at") or not run.get("completed_at"):
        raise ValueError("Only completed runs can be persisted")
    if set(run.get("results", {})) != {"stock", "crypto"}:
        raise ValueError("Both asset classes must have a recorded outcome")
    existing = read_run_journal(path)
    if any(item["run_id"] == run["run_id"] for item in existing):
        raise ValueError("Duplicate run_id")
    previous = "0" * 64
    if path.exists():
        with path.open(encoding="utf-8") as stream:
            for line in stream:
                previous = json.loads(line)["record_sha256"]
    payload = _canonical(run)
    digest = sha256((previous + payload).encode()).hexdigest()
    record = {
        "previous_sha256": previous,
        "payload": payload,
        "record_sha256": digest,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(_canonical(record) + "\n")
    return digest
