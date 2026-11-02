"""Offline SEC submission replay into a point-in-time research journal.

No network, trading, scheduler, HEBELTRADER or server configuration changes.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from scanner.stock_monitor.journal import Decision, append_run, as_utc
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
    lookback_hours: int | None = None,
) -> dict:
    """Journal events visible at cutoff; optional lookback bounds live polls.

    Historical replay omits ``lookback_hours`` and journals every receipt that
    passes chronology. Live monitors must pass a lookback (e.g. 72) so a stale
    SEC cache cannot re-append the entire submissions history each hour.
    """
    if lookback_hours is not None and not 1 <= lookback_hours <= 168:
        raise ValueError("lookback_hours must be 1..168")
    receipts = receipts_from_submissions(record, cik=cik, symbol=symbol)
    eligible = []
    future = 0
    outside_lookback = 0
    window_start = (
        as_utc(cutoff) - timedelta(hours=lookback_hours) if lookback_hours is not None else None
    )
    for evidence in receipts:
        try:
            evidence.validate(cutoff)
        except ValueError as exc:
            if str(exc) != "Evidence unavailable at cutoff":
                raise
            future += 1
            continue
        if window_start is not None and as_utc(evidence.published_at) < window_start:
            outside_lookback += 1
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
        f"visible={len(eligible)}; after_cutoff={future}; "
        f"outside_lookback={outside_lookback}; no executable quotes"
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
        "excluded_outside_lookback": outside_lookback,
        "lookback_hours": lookback_hours,
        "status": "research_only",
    }
