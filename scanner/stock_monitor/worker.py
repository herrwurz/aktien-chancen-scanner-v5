"""Bounded SEC monitoring pass; fetching is injected and explicitly controlled."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

from scanner.stock_monitor.sec_replay import replay_sec_snapshot


@dataclass(frozen=True)
class SecTarget:
    cik: int
    symbol: str


def run_sec_monitor(
    *,
    fetch_submissions: Callable[[int], dict],
    targets: list[SecTarget],
    journal_path: Path,
    run_id: str,
    code_version: str,
    cutoff: datetime | None = None,
    max_targets: int = 10,
) -> dict:
    """One bounded research-only pass; caller controls rate limits and cache."""
    if not 1 <= max_targets <= 100 or len(targets) > max_targets:
        raise ValueError("SEC target budget exceeded")
    if len({target.cik for target in targets}) != len(targets):
        raise ValueError("Duplicate SEC CIK")
    if any(target.cik <= 0 or not target.symbol.strip() for target in targets):
        raise ValueError("Invalid SEC target")
    observed_at = cutoff or datetime.now(UTC)
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise ValueError("Aware cutoff required")
    outcomes = []
    for target in targets:
        try:
            record = fetch_submissions(target.cik)
            if record.get("status") == "dry_run":
                outcomes.append({"symbol": target.symbol, "status": "dry_run"})
                continue
            result = replay_sec_snapshot(
                record=record,
                cik=target.cik,
                symbol=target.symbol,
                cutoff=observed_at,
                journal_path=journal_path,
                run_id=f"{run_id}:sec:{target.cik}",
                code_version=code_version,
            )
            outcomes.append({"symbol": target.symbol, **result})
        except (ValueError, KeyError, TypeError, OSError) as exc:
            outcomes.append({
                "symbol": target.symbol,
                "status": "unavailable",
                "error_type": type(exc).__name__,
            })
    return {
        "run_id": run_id,
        "cutoff": observed_at.isoformat(),
        "status": (
            "complete"
            if len(outcomes) == len(targets)
            and all(item["status"] == "research_only" for item in outcomes)
            else "partial"
        ),
        "outcomes": outcomes,
        "requested_targets": len(targets),
        "successful_targets": sum(item["status"] == "research_only" for item in outcomes),
    }
