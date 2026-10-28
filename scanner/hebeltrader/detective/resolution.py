"""Operator-entered post-freeze resolution; separate from teaser input schemas."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ResolutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    asset_id: str = Field(min_length=1, max_length=300)
    name: str = Field(min_length=1, max_length=300)
    source: str = Field(min_length=1, max_length=2000)
    basis: Literal["user", "primary_source"] = "user"
    call_wkn: str | None = Field(default=None, pattern=r"^[A-Z0-9]{6}$")
    error_analysis: str = Field(min_length=1, max_length=5000)
    algorithm_change: str = Field(default="", max_length=5000)
    confirmed_at: str | None = None
    original_sha256: str | None = None
