"""Point-in-time, append-only evidence journal for stock research.

No order execution, market data fetching, or HEBELTRADER dependency.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Literal


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Timestamp must be timezone-aware")
    return value.astimezone(UTC)


def utc(value: datetime) -> str:
    return as_utc(value).isoformat()


@dataclass(frozen=True)
class Evidence:
    event_id: str
    symbol: str
    source_url: str
    source_type: Literal["primary", "secondary", "community"]
    published_at: datetime
    first_seen_at: datetime
    retrieved_at: datetime
    content_sha256: str

    def validate(self, cutoff: datetime) -> None:
        if not all((self.event_id, self.symbol, self.source_url)):
            raise ValueError("Missing event identity")
        if not self.source_url.startswith(("https://", "http://")):
            raise ValueError("Source URL required")
        if len(self.content_sha256) != 64 or any(
            c not in "0123456789abcdef" for c in self.content_sha256
        ):
            raise ValueError("Invalid SHA256")
        if not (
            as_utc(self.published_at)
            <= as_utc(self.first_seen_at)
            <= as_utc(self.retrieved_at)
            <= as_utc(cutoff)
        ):
            raise ValueError("Evidence unavailable at cutoff")


@dataclass(frozen=True)
class Decision:
    event_id: str
    status: Literal["event_detected", "research_candidate", "paper_entry_eligible", "rejected"]
    reason: str
    quote_kind: Literal["eod", "delayed", "executable", "unavailable"]
    quote_timestamp: datetime | None = None
    entry_limit: float | None = None
    stop: float | None = None
    target: float | None = None

    def validate(self, cutoff: datetime) -> None:
        if not self.reason.strip():
            raise ValueError("Reason required")
        if self.quote_timestamp is not None and as_utc(self.quote_timestamp) > as_utc(cutoff):
            raise ValueError("Look-ahead quote")
        if self.status == "paper_entry_eligible":
            if self.quote_kind != "executable" or self.quote_timestamp is None:
                raise ValueError("Executable timestamped quote required")
            if any(v is None or v <= 0 for v in (self.entry_limit, self.stop, self.target)):
                raise ValueError("Paper scenario requires positive entry, stop, target")
            if not self.stop < self.entry_limit < self.target:
                raise ValueError("Invalid long risk scenario")


def append_run(
    path: Path,
    *,
    run_id: str,
    cutoff: datetime,
    evidence: list[Evidence],
    decisions: list[Decision],
    code_version: str,
    coverage: str,
) -> str:
    """Append one SHA-linked JSONL record. Never silently rewrite prior runs."""
    if not run_id or not code_version or not coverage:
        raise ValueError("Missing run metadata")
    cutoff_utc = utc(cutoff)
    for event in evidence:
        event.validate(cutoff)
    ids = {event.event_id for event in evidence}
    for decision in decisions:
        decision.validate(cutoff)
        if decision.event_id not in ids:
            raise ValueError("Decision without evidence")

    def serial(value: object) -> object:
        if isinstance(value, datetime):
            return utc(value)
        raise TypeError(type(value).__name__)

    payload = {
        "run_id": run_id,
        "cutoff": cutoff_utc,
        "code_version": code_version,
        "coverage": coverage,
        "evidence": [asdict(e) for e in evidence],
        "decisions": [asdict(d) for d in decisions],
    }
    serialized = json.dumps(payload, default=serial, sort_keys=True, separators=(",", ":"))
    path.parent.mkdir(parents=True, exist_ok=True)
    previous = "0" * 64
    if path.exists():
        with path.open(encoding="utf-8") as reader:
            for line in reader:
                item = json.loads(line)
                expected = sha256((item["previous_sha256"] + item["payload"]).encode()).hexdigest()
                if item["record_sha256"] != expected or item["previous_sha256"] != previous:
                    raise ValueError("Corrupted journal chain")
                if json.loads(item["payload"])["run_id"] == run_id:
                    raise ValueError("Duplicate run_id")
                previous = expected
    digest = sha256((previous + serialized).encode()).hexdigest()
    with path.open("a", encoding="utf-8") as writer:
        writer.write(
            json.dumps(
                {"previous_sha256": previous, "payload": serialized, "record_sha256": digest},
                sort_keys=True,
            )
            + "\n"
        )
    return digest
