from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from scanner.detector import VolumeDetector
from scanner.domain import Candle

START = datetime(2026, 1, 1, tzinfo=UTC)


def candle(index=0, volume="10", quote_volume="100000", **overrides):
    values = dict(
        provider="fixture",
        asset_class="crypto",
        symbol="BTCUSDT",
        interval="5m",
        open_time=START + timedelta(minutes=index * 5),
        close_time=START + timedelta(minutes=(index + 1) * 5),
        open="100",
        high="110",
        low="90",
        close="105",
        volume=volume,
        quote_volume=quote_volume,
    )
    return Candle(**(values | overrides))


def test_spike_uses_previous_volumes_only():
    result = VolumeDetector(lookback=3).evaluate([candle(i) for i in range(3)], candle(3, "30"))
    assert result.is_signal
    assert result.ratio == Decimal("3")
    assert result.baseline_volume == Decimal("10")


@pytest.mark.parametrize(
    ("history", "target", "reason"),
    [
        ([candle(0)], candle(1), "insufficient_history"),
        ([candle(i) for i in (0, 1, 3)], candle(4, "40"), "history_gap"),
        ([candle(i, "0") for i in range(3)], candle(3, "40"), "zero_baseline"),
        ([candle(i) for i in range(3)], candle(3, "29"), "normal_volume"),
        ([candle(i) for i in range(3)], candle(3, "40", "99999"), "low_quote_volume"),
    ],
)
def test_rejections_are_explained(history, target, reason):
    result = VolumeDetector(lookback=3).evaluate(history, target)
    assert not result.is_signal
    assert result.reason == reason


def test_future_and_other_market_data_do_not_affect_baseline():
    history = [candle(i) for i in range(3)] + [
        candle(4, "9999"),
        candle(2, "999", symbol="ETHUSDT"),
    ]
    assert VolumeDetector(lookback=3).evaluate(history, candle(3, "30")).ratio == 3


@pytest.mark.parametrize(
    "overrides",
    [
        {"volume": "-1"},
        {"volume": "NaN"},
        {"high": "99"},
        {"close_time": START},
        {"open_time": START.replace(tzinfo=None)},
        {"interval": "1m"},
        {"quote_volume": "Infinity"},
    ],
)
def test_invalid_candles_rejected(overrides):
    with pytest.raises(ValueError):
        candle(**overrides)
