"""Bounded real-provider research pass for the cross-asset Docker worker.

No trading or buy-alert generation. Each provider is opt-in and audited.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx

from scanner.providers.base import ProviderError
from scanner.providers.binance import BinanceSpotProvider
from scanner.stock_monitor.cross_asset import run_cross_asset
from scanner.stock_monitor.cross_asset_journal import append_cross_asset_run
from scanner.stock_monitor.crypto_schedule import choose_detail_symbols
from scanner.stock_monitor.sec_client_runner import run_with_sec_client
from scanner.stock_monitor.spot_signals import evaluate_spot_candidate
from scanner.stock_monitor.spot_snapshots import rank_snapshot
from scanner.stock_monitor.spot_universe import discover_spot_symbols
from scanner.stock_monitor.stock_universe import discover_sec_targets
from scanner.stock_monitor.worker import SecTarget


async def _crypto_pass(symbols: list[str], *, cutoff: datetime, root: Path | None = None) -> dict:
    discovery = None
    if os.getenv("CRYPTO_DISCOVER_UNIVERSE", "false").lower() == "true":
        async with httpx.AsyncClient() as client:
            discovery = await discover_spot_symbols(client)
        # Only replace the configured watchlist on a successful discovery pass.
        # A failed discover must not wipe CRYPTO_SYMBOLS into an empty market.
        if discovery.get("status") == "complete":
            symbols = discovery["symbols"]
        else:
            return {
                "status": "unavailable",
                "reason": "crypto_discovery_failed",
                "discovery": discovery,
                "configured_symbols_preserved": len(symbols),
            }
    if discovery and discovery.get("status") == "complete" and root is not None:
        snapshot_path = root / "spot-ticker-snapshot.json"
        previous = None
        try:
            if snapshot_path.exists():
                stored = json.loads(snapshot_path.read_text(encoding="utf-8"))
                previous = stored.get("ticker_snapshot")
        except (OSError, ValueError, TypeError, AttributeError):
            previous = None
        symbols, ranking_mode = rank_snapshot(
            symbols, discovery.get("ticker_snapshot", {}), previous
        )
        discovery["ranking_mode"] = ranking_mode
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot_payload = {
            "observed_at": cutoff.isoformat(),
            "ticker_snapshot": discovery.get("ticker_snapshot", {}),
        }
        tmp_path = snapshot_path.with_suffix(".json.tmp")
        tmp_path.write_text(json.dumps(snapshot_payload), encoding="utf-8")
        tmp_path.replace(snapshot_path)
    universe_count = len(symbols)
    if discovery:
        symbols, scan_mode = choose_detail_symbols(symbols, cutoff=cutoff)
    else:
        scan_mode = "configured_symbols"
    if not symbols:
        return {
            "status": "unavailable",
            "reason": "no_crypto_symbols_available",
            "discovery": discovery,
        }
    # Bound concurrent API calls. Detail coverage is the scheduled subset
    # (full Vienna hours, otherwise top-20 + rotating ≤60), not every eligible symbol.
    concurrency = int(os.getenv("CRYPTO_DETAIL_CONCURRENCY", "4"))
    if not 1 <= concurrency <= 8:
        raise ValueError("CRYPTO_DETAIL_CONCURRENCY must be 1..8")
    async with httpx.AsyncClient() as client:
        provider = BinanceSpotProvider(client)
        semaphore = asyncio.Semaphore(concurrency)

        async def inspect(symbol: str) -> dict:
            async with semaphore:
                try:
                    candles = await provider.fetch_candles(symbol, "5m", limit=22, now=cutoff)
                    signal = evaluate_spot_candidate(candles)
                    last_candle_at = candles[-1].close_time.isoformat() if candles else None
                    return {
                        "candidate": signal,
                        "symbol": symbol,
                        "status": "checked" if len(candles) >= 21 else "unavailable",
                        "closed_candles": len(candles),
                        "last_candle_at": last_candle_at,
                    }
                except (ValueError, httpx.HTTPError, ProviderError) as exc:
                    return {
                        "symbol": symbol,
                        "status": "unavailable",
                        "error_type": type(exc).__name__,
                    }

        outcomes = await asyncio.gather(*(inspect(symbol) for symbol in symbols))
    checked = sum(item["status"] == "checked" for item in outcomes)
    candidates = [item["symbol"] for item in outcomes if item.get("candidate", {}).get("qualified")]
    if checked == len(symbols):
        status = "complete"
    elif checked == 0:
        status = "unavailable"
    else:
        status = "partial"
    return {
        "status": status,
        "source": "binance_spot",
        "scan_mode": scan_mode,
        "universe_symbols": universe_count,
        "discovery": discovery,
        "requested_symbols": len(symbols),
        "checked_symbols": checked,
        "momentum_candidates": candidates,
        "outcomes": outcomes,
        "signal_status": "unvalidated_momentum_candidates_only",
        "bitpanda_listing_status": "not_checked",
    }


def _stock_pass(*, root: Path, targets: list[SecTarget], run_id: str, cutoff: datetime) -> dict:
    allow_network = os.getenv("SEC_ALLOW_NETWORK", "false").lower() == "true"
    if not targets and os.getenv("STOCK_AUTO_DISCOVERY", "false").lower() == "true":
        if not allow_network:
            return {"status": "unavailable", "reason": "sec_network_not_enabled"}
        try:
            targets = discover_sec_targets(
                user_agent=os.getenv("SEC_USER_AGENT", ""),
                slot=int(cutoff.timestamp() // 3600),
            )
        except (ValueError, httpx.HTTPError) as exc:
            return {
                "status": "unavailable",
                "reason": "sec_auto_discovery_failed",
                "error_type": type(exc).__name__,
            }
    if not targets:
        return {"status": "unavailable", "reason": "no_sec_targets_configured"}
    result = run_with_sec_client(
        cache_root=root / "sec-cache",
        journal_path=root / "sec-journal.jsonl",
        targets=targets,
        run_id=run_id,
        code_version="cross-asset-worker-v1",
        allow_network=allow_network,
        max_requests=int(os.getenv("SEC_MAX_REQUESTS", "0")),
        user_agent=os.getenv("SEC_USER_AGENT"),
        cutoff=cutoff,
        live_mode=True,
    )
    # Preserve complete / partial / unavailable from the SEC monitor.
    result["signal_status"] = "research_only_no_trade_validation"
    return result


async def run_once(*, root: Path, symbols: list[str], targets: list[SecTarget]) -> dict:
    cutoff = datetime.now(UTC)
    run_id = f"{cutoff:%Y%m%dT%H%M%S}-{uuid4().hex[:12]}"
    # SEC client is synchronous and must not block the async spot feed.
    stock_task = asyncio.create_task(
        asyncio.to_thread(_stock_pass, root=root, targets=targets, run_id=run_id, cutoff=cutoff)
    )
    crypto_task = asyncio.create_task(_crypto_pass(symbols, cutoff=cutoff, root=root))
    stock_result, crypto_result = await asyncio.gather(
        stock_task, crypto_task, return_exceptions=True
    )

    def outcome(result):
        if isinstance(result, BaseException):
            return {"status": "unavailable", "error_type": type(result).__name__}
        return result

    envelope = run_cross_asset(
        run_id=run_id,
        stock_scan=lambda: outcome(stock_result),
        crypto_scan=lambda: outcome(crypto_result),
    )
    append_cross_asset_run(root / "cross-asset-runs.jsonl", envelope)
    return envelope


def main() -> None:
    parser = argparse.ArgumentParser(description="Cross-asset research-only one-shot worker")
    parser.add_argument("--once", action="store_true", required=True)
    args = parser.parse_args()
    del args
    root = Path(os.getenv("CROSS_ASSET_DATA_DIR", "/data"))
    symbols = json.loads(os.getenv("CRYPTO_SYMBOLS", "[]"))
    target_rows = json.loads(os.getenv("SEC_TARGETS", "[]"))
    if not isinstance(symbols, list) or any(not isinstance(x, str) for x in symbols):
        raise ValueError("CRYPTO_SYMBOLS must be a JSON string array")
    if not isinstance(target_rows, list):
        raise ValueError("SEC_TARGETS must be a JSON array")
    targets = [SecTarget(cik=int(row["cik"]), symbol=str(row["symbol"])) for row in target_rows]
    if len(targets) > 10:
        raise ValueError("Maximum 10 SEC targets per pass")
    result = asyncio.run(run_once(root=root, symbols=symbols, targets=targets))
    print(
        json.dumps(
            {
                "run_id": result["run_id"],
                "status": result["status"],
                "stock_status": result["results"]["stock"]["status"],
                "crypto_status": result["results"]["crypto"]["status"],
                "order_execution": False,
            }
        )
    )


if __name__ == "__main__":
    main()
