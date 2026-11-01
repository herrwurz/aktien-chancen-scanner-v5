"""Safe, offline, read-only export of stock-monitor journal summaries.

This module exposes no web endpoint, secrets, orders, or HEBELTRADER data.
"""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path


def export_runs(journal_path: Path, *, limit: int = 20) -> dict:
    if not 1 <= limit <= 100:
        raise ValueError("limit must be 1..100")
    if not journal_path.is_file():
        return {
            "schema_version": "stock-monitor-export-v1",
            "status": "unavailable",
            "reason": "journal_missing",
            "runs": [],
        }
    previous = "0" * 64
    records = []
    with journal_path.open(encoding="utf-8") as stream:
        for line in stream:
            record = json.loads(line)
            if record["previous_sha256"] != previous:
                raise ValueError("Journal chain discontinuity")
            digest = sha256((previous + record["payload"]).encode()).hexdigest()
            if digest != record["record_sha256"]:
                raise ValueError("Journal checksum mismatch")
            previous = digest
            data = json.loads(record["payload"])
            records.append(
                {
                    "run_id": data["run_id"],
                    "cutoff": data["cutoff"],
                    "code_version": data["code_version"],
                    "coverage": data["coverage"],
                    "evidence": [
                        {
                            "event_id": e["event_id"],
                            "symbol": e["symbol"],
                            "source_url": e["source_url"],
                            "source_type": e["source_type"],
                            "published_at": e["published_at"],
                            "first_seen_at": e["first_seen_at"],
                            "retrieved_at": e["retrieved_at"],
                            "content_sha256": e["content_sha256"],
                        }
                        for e in data["evidence"]
                    ],
                    "decisions": data["decisions"],
                    "record_sha256": digest,
                }
            )
    return {
        "schema_version": "stock-monitor-export-v1",
        "status": "partial",
        "reason": "research_journal_only_no_executable_quotes_or_market_coverage_guarantee",
        "runs": records[-limit:],
        "total_runs": len(records),
        "chain_head": previous,
    }
