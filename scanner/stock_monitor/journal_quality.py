"""Build candidate-level audit from verified stock journal records."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from scanner.stock_monitor.export import export_runs
from scanner.stock_monitor.quality import CandidateAudit, quality_summary


def audit_stock_journal(path: Path, *, limit: int = 100) -> dict:
    """Count actual decisions; SEC event detection is not a trade alert."""
    exported = export_runs(path, limit=limit)
    if exported["status"] == "unavailable":
        return {
            "status": "unavailable",
            "reason": exported["reason"],
            "quality": quality_summary([]),
        }
    events = {}
    for run in exported["runs"]:
        evidence = {item["event_id"]: item for item in run["evidence"]}
        for decision in run["decisions"]:
            event_id = decision["event_id"]
            if event_id not in evidence:
                raise ValueError("Decision without journal evidence")
            receipt = evidence[event_id]
            status = decision["status"]
            if status == "rejected":
                outcome = "rejected"
            elif status == "paper_entry_eligible":
                outcome = "alerted"
            else:
                outcome = "pending"
            first_seen = datetime.fromisoformat(receipt["first_seen_at"])
            if event_id in events:
                prior = events[event_id]
                if prior.symbol != receipt["symbol"]:
                    raise ValueError("Conflicting event symbol")
                if first_seen < prior.detected_at:
                    raise ValueError("Event discovery time moved backward")
            events[event_id] = CandidateAudit(
                asset_class="stock",
                event_id=event_id,
                symbol=receipt["symbol"],
                detected_at=first_seen,
                outcome=outcome,
                reason=decision["reason"],
            )
    quality = quality_summary(list(events.values()))
    return {
        "status": "research_only",
        "quality": quality,
        "journal_runs_considered": len(exported["runs"]),
        "distinct_decided_events": len(events),
        "chain_head": exported["chain_head"],
        "coverage_status": "unknown_without_source_run_accounting",
    }
