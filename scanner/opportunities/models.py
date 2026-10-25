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
    liquidity_price_basis: Literal["raw_close_x_raw_volume_usd"]
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
    evidence_status: str
    verification_status: Literal["confirmed", "context_only"]


class InstrumentTypeReview(StrictModel):
    asset_id: str
    cik: str
    ticker: str
    instrument_type: Literal["operating_company", "fund", "other"]
    source_url: str
    source_sha256: str
    source_retrieved_at: datetime
    reviewer: str
    reviewed_at: datetime


class RiskScenario(StrictModel):
    reference_date: date
    reference_price: Decimal
    entry_basis: Literal["modeled_reference_close"] = "modeled_reference_close"
    reference_price_basis: Literal["raw_session_close"] = "raw_session_close"
    feature_price_basis: Literal["adjusted_ohlc"] = "adjusted_ohlc"
    raw_per_adjusted_scale: Decimal
    raw_atr_14: Decimal
    stop_price: Decimal
    target_price: Decimal
    gross_crv: Decimal
    assumed_round_trip_cost_bps: Decimal
    spread_status: Literal["unavailable"] = "unavailable"
    net_crv: None = None
    executable: Literal[False] = False


class StrategyChannel(StrictModel):
    status: Literal["inactive", "triggered", "awaiting_confirmation"]
    reasons: list[str]


class OpportunityCandidate(StrictModel):
    asset_id: str
    ticker: str | None
    name: str
    exchange: str | None
    mic: str | None
    status: Literal["candidate_research", "watch_only", "unavailable"]
    score: int
    score_reasons: list[str]
    selection_reasons: list[str]
    failed_gates: list[str]
    uncertainties: list[str]
    features: TechnicalFeatures | None
    catalysts: list[CatalystEvidence]
    risk: RiskScenario | None
    strategy_channels: dict[str, StrategyChannel]
    historical_availability_verified: Literal[False] = False
    training_eligible: Literal[False] = False
    probability_claimed: Literal[False] = False
