import logging
import sys
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from scanner.detector import VolumeDetector
from scanner.domain import Candle
from scanner.models import Evaluation, MarketCandle, ScanRun, Signal
from scanner.providers.base import MarketDataProvider

logger = logging.getLogger(__name__)


def fail_orphaned_runs(session, now: datetime) -> None:
    """Caller holds the worker lock, so every running row belongs to a dead cycle."""
    session.execute(
        update(ScanRun).where(ScanRun.status == "running").values(status="failed", finished_at=now)
    )


def ingest(session, candles: list[Candle], detector: VolumeDetector, now: datetime, *, clock=None):
    """Immutable first-observation import; caller owns transaction and worker lock."""
    if session.bind is None:
        raise RuntimeError("ingest requires a bound session")
    fresh = [candle for candle in candles if candle.close_time <= now]
    if not fresh:
        return
    insert = pg_insert if session.bind.dialect.name == "postgresql" else sqlite_insert
    grouped: dict[tuple, list[Candle]] = {}
    for candle in fresh:
        grouped.setdefault(candle.market, []).append(candle)
    for market, batch in grouped.items():
        _ingest_market(session, insert, market, batch, detector, now, clock)


def _ingest_market(session, insert, market, batch, detector, now, clock) -> None:
    deduped: list[Candle] = []
    seen: set = set()
    for candle in sorted(batch, key=lambda item: item.open_time):
        if candle.open_time in seen:
            continue
        seen.add(candle.open_time)
        deduped.append(candle)
    key = dict(zip(("provider", "asset_class", "symbol", "interval"), market, strict=True))
    session.execute(
        insert(MarketCandle)
        .values([{**candle.model_dump(), "observed_at": now} for candle in deduped])
        .on_conflict_do_nothing(index_elements=[*key, "open_time"])
    )
    earliest, latest = deduped[0].open_time, deduped[-1].open_time
    prior = session.scalars(
        select(MarketCandle)
        .filter_by(**key)
        .where(MarketCandle.open_time < earliest)
        .order_by(MarketCandle.open_time.desc())
        .limit(detector.lookback)
    ).all()
    current = session.scalars(
        select(MarketCandle)
        .filter_by(**key)
        .where(MarketCandle.open_time >= earliest, MarketCandle.open_time <= latest)
        .order_by(MarketCandle.open_time.asc())
    ).all()
    found = {row.open_time: row for row in current}
    missing = [candle.open_time for candle in deduped if candle.open_time not in found]
    if missing:
        raise RuntimeError("Inserted candle is not readable")
    targets = [found[candle.open_time] for candle in deduped]
    done = set(
        session.scalars(
            select(Evaluation.candle_id).where(
                Evaluation.candle_id.in_([row.id for row in targets]),
                Evaluation.detector_key == detector.config_key,
            )
        )
    )
    history = [row.to_candle() for row in sorted([*prior, *current], key=lambda row: row.open_time)]
    for record in targets:
        if record.id in done:
            continue
        target = record.to_candle()
        preceding = [candle for candle in history if candle.open_time < target.open_time]
        decision = detector.evaluate(preceding, target)
        evaluation = Evaluation(
            candle_id=record.id,
            detector_key=detector.config_key,
            evaluated_at=clock() if clock else now,
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


def _require_market(candles, symbol, interval, provider: MarketDataProvider) -> None:
    if not candles:
        raise ValueError("No closed candles")
    if any(
        candle.symbol != symbol
        or candle.interval != interval
        or candle.provider != provider.name
        or candle.asset_class != provider.asset_class
        for candle in candles
    ):
        raise ValueError("Provider returned another market")


async def collect_markets(provider: MarketDataProvider, symbols, intervals, detector, now):
    """Fetch every market before the caller takes the database lock."""
    fetched: dict = {}
    errors = []
    for symbol in symbols:
        for interval in intervals:
            try:
                candles = await provider.fetch_candles(
                    symbol,
                    interval,
                    limit=detector.lookback + 2,
                    now=now,
                )
                _require_market(candles, symbol, interval, provider)
                fetched.setdefault(symbol, {})[interval] = candles
            except Exception as exc:
                errors.append({"symbol": symbol, "interval": interval, "error": type(exc).__name__})
    return fetched, errors


def _finish_run(sessions, run_id: int, status: str, errors: list[dict]) -> None:
    with sessions.begin() as session:
        run = session.get(ScanRun, run_id)
        if run is None or run.finished_at is not None:
            return
        run.status = status
        run.finished_at = datetime.now(UTC)
        run.error_count = len(errors)
        run.errors = errors


async def scan_once(
    sessions,
    provider: MarketDataProvider,
    symbols,
    intervals,
    detector,
    now=None,
    *,
    fetched=None,
    prefetch_errors=None,
):
    started_at = datetime.now(UTC)
    cutoff = now or started_at
    run_id = None
    errors: list[dict] = []
    status = "failed"
    try:
        with sessions.begin() as session:
            fail_orphaned_runs(session, started_at)
            run = ScanRun(
                started_at=started_at, provider=provider.name, status="running", errors=[]
            )
            session.add(run)
            session.flush()
            run_id = run.id
        if fetched is None:
            fetched, prefetch_errors = await collect_markets(
                provider, symbols, intervals, detector, cutoff
            )
        else:
            prefetch_errors = list(prefetch_errors or [])
        failed = {(item["symbol"], item["interval"]) for item in prefetch_errors}
        for item in prefetch_errors:
            errors.append(
                {"symbol": item["symbol"], "interval": item["interval"], "error": item["error"]}
            )
            logger.warning(
                "Scan failed for %s %s: %s", item["symbol"], item["interval"], item["error"]
            )
        total = 0
        for symbol in symbols:
            for interval in intervals:
                total += 1
                if (symbol, interval) in failed:
                    continue
                try:
                    candles = fetched[symbol][interval]
                    _require_market(candles, symbol, interval, provider)
                    with sessions.begin() as session:
                        ingest(
                            session,
                            candles,
                            detector,
                            datetime.now(UTC),
                            clock=lambda: datetime.now(UTC),
                        )
                except Exception as exc:
                    # Persist only class and market; URLs, passwords and payloads stay out of logs.
                    errors.append(
                        {"symbol": symbol, "interval": interval, "error": type(exc).__name__}
                    )
                    logger.warning(
                        "Scan failed for %s %s: %s", symbol, interval, type(exc).__name__
                    )
        status = "failed" if len(errors) == total else ("partial" if errors else "ok")
        return status
    finally:
        pending = sys.exc_info()[1]
        if run_id is not None:
            try:
                _finish_run(sessions, run_id, status, errors)
            except Exception:
                logger.error("Scan run %s could not be finalized", run_id)
                if pending is None:
                    raise
