"""Provider-neutral news evidence models; never strategy decisions."""

from datetime import datetime
from typing import Literal, Protocol

from pydantic import BaseModel, Field, model_validator


class NewsItem(BaseModel):
    source_id: str
    source_type: Literal["PRIMARY", "SECONDARY", "COMMUNITY"]
    url: str
    title: str
    published_at: datetime
    first_seen_at: datetime
    retrieved_at: datetime
    source_available_at: datetime
    actual_event_at: datetime | None = None
    company_identifiers: dict[str, list[str]] = Field(default_factory=dict)
    event_type: str = "unknown"
    event_confidence: Literal["source_claim", "inferred", "unknown"] = "unknown"
    evidence_status: str = "unknown"
    license_status: Literal["permitted_metadata", "metadata_only", "unknown"]
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    origin_id: str

    @model_validator(mode="after")
    def community_is_not_a_verified_fact(self):
        if self.source_type == "COMMUNITY" and self.evidence_status == "verified_company_fact":
            raise ValueError("community evidence cannot verify a company fact")
        return self

    def available_at(self, point_in_time):
        return max(self.published_at, self.source_available_at) <= point_in_time


class NewsBatch(BaseModel):
    provider: str
    status: Literal["ok", "partial", "unavailable"]
    items: list[NewsItem] = Field(default_factory=list)
    retrieved_at: datetime
    cache_hit: bool = False
    request_count: int = 0
    cost_eur: float = 0
    errors: list[str] = Field(default_factory=list)
    coverage: dict = Field(default_factory=dict)


class NewsSource(Protocol):
    def fetch(self, query, *, start, end, limit, **kwargs) -> NewsBatch: ...
