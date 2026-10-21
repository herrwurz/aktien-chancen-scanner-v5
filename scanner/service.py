import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from scanner.detector import VolumeDetector
from scanner.domain import Candle
from scanner.models import Evaluation, MarketCandle, ScanRun, Signal
from scanner.providers.base import MarketDataProvider

logger = logging.getLogger(__name__)


def ingest(session, candles: list[Candle], detector: VolumeDetector, now: datetime):
    """Immutable first-observation import; caller owns transaction and worker lock."""
    insert = pg_insert if session.bind.dialect.name == "postgresql" else sqlite_insert
    for candle in sorted(candles, key=lambda c: c.open_time):
        if candle.close_time > now:
            continue
        key = dict(
            zip(("provider", "asset_class", "symbol", "interval"), candle.market, strict=True)
        )
        session.execute(
            insert(MarketCandle)
            .values(
                **candle.model_dump(),
                observed_at=now,
            )
            .on_conflict_do_nothing(index_elements=[*key, "open_time"])
        )
        record = session.scalar(select(MarketCandle).filter_by(**key, open_time=candle.open_time))
        existing = session.scalar(
            select(Evaluation.id).filter_by(
                candle_id=record.id,
                detector_key=detector.config_key,
            )
        )
        if existing is not None:
            continue
        history = session.scalars(
            select(MarketCandle)
            .filter_by(**key)
            .where(
                MarketCandle.open_time < candle.open_time,
            )
            .order_by(MarketCandle.open_time.desc())
            .limit(detector.lookback)
        ).all()
        decision = detector.evaluate([h.to_candle() for h in history], record.to_candle())
        evaluation = Evaluation(
            candle_id=record.id,
            detector_key=detector.config_key,
            evaluated_at=now,
            is_signal=decision.is_signal,
            reason=decision.reason,
            baseline_volume=decision.baseline_volume,
            ratio=decision.ratio,
        )
        session.add(evaluation)
        session.flush()
        if decision.is_signal:
            session.add(Signal(evaluation_id=evaluation.id))
    session.flush()


async def scan_once(sessions, provider: MarketDataProvider, symbols, intervals, detector, now=None):
    now = now or datetime.now(UTC)
    with sessions.begin() as session:
        run = ScanRun(started_at=now, provider=provider.name, status="running", errors=[])
        session.add(run)
        session.flush()
        run_id = run.id
    errors = []
    total = 0
    for symbol in symbols:
        for interval in intervals:
            total += 1
            try:
                candles = await provider.fetch_candles(
                    symbol,
                    interval,
                    limit=detector.lookback + 2,
                    now=now,
                )
                if not candles:
                    raise ValueError("No closed candles")
                if any(
                    c.symbol != symbol
                    or c.interval != interval
                    or c.provider != provider.name
                    or c.asset_class != provider.asset_class
                    for c in candles
                ):
                    raise ValueError("Provider returned another market")
                with sessions.begin() as session:
                    ingest(session, candles, detector, now)
            except Exception as exc:
                # Persist only class and market; URLs, passwords and payloads stay out of logs.
                errors.append({"symbol": symbol, "interval": interval, "error": type(exc).__name__})
                logger.warning("Scan failed for %s %s: %s", symbol, interval, type(exc).__name__)
    status = "failed" if len(errors) == total else ("partial" if errors else "ok")
    with sessions.begin() as session:
        run = session.get(ScanRun, run_id)
        run.status = status
        run.finished_at = datetime.now(UTC)
        run.error_count = len(errors)
        run.errors = errors
    return status
