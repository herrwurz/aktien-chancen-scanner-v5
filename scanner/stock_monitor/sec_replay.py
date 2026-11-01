"""Offline SEC submission replay into a point-in-time research journal.

No network, trading, scheduler, HEBELTRADER or server configuration changes.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from scanner.stock_monitor.journal import Decision, append_run
from scanner.stock_monitor.sec_receipts import receipts_from_submissions


def replay_sec_snapshot(
    *,
    record: dict,
    cik: int,
    symbol: str,
    cutoff: datetime,
    journal_path: Path,
    run_id: str,
    code_version: str,
) -> dict:
    """Journal only events visible at cutoff, never infer executable quotes."""
    receipts = receipts_from_submissions(record, cik=cik, symbol=symbol)
    eligible = []
    future = 0
    for evidence in receipts:
        try:
            evidence.validate(cutoff)
        except ValueError as exc:
            if str(exc) != "Evidence unavailable at cutoff":
                raise
            future += 1
            continue
        eligible.append(evidence)
    decisions = [
        Decision(
            event_id=e.event_id,
            status="event_detected",
            reason="SEC submission receipt; content and market reaction not yet verified",
            quote_kind="unavailable",
        )
        for e in eligible
    ]
    coverage = (
        f"SEC cached snapshot only; symbol={symbol}; "
        f"visible={len(eligible)}; after_cutoff={future}; no executable quotes"
    )
    digest = append_run(
        journal_path,
        run_id=run_id,
        cutoff=cutoff,
        evidence=eligible,
        decisions=decisions,
        code_version=code_version,
        coverage=coverage,
    )
    return {
        "run_id": run_id,
        "record_sha256": digest,
        "event_count": len(eligible),
        "excluded_after_cutoff": future,
        "status": "research_only",
    }
