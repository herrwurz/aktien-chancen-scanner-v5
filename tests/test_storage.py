import asyncio
from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from test_domain import START, candle

from scanner.detector import VolumeDetector
from scanner.models import Base, Evaluation, MarketCandle, ScanRun, Signal
from scanner.service import ingest, scan_once


@pytest.fixture
def sessions():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    yield sessionmaker(engine)
    engine.dispose()


def test_import_is_idempotent_and_auditable(sessions):
    data = [candle(i, "40" if i == 3 else "10") for i in range(4)]
    now = START + timedelta(hours=1)
    detector = VolumeDetector(lookback=3)
    for _ in range(2):
        with sessions.begin() as session:
            ingest(session, data, detector, now)
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(MarketCandle)) == 4
        assert session.scalar(select(func.count()).select_from(Evaluation)) == 4
        assert session.scalar(select(func.count()).select_from(Signal)) == 1
        result = session.scalar(select(Evaluation).where(Evaluation.is_signal.is_(True)))
        assert result.ratio == 4
        assert result.evaluated_at == now
        assert result.reason == "volume_spike"
        assert result.detector_key == detector.config_key
        assert result.candle.close_time < result.evaluated_at


def test_open_candles_never_persist(sessions):
    with sessions.begin() as session:
        ingest(
            session,
            [candle(0), candle(1)],
            VolumeDetector(lookback=1),
            START + timedelta(minutes=5),
        )
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(MarketCandle)) == 1


def test_new_detector_settings_have_separate_decisions(sessions):
    data = [candle(0), candle(1, "40")]
    with sessions.begin() as session:
        ingest(session, data, VolumeDetector(lookback=1), START + timedelta(hours=1))
        ingest(
            session,
            data,
            VolumeDetector(lookback=1, threshold=Decimal("5")),
            START + timedelta(hours=2),
        )
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(Evaluation)) == 4
        assert session.scalar(select(func.count()).select_from(Signal)) == 1


def test_reimport_does_not_rewrite_original_data_or_decision(sessions):
    now = START + timedelta(hours=1)
    with sessions.begin() as session:
        ingest(session, [candle(0)], VolumeDetector(lookback=1), now)
    with sessions.begin() as session:
        ingest(session, [candle(0, "999")], VolumeDetector(lookback=1), now + timedelta(hours=1))
    with sessions() as session:
        assert session.scalar(select(MarketCandle)).volume == 10
        assert session.scalar(select(Evaluation)).evaluated_at == now


def test_failed_symbol_does_not_block_other_symbols(sessions):
    class Provider:
        name = "fixture"
        asset_class = "crypto"

        async def fetch_candles(self, symbol, interval, **kwargs):
            if symbol == "BADUSDT":
                raise RuntimeError("provider failed")
            return [candle(0), candle(1, "40")]

    result = asyncio.run(
        scan_once(
            sessions,
            Provider(),
            ["BADUSDT", "BTCUSDT"],
            ["5m"],
            VolumeDetector(lookback=1),
            START + timedelta(hours=1),
        )
    )
    assert result == "partial"
    with sessions() as session:
        assert session.scalar(select(ScanRun)).error_count == 1
        assert session.scalar(select(func.count()).select_from(Signal)) == 1


def test_rollback_keeps_batch_atomic(sessions):
    with pytest.raises(RuntimeError), sessions.begin() as session:
        ingest(session, [candle(0)], VolumeDetector(), START + timedelta(hours=1))
        raise RuntimeError("rollback")
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(MarketCandle)) == 0


def test_audit_times_follow_each_provider_response(sessions, monkeypatch):
    from datetime import datetime

    import scanner.service as service

    current = START + timedelta(hours=1)
    received = {}

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return current

    class Provider:
        name = "fixture"
        asset_class = "crypto"

        async def fetch_candles(self, symbol, interval, **kwargs):
            nonlocal current
            current += timedelta(seconds=30)
            received[symbol] = current
            return [candle(0, symbol=symbol), candle(1, "40", symbol=symbol)]

    monkeypatch.setattr(service, "datetime", Clock)
    asyncio.run(
        scan_once(sessions, Provider(), ["BTCUSDT", "ETHUSDT"], ["5m"], VolumeDetector(lookback=1))
    )
    with sessions() as session:
        run = session.scalar(select(ScanRun))
        for evaluation in session.scalars(select(Evaluation)):
            assert run.started_at < received[evaluation.candle.symbol]
            assert received[evaluation.candle.symbol] <= evaluation.candle.observed_at
            assert evaluation.candle.observed_at <= evaluation.evaluated_at <= run.finished_at
