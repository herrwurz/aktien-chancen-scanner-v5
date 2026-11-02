"""Deterministic Vienna-local scan scheduling and rotating detail selection."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

VIENNA = ZoneInfo("Europe/Vienna")


def choose_detail_symbols(symbols: list[str], *, cutoff: datetime) -> tuple[list[str], str]:
    """Full scans at 07:00/19:00 Vienna; hourly priority and rotating coverage otherwise."""
    if cutoff.tzinfo is None or cutoff.utcoffset() is None:
        raise ValueError("cutoff must be timezone-aware")
    local = cutoff.astimezone(VIENNA)
    if local.hour in {7, 19}:
        return symbols, "full"
    priority_count = min(20, len(symbols))
    pool = symbols[priority_count:]
    rotation_count = min(60, len(pool))
    if not pool:
        return symbols, "hourly_priority_rotation"
    # Consecutive hourly slots cover the entire pool before repeating.
    slot = int(cutoff.timestamp() // 3600)
    start = (slot * rotation_count) % len(pool)
    rotated = [pool[(start + i) % len(pool)] for i in range(rotation_count)]
    return symbols[:priority_count] + rotated, "hourly_priority_rotation"
