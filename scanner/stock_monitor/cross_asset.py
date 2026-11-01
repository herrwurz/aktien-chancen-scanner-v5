"""One auditable execution envelope, two independent market scanners.

This orchestration layer does not fetch data, execute orders or emit buy alerts.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any


def run_cross_asset(
    *,
    run_id: str,
    stock_scan: Callable[[], dict[str, Any]],
    crypto_scan: Callable[[], dict[str, Any]],
    now: Callable[[], datetime] | None = None,
) -> dict[str, Any]:
    """Attempt both scanners even when one fails; never infer no signal on error."""
    if not run_id.strip():
        raise ValueError("Nonempty run_id required")
    clock = now or (lambda: datetime.now(UTC))
    started_at = clock()
    if started_at.tzinfo is None or started_at.utcoffset() is None:
        raise ValueError("Timezone-aware clock required")
    results: dict[str, dict[str, Any]] = {}
    for asset, scan in (("stock", stock_scan), ("crypto", crypto_scan)):
        try:
            result = scan()
            if not isinstance(result, dict):
                raise TypeError("Scanner must return a dictionary")
            if result.get("status") not in {"complete", "partial", "unavailable"}:
                raise ValueError("Scanner must declare coverage status")
            results[asset] = result
        except Exception as exc:
            # An unexpected failure must be observable and must not suppress
            # the other asset class. Never leak credentials via exception text.
            results[asset] = {
                "status": "unavailable",
                "error_type": type(exc).__name__,
                "reason": "scanner_execution_failed",
            }
    finished_at = clock()
    if finished_at.tzinfo is None or finished_at.utcoffset() is None:
        raise ValueError("Timezone-aware clock required")
    if finished_at < started_at:
        raise ValueError("Clock moved backwards")
    return {
        "run_id": run_id,
        "started_at": started_at.astimezone(UTC).isoformat(),
        "completed_at": finished_at.astimezone(UTC).isoformat(),
        "status": (
            "complete"
            if all(item["status"] == "complete" for item in results.values())
            else "partial"
        ),
        "results": results,
        "order_execution": False,
    }
