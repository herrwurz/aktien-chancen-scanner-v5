from datetime import UTC
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from scanner.domain import Candle


class UTCDateTime(TypeDecorator):
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            if value.tzinfo is None:
                raise ValueError("Timezone required")
            return value.astimezone(UTC)

    def process_result_value(self, value, dialect):
        if value is not None:
            return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class Base(DeclarativeBase):
    pass


class MarketCandle(Base):
    __tablename__ = "market_candles"
    __table_args__ = (
        UniqueConstraint(
            "provider", "asset_class", "symbol", "interval", "open_time", name="uq_bar"
        ),
        CheckConstraint("volume >= 0 AND quote_volume >= 0", name="ck_nonnegative_volume"),
        CheckConstraint("close_time > open_time", name="ck_candle_time"),
        Index("ix_market_history", "provider", "asset_class", "symbol", "interval", "open_time"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(40))
    asset_class: Mapped[str] = mapped_column(String(16))
    symbol: Mapped[str] = mapped_column(String(30))
    interval: Mapped[str] = mapped_column(String(4))
    open_time: Mapped[object] = mapped_column(UTCDateTime())
    close_time: Mapped[object] = mapped_column(UTCDateTime())
    open: Mapped[Decimal] = mapped_column(Numeric(38, 18))
    high: Mapped[Decimal] = mapped_column(Numeric(38, 18))
    low: Mapped[Decimal] = mapped_column(Numeric(38, 18))
    close: Mapped[Decimal] = mapped_column(Numeric(38, 18))
    volume: Mapped[Decimal] = mapped_column(Numeric(38, 18))
    quote_volume: Mapped[Decimal] = mapped_column(Numeric(38, 18))
    observed_at: Mapped[object] = mapped_column(UTCDateTime())

    def to_candle(self):
        return Candle(**{key: getattr(self, key) for key in Candle.model_fields})


class Evaluation(Base):
    __tablename__ = "evaluations"
    __table_args__ = (
        UniqueConstraint("candle_id", "detector_key", name="uq_evaluation"),
        Index("ix_evaluated_at", "evaluated_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    candle_id: Mapped[int] = mapped_column(ForeignKey("market_candles.id", ondelete="CASCADE"))
    detector_key: Mapped[str] = mapped_column(String(160))
    evaluated_at: Mapped[object] = mapped_column(UTCDateTime())
    is_signal: Mapped[bool] = mapped_column(Boolean)
    reason: Mapped[str] = mapped_column(String(40))
    baseline_volume: Mapped[Decimal | None] = mapped_column(Numeric(38, 18))
    ratio: Mapped[Decimal | None] = mapped_column(Numeric(38, 18))
    candle: Mapped[MarketCandle] = relationship(lazy="joined")


class Signal(Base):
    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(primary_key=True)
    evaluation_id: Mapped[int] = mapped_column(
        ForeignKey("evaluations.id", ondelete="CASCADE"),
        unique=True,
    )
    evaluation: Mapped[Evaluation] = relationship(lazy="joined")


class Outcome(Base):
    """Schema foundation only; no fabricated historical performance."""

    __tablename__ = "outcomes"
    __table_args__ = (
        UniqueConstraint("signal_id", "horizon_hours", name="uq_outcome_horizon"),
        CheckConstraint("horizon_hours IN (1, 4, 24)", name="ck_outcome_horizon"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    signal_id: Mapped[int] = mapped_column(ForeignKey("signals.id", ondelete="CASCADE"))
    horizon_hours: Mapped[int] = mapped_column(Integer)
    measured_at: Mapped[object] = mapped_column(UTCDateTime())
    return_pct: Mapped[Decimal] = mapped_column(Numeric(38, 18))


class ScanRun(Base):
    __tablename__ = "scan_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    started_at: Mapped[object] = mapped_column(UTCDateTime(), index=True)
    finished_at: Mapped[object | None] = mapped_column(UTCDateTime())
    provider: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(16))
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[list] = mapped_column(JSON, default=list)
