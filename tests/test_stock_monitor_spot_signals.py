"""Offline regression tests for conservative spot candidate detection."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from scanner.domain import Candle
from scanner.stock_monitor.spot_signals import evaluate_spot_candidate


def bars(*, spike: bool = False):
    start = datetime(2026, 11, 1, tzinfo=UTC)
    result = []
    for i in range(21):
        last = i == 20
        price = Decimal("102") if last and spike else Decimal("100")
        result.append(
            Candle(
                provider="binance_spot",
                asset_class="crypto",
                symbol="BTCUSDT",
                interval="5m",
                open_time=start + timedelta(minutes=5 * i),
                close_time=start + timedelta(minutes=5 * (i + 1)),
                open=price,
                high=price,
                low=price,
                close=price,
                volume=Decimal("2000") if last and spike else Decimal("100"),
                quote_volume=Decimal("200000") if last and spike else Decimal("10000"),
            )
        )
    return result


def test_qualifies_strong_spot_move():
    result = evaluate_spot_candidate(bars(spike=True))
    assert result["qualified"] is True
    assert result["requires_listing_and_spread_validation"] is True


def test_rejects_flat_market():
    assert evaluate_spot_candidate(bars())["qualified"] is False


def test_rejects_discontinuous_history():
    sample = bars(spike=True)
    sample.pop(5)
    assert evaluate_spot_candidate(sample)["reason"] == "insufficient_history"


def test_rejects_missing_history():
    assert evaluate_spot_candidate([])["reason"] == "insufficient_history"


def test_spike_reports_early_momentum_evidence():
    result = evaluate_spot_candidate(bars(spike=True))
    assert result["return_5m_pct"] == 2.0
    assert result["return_60m_pct"] == 2.0
    assert result["breakout_above_prior_20_bar_high_pct"] == 2.0
    assert result["overheated"] is False


def test_rejects_overheated_spike():
    sample = bars(spike=True)
    last = sample[-1]
    sample[-1] = last.model_copy(update={
        "open": Decimal("120"),
        "high": Decimal("120"),
        "low": Decimal("120"),
        "close": Decimal("120"),
    })
    result = evaluate_spot_candidate(sample)
    assert result["qualified"] is False
    assert result["reason"] == "overheated_move"
