import argparse
import asyncio
import logging
import signal

import httpx

from scanner.config import Settings
from scanner.db import create_db, create_sessions, worker_lock
from scanner.detector import VolumeDetector
from scanner.providers.binance import BinanceSpotProvider
from scanner.providers.fixture import FixtureProvider
from scanner.service import scan_once

logger = logging.getLogger(__name__)


async def run_worker(settings: Settings, once=False):
    engine = create_db(settings)
    sessions = create_sessions(engine)
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
                    with worker_lock(engine) as acquired:
                        if acquired:
                            status = await scan_once(
                                sessions, provider, settings.symbols, settings.intervals, detector
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
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    raise SystemExit(asyncio.run(run_worker(Settings(), once=args.once)))


if __name__ == "__main__":
    main()
