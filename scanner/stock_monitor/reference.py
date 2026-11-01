"""Independent, timestamped opportunity reference sets for scanner recall audits."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ReferenceOpportunity:
    asset_class: str
    event_id: str
    symbol: str
    eligible_at: datetime
    source: str

    def validate(self) -> None:
        if self.asset_class not in {"stock", "crypto"}:
            raise ValueError("Invalid asset class")
        if not self.event_id or not self.symbol or not self.source:
            raise ValueError("Reference identity and source required")
        if self.eligible_at.tzinfo is None or self.eligible_at.utcoffset() is None:
            raise ValueError("Aware eligibility timestamp required")


def reference_recall(references: list[ReferenceOpportunity], detected: set[str]) -> dict:
    """Compute recall only against explicitly supplied independent references."""
    for item in references:
        item.validate()
    keys = [(item.asset_class, item.event_id) for item in references]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate reference event")
    if not references:
        return {"status": "unavailable", "reason": "empty_reference_set", "recall": None}
    # Identifiers must be stable and namespaced by asset class.
    matched = sum(f"{item.asset_class}:{item.event_id}" in detected for item in references)
    return {
        "status": "measured_against_supplied_reference",
        "reference_count": len(references),
        "detected_count": matched,
        "missed_count": len(references) - matched,
        "recall": matched / len(references),
        "methodology": "reference_set_dependent_not_universe_wide_recall",
    }
