"""Read-only research-index query and result contracts."""

from typing import Literal

from pydantic import BaseModel, Field

from scanner.research import AssetIdentity


class CandidateQuery(BaseModel):
    text: str | None = None
    sectors: list[str] = Field(default_factory=list)
    countries: list[str] = Field(default_factory=list)
    event_types: list[str] = Field(default_factory=list)
    fact_claims: list[str] = Field(default_factory=list)

    def constrained(self):
        return bool(
            (self.text or "").strip()
            or self.sectors
            or self.countries
            or self.event_types
            or self.fact_claims
        )


class CandidateHit(BaseModel):
    identity: AssetIdentity
    score: int
    confirmed: list[str]
    contradicted: list[str]
    unknown: list[str]
    evidence_source_ids: list[str]
    retrieval_channels: list[str] = Field(default_factory=list)


class CandidateBatch(BaseModel):
    status: Literal["ok", "unresolved", "insufficiently_constrained"]
    candidates: list[CandidateHit]
    full_universe_size: int
    visible_universe_size: int
    matched_before_limit: int
    limit: int
    index_payload_sha256: str
    weak_match_count: int = 0
    coverage_warnings: list[str] = Field(default_factory=list)
