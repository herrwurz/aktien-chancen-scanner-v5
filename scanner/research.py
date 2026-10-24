"""Shared provenance models for research strategies; never trading decisions."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field


class AssetIdentity(BaseModel):
    asset_type: Literal["stock", "derivative"]
    name: str
    ticker: str | None = None
    wkn: str | None = None
    isin: str | None = None
    lei: str | None = None
    cik: str | None = None
    exchange: str | None = None
    mic: str | None = None
    country: str | None = None
    sector: str | None = None
    instrument_type: Literal["operating_company", "fund", "other", "unknown"] = "unknown"
    instrument_type_status: Literal["source_verified", "inferred", "unknown"] = "unknown"
    instrument_type_evidence: str | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    quality_status: Literal["verified", "candidate", "conflicted", "incomplete"] = "candidate"
    source_id: str | None = None
    retrieved_at: datetime | None = None
    source_available_at: datetime | None = None

    def historically_available_at(self, point_in_time):
        return self.source_available_at is not None and self.source_available_at <= point_in_time


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


class CompanyFact(BaseModel):
    fact_id: str
    asset: AssetIdentity
    metric: str
    claim: Literal[
        "reported_value",
        "year_over_year_increase",
        "year_over_year_decrease",
        "unchanged",
    ]
    value: Decimal
    unit: str
    period_start: date
    period_end: date
    comparison_value: Decimal | None = None
    comparison_period_start: date | None = None
    comparison_period_end: date | None = None
    source_url: str = Field(min_length=1)
    source_location: str = Field(min_length=1)
    published_at: datetime
    source_available_at: datetime | None = None
    retrieved_at: datetime
    extraction_method: str
    verification_status: Literal["source_verified", "unknown"]
    content_sha256: str


class ProviderStatus(BaseModel):
    provider: str
    status: Literal["ok", "partial", "offline_fixture", "unavailable", "dry_run"]
    retrieved_at: datetime
    record_count: int = 0
    cache_hit: bool = False
    error_code: str | None = None
    data_age_seconds: int | None = None
