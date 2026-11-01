"""Auditable candidate-quality metrics shared across asset classes.

No market data fetching, orders, or performance assumptions.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

Outcome = Literal["alerted", "rejected", "missed", "pending"]


@dataclass(frozen=True)
class CandidateAudit:
    asset_class: Literal["stock", "crypto"]
    event_id: str
    symbol: str
    detected_at: datetime | None
    outcome: Outcome
    reason: str

    def validate(self) -> None:
        if self.asset_class not in {"stock", "crypto"}:
            raise ValueError("Unsupported asset class")
        if self.outcome not in {"alerted", "rejected", "missed", "pending"}:
            raise ValueError("Unsupported outcome")
        if not self.event_id.strip() or not self.symbol.strip() or not self.reason.strip():
            raise ValueError("Candidate audit requires identity and reason")
        if self.detected_at is not None and (
            self.detected_at.tzinfo is None or self.detected_at.utcoffset() is None
        ):
            raise ValueError("Detection timestamp must be timezone-aware")
        if self.outcome == "alerted" and self.detected_at is None:
            raise ValueError("Alert requires detection timestamp")


def quality_summary(candidates: list[CandidateAudit]) -> dict:
    """Count observed classifications; do not infer recall without a reference set."""
    for candidate in candidates:
        candidate.validate()
    ids = [(item.asset_class, item.event_id) for item in candidates]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate candidate event")
    totals = Counter(item.outcome for item in candidates)
    by_asset = {
        asset: {
            outcome: sum(
                item.asset_class == asset and item.outcome == outcome for item in candidates
            )
            for outcome in ("alerted", "rejected", "missed", "pending")
        }
        for asset in ("stock", "crypto")
    }
    return {
        "total": len(candidates),
        "outcomes": {
            outcome: totals[outcome] for outcome in ("alerted", "rejected", "missed", "pending")
        },
        "by_asset": by_asset,
        "recall": None,
        "recall_status": "requires_independent_reference_set",
    }
