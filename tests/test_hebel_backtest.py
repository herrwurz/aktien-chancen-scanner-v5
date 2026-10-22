from datetime import datetime, timezone, timedelta
from decimal import Decimal
from scanner.hebeltrader.backtest import Bar, simulate_stock

t = datetime(2026, 1, 1, tzinfo=timezone.utc)
def bar(n,o,h,l,c):
    return Bar(t+timedelta(days=n), *(Decimal(str(v)) for v in (o,h,l,c)))
def run(*bars):
    return simulate_stock(available_at=t, bars=bars, target1=12, target2=15, stop1=8)
def test_first_stop():
    r=run(bar(1,10,11,7,9))
    assert r["status"]=="stop_first"
def test_target_then_stop():
    r=run(bar(1,10,13,9,12),bar(2,12,13,9,10))
    assert r["status"]=="target1_then_stop"
def test_two_targets():
    r=run(bar(1,10,13,9,12),bar(2,13,16,11,15))
    assert r["status"]=="target2_after_target1"
def test_intrabar_ambiguity():
    assert run(bar(1,10,13,7,10))["status"]=="ambiguous"
def test_before_available_ignored():
    assert run(bar(0,10,16,7,10),bar(1,10,11,9,10))["status"]=="not_triggered"
def test_missing_bars():
    assert run()["status"]=="unknown"
def test_invalid_ohlc():
    import pytest
    with pytest.raises(ValueError):
        bar(1,10,9,7,10)
def test_gap_stop():
    r=run(bar(1,10,11,9,10),bar(2,7,9,6,8))
    assert r["status"]=="stop_first"
def test_no_derivative_return_claim():
    assert run(bar(1,10,11,9,10))["caveat"].startswith("OHLC")
