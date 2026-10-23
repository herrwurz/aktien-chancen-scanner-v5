"""Shared provenance models for research strategies; never trading decisions."""

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class AssetIdentity(BaseModel):
    asset_type: Literal["stock", "derivative"]
    name: str
    ticker: str | None = None
    wkn: str | None = None
    isin: str | None = None
    cik: str | None = None
    exchange: str | None = None
    mic: str | None = None
    country: str | None = None
    sector: str | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    quality_status: Literal["verified", "candidate", "conflicted", "incomplete"] = "candidate"
    source_id: str | None = None
    retrieved_at: datetime | None = None


class EvidenceRecord(BaseModel):
    source_id: str
    url: str
    title: str
    published_at: datetime
    retrieved_at: datetime
    effective_at: datetime
    source_available_at: datetime | None = None
    source_kind: Literal["fixture", "issuer", "regulatory", "news", "product_document"]
    facts: dict[str, Any] = Field(default_factory=dict)
    content_sha256: str

    def available_at(self, point_in_time):
        availability = self.source_available_at or self.retrieved_at
        return all(
            timestamp <= point_in_time
            for timestamp in (self.published_at, availability, self.effective_at)
        )


class CompanyEvent(BaseModel):
    event_id: str
    asset: AssetIdentity
    category: Literal[
        "quarterly_results",
        "earnings_surprise",
        "guidance_raise",
        "guidance_cut",
        "acquisition_or_stake",
        "major_contract",
        "regulatory_decision",
        "management_change",
        "share_buyback",
        "capital_action",
        "regulatory_filing",
    ]
    headline: str
    published_at: datetime
    retrieved_at: datetime
    effective_at: datetime
    evidence: EvidenceRecord
    facts: dict[str, Any] = Field(default_factory=dict)


class ProviderStatus(BaseModel):
    provider: str
    status: Literal["ok", "partial", "offline_fixture", "unavailable", "dry_run"]
    retrieved_at: datetime
    record_count: int = 0
    cache_hit: bool = False
    error_code: str | None = None
    data_age_seconds: int | None = None
