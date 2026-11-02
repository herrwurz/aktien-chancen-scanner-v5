"""Conservative, point-in-time SEC filing triage. Not an investment signal."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

NEW_YORK = ZoneInfo("America/New_York")
PRIORITY = {
    "8-K": "high",
    "6-K": "high",
    "SC 13D": "high",
    "SC 13D/A": "medium",
    "10-Q": "medium",
    "10-K": "medium",
}


def recent_filing_events(
    record: dict, *, symbol: str, cutoff: datetime, lookback_hours: int = 72
) -> list[dict]:
    """Report only filings accepted within the window and observed by cutoff."""
    if cutoff.tzinfo is None or cutoff.utcoffset() is None:
        raise ValueError("Aware cutoff required")
    if not 1 <= lookback_hours <= 168:
        raise ValueError("lookback_hours must be 1..168")
    recent = record["payload"]["filings"]["recent"]
    required = ("form", "acceptanceDateTime", "accessionNumber")
    if any(key not in recent for key in required):
        raise ValueError("Missing SEC filing columns")
    count = len(recent["form"])
    if any(len(recent[key]) != count for key in required):
        raise ValueError("Misaligned SEC filing columns")
    retrieved = datetime.fromisoformat(record["retrieved_at"])
    if retrieved.tzinfo is None or retrieved.utcoffset() is None:
        raise ValueError("SEC retrieval timestamp must be aware")
    now = cutoff.astimezone(UTC)
    if retrieved.astimezone(UTC) > now:
        raise ValueError("SEC response not yet observable at cutoff")
    start = now - timedelta(hours=lookback_hours)
    events = []
    for index in range(count):
        form = recent["form"][index]
        if form not in PRIORITY:
            continue
        accepted = datetime.fromisoformat(recent["acceptanceDateTime"][index])
        if accepted.tzinfo is None:
            accepted = accepted.replace(tzinfo=NEW_YORK)
        accepted = accepted.astimezone(UTC)
        if not start <= accepted <= now:
            continue
        accession = recent["accessionNumber"][index]
        if not isinstance(accession, str) or not accession.replace("-", "").isdigit():
            raise ValueError("Invalid accession number")
        events.append(
            {
                "symbol": symbol,
                "form": form,
                "priority": PRIORITY[form],
                "accepted_at": accepted.isoformat(),
                "accession": accession,
                "classification": "filing_type_only_unverified_content",
            }
        )
    return sorted(events, key=lambda item: item["accepted_at"], reverse=True)
