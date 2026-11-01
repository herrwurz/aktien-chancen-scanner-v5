"""Configuration and isolated live-provider research worker tests."""

import asyncio
from datetime import UTC, datetime

from scanner.stock_monitor.cross_asset_worker import _crypto_pass, run_once


def test_empty_crypto_universe_is_unavailable():
    result = asyncio.run(_crypto_pass([], cutoff=datetime(2026, 11, 1, tzinfo=UTC)))
    assert result["status"] == "unavailable"


def test_offline_run_records_both_unavailable_sources(tmp_path):
    result = asyncio.run(run_once(root=tmp_path, symbols=[], targets=[]))
    assert result["status"] == "partial"
    assert result["results"]["stock"]["status"] == "unavailable"
    assert result["results"]["crypto"]["status"] == "unavailable"
    assert (tmp_path / "cross-asset-runs.jsonl").exists()
