"""Configuration and isolated live-provider research worker tests."""

import asyncio
from datetime import UTC, datetime

from scanner.stock_monitor.cross_asset_worker import _crypto_pass, run_once


def test_empty_crypto_universe_is_unavailable():
    result = asyncio.run(_crypto_pass([], cutoff=datetime(2026, 11, 1, tzinfo=UTC)))
    assert result["status"] == "unavailable"


def test_offline_run_records_both_unavailable_sources(tmp_path):
    result = asyncio.run(run_once(root=tmp_path, symbols=[], targets=[]))
    assert result["status"] == "unavailable"
    assert result["results"]["stock"]["status"] == "unavailable"
    assert result["results"]["crypto"]["status"] == "unavailable"
    assert (tmp_path / "cross-asset-runs.jsonl").exists()


def test_failed_discovery_does_not_wipe_configured_symbols(monkeypatch):
    async def boom(_client):
        return {"status": "unavailable", "error_type": "HTTPError", "symbols": []}

    monkeypatch.setenv("CRYPTO_DISCOVER_UNIVERSE", "true")
    monkeypatch.setattr("scanner.stock_monitor.cross_asset_worker.discover_spot_symbols", boom)
    result = asyncio.run(_crypto_pass(["BTCUSDT"], cutoff=datetime(2026, 11, 1, tzinfo=UTC)))
    assert result["status"] == "unavailable"
    assert result["reason"] == "crypto_discovery_failed"
    assert result["configured_symbols_preserved"] == 1
