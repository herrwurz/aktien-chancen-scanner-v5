"""Strict contracts for research-only opportunity features and decisions."""

from datetime import date
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
