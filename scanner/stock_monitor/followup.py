"""Track candidate follow-up windows without inventing market prices."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

WINDOWS = (1, 4, 24)


@dataclass(frozen=True)
class Observation:
    symbol: str
    event_id: str
    first_seen_at: datetime
    observed_at: datetime
    price: float | None
    source: str
    quote_kind: str

    def validate(self) -> None:
        if not self.symbol or not self.event_id or not self.source:
            raise ValueError("Observation identity and source required")
        for instant in (self.first_seen_at, self.observed_at):
            if instant.tzinfo is None or instant.utcoffset() is None:
                raise ValueError("Aware observation timestamps required")
        if self.observed_at < self.first_seen_at:
            raise ValueError("Observation predates discovery")
        if self.price is not None and self.price <= 0:
            raise ValueError("Observed price must be positive")


def followup_status(first_seen_at: datetime, now: datetime) -> dict:
    """Report due follow-ups; market-hours-aware return computation is separate."""
    if first_seen_at.tzinfo is None or first_seen_at.utcoffset() is None:
        raise ValueError("Aware first-seen timestamp required")
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Aware current timestamp required")
    if now < first_seen_at:
        raise ValueError("Current time precedes discovery")
    return {
        "first_seen_at": first_seen_at.isoformat(),
        "windows": [
            {
                "hours": hours,
                "due_at": (first_seen_at + timedelta(hours=hours)).isoformat(),
                "due": now >= first_seen_at + timedelta(hours=hours),
                "price_return": None,
                "return_status": "unavailable_without_verified_quotes",
            }
            for hours in WINDOWS
        ],
    }
