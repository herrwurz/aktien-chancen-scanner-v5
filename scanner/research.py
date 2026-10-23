"""Shared provenance models for research strategies; never trading decisions."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class AssetIdentity(BaseModel):
    asset_type: Literal["stock", "derivative"]
    name: str
    ticker: str | None = None
    wkn: str | None = None
    isin: str | None = None


class EvidenceRecord(BaseModel):
    source_id: str
    url: str
    title: str
    published_at: datetime
    retrieved_at: datetime
    effective_at: datetime
    source_kind: Literal["fixture", "issuer", "regulatory", "news", "product_document"]
    facts: dict[str, Any] = Field(default_factory=dict)
    content_sha256: str

    def available_at(self, point_in_time):
        return all(
            timestamp <= point_in_time
            for timestamp in (self.published_at, self.retrieved_at, self.effective_at)
        )
