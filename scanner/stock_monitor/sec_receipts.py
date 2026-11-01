"""Convert existing SEC cache records into isolated stock-monitor receipts.

Pure adapter: no network calls and no HEBELTRADER import. SEC acceptance
timestamps are interpreted as America/New_York local time, not UTC.
"""

from __future__ import annotations

import json
from datetime import datetime
from hashlib import sha256
from zoneinfo import ZoneInfo

from scanner.stock_monitor.journal import Evidence

SEC_ZONE = ZoneInfo("America/New_York")
FORMS = frozenset({"8-K", "6-K", "SC 13D", "SC 13D/A", "10-Q", "10-K"})


def receipts_from_submissions(record: dict, *, cik: int, symbol: str) -> list[Evidence]:
    if cik <= 0 or not symbol:
        raise ValueError("Verified CIK and symbol required")
    payload = record["payload"]
    recent = payload["filings"]["recent"]
    keys = ("accessionNumber", "acceptanceDateTime", "form")
    if any(key not in recent for key in keys):
        raise ValueError("Missing SEC submission columns")
    count = len(recent["form"])
    if any(len(recent[key]) != count for key in keys):
        raise ValueError("Misaligned SEC submission columns")
    retrieved = datetime.fromisoformat(record["retrieved_at"])
    if retrieved.tzinfo is None or retrieved.utcoffset() is None:
        raise ValueError("Retrieval timestamp must include timezone")
    # The SEC archive snapshot hash is a provenance receipt for the submissions
    # response, not a hash of each filing's full text.
    raw_hash = record.get("raw_sha256")
    if (
        not isinstance(raw_hash, str)
        or len(raw_hash) != 64
        or any(c not in "0123456789abcdef" for c in raw_hash)
    ):
        raise ValueError("Invalid SEC response hash")
    result = []
    for i in range(count):
        form = recent["form"][i]
        if form not in FORMS:
            continue
        accession = recent["accessionNumber"][i]
        if not isinstance(accession, str) or not accession.replace("-", "").isdigit():
            raise ValueError("Invalid accession number")
        raw_time = recent["acceptanceDateTime"][i]
        accepted = datetime.fromisoformat(raw_time)
        if accepted.tzinfo is None:
            accepted = accepted.replace(tzinfo=SEC_ZONE)
        url = (
            f"https://www.sec.gov/Archives/edgar/data/{cik}/"
            f"{accession.replace('-', '')}/{accession}-index.html"
        )
        result.append(
            Evidence(
                event_id=f"sec:{accession}",
                symbol=symbol,
                source_url=url,
                source_type="primary",
                published_at=accepted,
                first_seen_at=retrieved,
                retrieved_at=retrieved,
                content_sha256=raw_hash,
            )
        )
    return result


def record_sha256(payload: dict) -> str:
    """Hash deterministic test/replay payload; not a substitute for raw-response hash."""
    return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
