from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

INTERVALS = {"5m": timedelta(minutes=5), "15m": timedelta(minutes=15)}


class Candle(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider: str
    asset_class: Literal["crypto", "stock"]
    symbol: str
    interval: Literal["5m", "15m"]
    open_time: datetime
    close_time: datetime  # exclusive boundary, normalized from exchange timestamps
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    quote_volume: Decimal

    @field_validator("open_time", "close_time")
    @classmethod
    def utc_time(cls, value):
        if value.tzinfo is None:
            raise ValueError("Timezone required")
        return value.astimezone(UTC)

    @field_validator("open", "high", "low", "close", "volume", "quote_volume")
    @classmethod
    def finite_nonnegative(cls, value):
        if not value.is_finite() or value < 0:
            raise ValueError("Expected finite nonnegative decimal")
        return value

    @model_validator(mode="after")
    def valid_bar(self):
        if self.close_time - self.open_time != INTERVALS[self.interval]:
            raise ValueError("Candle duration must match interval")
        if self.low <= 0 or self.high < max(self.open, self.close, self.low):
            raise ValueError("Invalid OHLC range")
        if self.low > min(self.open, self.close):
            raise ValueError("Invalid OHLC range")
        return self

    @property
    def market(self):
        return self.provider, self.asset_class, self.symbol, self.interval
