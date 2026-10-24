"""Strict contracts for historical stock data and its provenance."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class InstrumentListing(StrictModel):
    asset_id: str = Field(min_length=1)
    ticker: str = Field(pattern=r"^[A-Z0-9.-]{1,32}$")
    exchange: str = Field(pattern=r"^[A-Za-z0-9 ._-]{2,64}$")
    mic: str = Field(pattern=r"^[A-Z0-9]{4}$")
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    timezone: str
    provider_symbol: str = Field(pattern=r"^[A-Za-z0-9_.^-]{1,64}$")
    cik: str | None = Field(default=None, pattern=r"^[0-9]{10}$")
    isin: str | None = Field(default=None, pattern=r"^[A-Z]{2}[A-Z0-9]{10}$")

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError:
            raise ValueError("invalid timezone") from None
        return value


class PriceVector(StrictModel):
    open: Decimal | None
    high: Decimal | None
    low: Decimal | None
    close: Decimal
    volume: Decimal | None

    @model_validator(mode="after")
    def valid_ohlcv(self):
        values = (self.open, self.high, self.low, self.close)
        if any(value is not None and (not value.is_finite() or value < 0) for value in values):
            raise ValueError("invalid OHLC")
        if self.volume is not None and (not self.volume.is_finite() or self.volume < 0):
            raise ValueError("invalid volume")
        if self.high is not None and self.low is not None:
            known = [value for value in (self.open, self.close) if value is not None]
            if self.low > self.high or any(not self.low <= value <= self.high for value in known):
                raise ValueError("invalid OHLC range")
        return self


class DailyBar(StrictModel):
    session_date: date
    session_end_at: datetime
    modeled_available_at: datetime
    raw: PriceVector
    adjusted: PriceVector
    retrieved_at: datetime
    historical_availability_verified: bool = False
    source_pointer: str

    @model_validator(mode="after")
    def aware_clocks(self):
        for value in (self.session_end_at, self.modeled_available_at, self.retrieved_at):
            if value.utcoffset() is None:
                raise ValueError("aware timestamps required")
        if self.modeled_available_at < self.session_end_at:
            raise ValueError("availability precedes session close")
        return self


class CorporateAction(StrictModel):
    kind: Literal["dividend", "split"]
    effective_date: date
    value: Decimal
    currency: str | None = None
    source_pointer: str

    @model_validator(mode="after")
    def valid_action(self):
        if not self.value.is_finite() or self.value <= 0:
            raise ValueError("invalid corporate action")
        if self.kind == "dividend" and self.currency is None:
            raise ValueError("dividend currency required")
        if self.kind == "split" and self.currency is not None:
            raise ValueError("split currency forbidden")
        return self


class Quote(StrictModel):
    at: datetime
    bid: Decimal
    ask: Decimal
    source_pointer: str

    @model_validator(mode="after")
    def valid_quote(self):
        if self.at.utcoffset() is None or self.bid < 0 or self.ask < self.bid:
            raise ValueError("invalid observed quote")
        return self


class MarketDataBatch(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    provider: Literal["Tiingo", "EODHD"]
    instrument: InstrumentListing
    bars: list[DailyBar]
    actions: list[CorporateAction]
    quotes: list[Quote] = Field(default_factory=list)
    quote_availability: Literal["observed", "not_provided"] = "not_provided"
    retrieved_at: datetime
    source_reference: str
    license_reference: str
    raw_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    availability_basis: Literal["modeled_session_close", "historically_verified"]
    training_eligible: bool = False

    @model_validator(mode="after")
    def consistent(self):
        if self.retrieved_at.utcoffset() is None:
            raise ValueError("aware retrieval timestamp required")
        dates = [bar.session_date for bar in self.bars]
        if len(dates) != len(set(dates)):
            raise ValueError("duplicate session")
        if dates != sorted(dates):
            raise ValueError("unordered sessions")
        if bool(self.quotes) != (self.quote_availability == "observed"):
            raise ValueError("quote availability mismatch")
        return self
