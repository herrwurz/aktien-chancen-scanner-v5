"""Canonical aggregation of separately quota-bounded market collection batches."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .pilot import write_pilot_report


def aggregate_batch_reports(paths, *, output_prefix, archive_sha256, target_count=100):
    if type(target_count) is not int or target_count < 1:
        raise ValueError("positive target count required")
    reports = []
    for value in sorted({Path(path).resolve() for path in paths}, key=str):
        raw = value.read_bytes()
        checksum = value.with_suffix(".sha256")
        if not checksum.is_file():
            raise ValueError(f"missing batch checksum: {value.name}")
        expected = checksum.read_text().split()[0]
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError(f"batch integrity error: {value.name}")
        reports.append((value, expected, json.loads(raw)))
    rows, conflicts = {}, []
    for _, digest, report in reports:
        if report.get("coverage_kind") != "real_provider_archive":
            raise ValueError("synthetic batch cannot enter real expansion report")
        for row in report.get("instruments", []):
            asset_id = row["asset_id"]
            previous = rows.get(asset_id)
            if previous and previous["ticker"] != row["ticker"]:
                conflicts.append(asset_id)
                continue
            rows[asset_id] = {**row, "batch_report_sha256": digest}
    instruments = [rows[key] for key in sorted(rows)]
    successful = sum(row.get("status") in {"imported", "up_to_date"} for row in instruments)
    complete = sum(
        (row.get("archive_session_count") or row.get("session_count", 0)) >= 250
        for row in instruments
    )
    calendar_verified = sum(
        row.get("calendar_status") == "verified_complete" for row in instruments
    )
    report = {
        "schema_version": "1.0",
        "coverage_kind": "real_provider_archive",
        "target_count": target_count,
        "distinct_instruments": len(instruments),
        "successful_instruments": successful,
        "minimum_250_sessions_met": complete,
        "calendar_verified_complete": calendar_verified,
        "identity_conflicts": sorted(conflicts),
        "status": (
            "accepted"
            if len(instruments) >= target_count
            and successful >= target_count
            and complete >= target_count
            and calendar_verified >= target_count
            and not conflicts
            else "partial"
        ),
        "batch_reports": [
            {"file": path.name, "sha256": digest, "status": batch.get("status")}
            for path, digest, batch in reports
        ],
        "archive_sha256": archive_sha256,
        "instruments": instruments,
        "training_eligible": False,
    }
    return report, write_pilot_report(report, output_prefix)
