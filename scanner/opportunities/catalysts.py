"""Point-in-time catalyst selection for the short-term research scanner."""

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from scanner.opportunities.models import CatalystEvidence

_SUPPORTED_EVENTS = {
    "acquisition_or_stake",
    "analyst_revision",
    "earnings_surprise",
    "guidance_raise",
    "major_contract",
    "partnership",
    "quarterly_results",
    "regulatory_decision",
}
_SOURCE_TYPES = {"PRIMARY", "SECONDARY", "COMMUNITY"}


def _timestamp(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(UTC)


def select_catalysts(
    evidence: Iterable[dict[str, Any]], *, signal_at: datetime
) -> list[CatalystEvidence]:
    """Return only evidence proven public by ``signal_at``.

    Community messages remain context and never become confirmed company facts.
    Missing timestamps fail closed because their historical availability cannot be
    established.
    """

    if signal_at.tzinfo is None:
        raise ValueError("signal_at must be timezone-aware")
    cutoff = signal_at.astimezone(UTC)
    selected: list[CatalystEvidence] = []
    for row in evidence:
        published_at = _timestamp(row.get("published_at"))
        available_at = _timestamp(row.get("source_available_at"))
        source_type = str(row.get("source_type", "")).upper()
        event_type = str(row.get("event_type", ""))
        if (
            published_at is None
            or available_at is None
            or published_at > cutoff
            or available_at > cutoff
            or source_type not in _SOURCE_TYPES
            or event_type not in _SUPPORTED_EVENTS
        ):
            continue
        try:
            selected.append(
                CatalystEvidence(
                    source_id=str(row["source_id"]),
                    source_type=source_type,
                    url=str(row["url"]),
                    title=str(row["title"]),
                    event_type=event_type,
                    published_at=published_at,
                    source_available_at=available_at,
                    verification_status=(
                        "context_only" if source_type == "COMMUNITY" else "confirmed"
                    ),
                )
            )
        except (KeyError, ValueError):
            continue
    return sorted(selected, key=lambda item: item.source_id)
