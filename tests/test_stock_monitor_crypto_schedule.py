"""Offline tests for Vienna-local scan schedule and rotation."""

from datetime import UTC, datetime

import pytest

from scanner.stock_monitor.crypto_schedule import choose_detail_symbols


@pytest.mark.parametrize(
    ("cutoff", "expected"),
    [
        (datetime(2026, 11, 2, 6, tzinfo=UTC), "full"),
        (datetime(2026, 11, 2, 18, tzinfo=UTC), "full"),
        (datetime(2026, 7, 2, 5, tzinfo=UTC), "full"),
        (datetime(2026, 7, 2, 17, tzinfo=UTC), "full"),
        (datetime(2026, 11, 2, 12, tzinfo=UTC), "hourly_priority_rotation"),
    ],
)
def test_schedule_respects_vienna_daylight_saving(cutoff, expected):
    symbols = [f"COIN{i}USDT" for i in range(552)]
    selected, mode = choose_detail_symbols(symbols, cutoff=cutoff)
    assert mode == expected
    assert len(selected) == (552 if expected == "full" else 80)


def test_rotation_advances_between_hours():
    symbols = [f"COIN{i}USDT" for i in range(552)]
    first, _ = choose_detail_symbols(symbols, cutoff=datetime(2026, 11, 2, 12, tzinfo=UTC))
    second, _ = choose_detail_symbols(symbols, cutoff=datetime(2026, 11, 2, 13, tzinfo=UTC))
    assert first[:20] == second[:20]
    assert set(first[20:]).isdisjoint(second[20:])


def test_schedule_requires_aware_cutoff():
    with pytest.raises(ValueError, match="timezone-aware"):
        choose_detail_symbols(["BTCUSDT"], cutoff=datetime(2026, 11, 2, 12))
