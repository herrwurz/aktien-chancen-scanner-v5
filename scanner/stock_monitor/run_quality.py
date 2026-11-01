"""Convert real SEC monitor outcomes to candidate audit entries."""

from __future__ import annotations

from datetime import datetime

from scanner.stock_monitor.quality import CandidateAudit, quality_summary


def audit_monitor_outcomes(run: dict) -> dict:
    """Only actual detected events count as alerts; unavailable is not missed."""
    cutoff = datetime.fromisoformat(run["cutoff"])
    if cutoff.tzinfo is None or cutoff.utcoffset() is None:
        raise ValueError("Monitor cutoff must be timezone-aware")
    candidates = []
    unavailable = 0
    for outcome in run["outcomes"]:
        if outcome["status"] != "research_only":
            unavailable += 1
            continue
        count = outcome["event_count"]
        if not isinstance(count, int) or count < 0:
            raise ValueError("Invalid event count")
        # Event-level identifiers are not exposed by the monitor summary.
        # Do not invent event IDs or label filings as investor alerts.
        # This metric measures source receipt volume, not signal success.
    quality = quality_summary(candidates)
    quality["source_runs_unavailable"] = unavailable
    quality["filing_receipts"] = sum(
        outcome["event_count"]
        for outcome in run["outcomes"]
        if outcome["status"] == "research_only"
    )
    quality["alert_count_status"] = "not_available_from_aggregate_receipts"
    return quality
