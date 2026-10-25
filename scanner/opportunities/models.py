"""Strict contracts for research-only opportunity features and decisions."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TechnicalFeatures(StrictModel):
    signal_date: date
    session_count_available: int
    raw_reference_close: Decimal
    adjusted_reference_close: Decimal
    momentum_5: Decimal
    momentum_10: Decimal
    momentum_20: Decimal
    average_volume_prior_20: Decimal
    volume_ratio: Decimal
    median_dollar_volume_20: Decimal
    atr_14: Decimal
    atr_percent: Decimal
    gap_percent: Decimal
    trend: Literal["up", "down", "flat"]
    prior_20_high: Decimal
    distance_to_prior_20_high: Decimal
    breakout_20: bool
    relative_strength_20: Decimal | None
    benchmark_status: Literal["available", "unavailable"]


class CatalystEvidence(StrictModel):
    source_id: str
    source_type: Literal["PRIMARY", "SECONDARY", "COMMUNITY"]
    url: str
    title: str
    event_type: str
    published_at: datetime
    source_available_at: datetime
    verification_status: Literal["confirmed", "context_only"]


class RiskScenario(StrictModel):
    reference_date: date
    reference_price: Decimal
    entry_basis: Literal["modeled_reference_close"] = "modeled_reference_close"
    stop_price: Decimal
    target_price: Decimal
    gross_crv: Decimal
    assumed_round_trip_cost_bps: Decimal
    spread_status: Literal["unavailable"] = "unavailable"
    net_crv: None = None
    executable: Literal[False] = False


class OpportunityCandidate(StrictModel):
    asset_id: str
    ticker: str | None
    name: str
    status: Literal["candidate_research", "watch_only", "unavailable"]
    score: int
    score_reasons: list[str]
    selection_reasons: list[str]
    failed_gates: list[str]
    uncertainties: list[str]
    features: TechnicalFeatures | None
    catalysts: list[CatalystEvidence]
    risk: RiskScenario | None
    historical_availability_verified: Literal[False] = False
    training_eligible: Literal[False] = False
    probability_claimed: Literal[False] = False
