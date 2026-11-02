"""SEC ticker mapping tests without live network requests."""

import pytest

from scanner.stock_monitor.stock_universe import select_targets


def test_rotating_watchlist_maps_official_ciks():
    rows = {
        "0": {"ticker": "AAPL", "cik_str": 320193},
        "1": {"ticker": "MSFT", "cik_str": 789019},
        "2": {"ticker": "NVDA", "cik_str": 1045810},
    }
    targets = select_targets(rows, slot=1, limit=2)
    assert [item.symbol for item in targets] == ["NVDA", "AAPL"]
    assert [item.cik for item in targets] == [1045810, 320193]


def test_empty_sec_mapping_fails_closed():
    with pytest.raises(ValueError, match="No configured"):
        select_targets({}, slot=0)
