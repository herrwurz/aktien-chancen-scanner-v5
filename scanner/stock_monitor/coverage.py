"""Cross-asset scan coverage contract, adapted from crypto V3 quality lessons.

Shared evidence accounting only. Stock and crypto strategies remain independent.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

CoverageState = Literal["checked", "rejected", "unavailable"]


@dataclass(frozen=True)
class SourceCoverage:
    source: str
    state: CoverageState
    observed_at: datetime | None
    reason: str

    def validate(self) -> None:
        if not self.source.strip() or not self.reason.strip():
            raise ValueError("Coverage source and reason required")
        if self.state not in {"checked", "rejected", "unavailable"}:
            raise ValueError("Unknown coverage state")
        if self.state != "unavailable" and self.observed_at is None:
            raise ValueError("Checked/rejected sources require observation timestamp")
        if self.observed_at is not None and (
            self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None
        ):
            raise ValueError("Coverage timestamps must be timezone-aware")


def summarize_coverage(sources: list[SourceCoverage]) -> dict:
    """Never treat missing access as a scan with no candidates."""
    for source in sources:
        source.validate()
    if len({source.source for source in sources}) != len(sources):
        raise ValueError("Duplicate source coverage")
    counts = {
        state: sum(source.state == state for source in sources)
        for state in ("checked", "rejected", "unavailable")
    }
    return {
        "coverage": counts,
        "complete": bool(sources) and counts["unavailable"] == 0,
        "sources": [
            {
                "source": source.source,
                "state": source.state,
                "observed_at": (
                    source.observed_at.isoformat() if source.observed_at is not None else None
                ),
                "reason": source.reason,
            }
            for source in sources
        ],
    }
