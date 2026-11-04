import argparse
import asyncio
import logging
import signal
from datetime import UTC, datetime

import httpx

from scanner.config import Settings
from scanner.db import create_db, create_sessions, worker_lock
from scanner.detector import VolumeDetector
from scanner.providers.binance import BinanceSpotProvider
from scanner.providers.fixture import FixtureProvider
from scanner.service import collect_markets, scan_once

logger = logging.getLogger(__name__)


async def run_worker(settings: Settings, once=False):
    engine = create_db(settings)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    detector = VolumeDetector(
        settings.volume_lookback, settings.volume_threshold, settings.min_quote_volume
    )
    try:
        async with httpx.AsyncClient() as client:
            provider = (
                FixtureProvider() if settings.provider == "fixture" else BinanceSpotProvider(client)
            )
            while not stop.is_set():
                try:
                    fetched, prefetch_errors = await collect_markets(
                        provider,
                        settings.symbols,
                        settings.intervals,
                        detector,
                        datetime.now(UTC),
                    )
                    if stop.is_set():
                        break
                    with worker_lock(engine) as acquired:
                        if acquired:
                            # New checkout each cycle: the advisory lock lives on this connection.
                            sessions = create_sessions(acquired, require_lock=True)
                            status = await scan_once(
                                sessions,
                                provider,
                                settings.symbols,
                                settings.intervals,
                                detector,
                                fetched=fetched,
                                prefetch_errors=prefetch_errors,
                            )
                            logger.info("Scan finished: %s", status)
                            if once:
                                return 0 if status == "ok" else 1
                        else:
                            logger.info("Another worker owns the scan lock")
                            if once:
                                return 1
                except Exception as exc:
                    logger.error("Worker cycle failed: %s", type(exc).__name__)
                    if once:
                        return 1
                try:
                    await asyncio.wait_for(stop.wait(), timeout=settings.scan_seconds)
                except TimeoutError:
                    pass
    finally:
        engine.dispose()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.remove_signal_handler(sig)
    return 0


def main():
    parser = argparse.ArgumentParser(description="Read-only market scanner worker")
    parser.add_argument("--once", action="store_true", help="One scan, nonzero exit on failure")
    parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logger.warning(
        "Projekt archiviert. Der Worker startet keinen Scan und beendet sich ohne Netzabruf."
    )
    raise SystemExit(0)


if __name__ == "__main__":
    main()
