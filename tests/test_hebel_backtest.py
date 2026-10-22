from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from scanner.hebeltrader.backtest import Bar, Rules, simulate_stock

t = datetime(2026, 1, 1, tzinfo=UTC)


def bar(n, opening, high, low, close, **kwargs):
    return Bar(
        t + timedelta(days=n), *(Decimal(str(v)) for v in (opening, high, low, close)), **kwargs
    )


DEFAULT_RULES = Rules()


def run(*bars, rules=DEFAULT_RULES, **kwargs):
    return simulate_stock(
        available_at=t, bars=bars, target1=12, target2=15, stop1=8, rules=rules, **kwargs
    )


def test_first_stop():
    assert run(bar(1, 10, 11, 7, 9))["status"] == "stop_first"


def test_explicit_stop_change_and_partial_sale():
    r = run(
        bar(1, 10, 11, 9, 10), bar(2, 12, 13, 11, 12), bar(3, 9, 11, 8, 10), rules=Rules("entry")
    )
    assert r["status"] == "target1_first"
    assert r["exit_reason"] == "target1_then_stop"
    assert Decimal(r["modeled_return_pct"]) == Decimal("5")
    assert r["events"][0]["fraction"] == "0.5"
    assert r["realized_return_pct"] is None


def test_two_targets():
    assert run(bar(1, 10, 13, 9, 12), bar(2, 13, 16, 11, 15))["status"] == "target2_after_target1"


def test_intrabar_ambiguity():
    assert run(bar(1, 10, 13, 7, 10))["status"] == "ambiguous"
    assert run(bar(1, 10, 13, 9, 12), rules=Rules("entry"))["status"] == "ambiguous"


def test_open_target_recalculates_stop_before_intrabar():
    r = run(bar(1, 10, 11, 9, 10), bar(2, 13, 14, 9, 11), rules=Rules("entry"))
    assert r["exit_reason"] == "target1_then_stop"
    assert [e["phase"] for e in r["events"]] == ["open", "intrabar"]


def test_open_target_and_new_stop_target_collision():
    assert (
        run(bar(1, 10, 11, 9, 10), bar(2, 13, 16, 9, 11), rules=Rules("entry"))["status"]
        == "ambiguous"
    )


def test_availability_and_completed_horizon():
    assert run(bar(0, 10, 16, 7, 10), bar(1, 10, 11, 9, 10))["status"] == "not_triggered"
    assert (
        run(bar(1, 10, 16, 7, 10, end_at=t + timedelta(days=2)), horizon=t + timedelta(days=1))[
            "status"
        ]
        == "unknown"
    )


def test_missing_inputs_and_no_implicit_stop2():
    assert run()["status"] == "unknown"
    assert run(bar(1, 10, 11, 9, 10), rules=None)["reason"] == "missing_documented_rules"
    assert run(bar(1, 10, 11, 9, 10), rules=Rules("stop2"))["status"] == "unknown"
    assert run(bar(1, 10, 11, 9, 10), stop2=11)["status"] == "not_triggered"


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -1])
def test_invalid_prices(bad):
    with pytest.raises(ValueError):
        bar(1, 10, bad, 7, 10)


def test_invalid_metadata():
    with pytest.raises(ValueError):
        bar(1, 10, 11, 9, 10, volume=Decimal("NaN"))
    with pytest.raises(ValueError):
        bar(1, 10, 11, 9, 10, end_at=t)


def test_gap_stop():
    r = run(bar(1, 10, 11, 9, 10), bar(2, 7, 9, 6, 8))
    assert r["status"] == "stop_first"
    assert r["events"][-1]["at_price"] == "7"


def test_expiry_is_explicit_and_session_count_includes_entry():
    bars = [bar(n, 10, 11, 9, 10) for n in range(1, 25)]
    assert run(*bars)["status"] == "not_triggered"
    r = run(*bars, rules=Rules(close_after_days=20, close_unit="trading_sessions"))
    assert r["status"] == "expired"
    assert r["events"][-1]["at"] == (t + timedelta(days=20)).isoformat()
    r = run(*bars, rules=Rules(close_after_days=20, close_unit="calendar_days"))
    assert r["status"] == "expired"
    assert r["events"][-1]["at"] == (t + timedelta(days=21)).isoformat()
    assert (
        run(*bars[:5], rules=Rules(close_after_days=20, close_unit="calendar_days"))["status"]
        == "not_triggered"
    )


def test_nonfinite_levels_and_duplicate_bars():
    b = bar(1, 10, 11, 9, 10)
    assert run(b, stop2=Decimal("NaN"), rules=Rules("stop2"))["status"] == "unknown"
    assert run(b, b)["reason"] == "duplicate_bar_timestamps"


def test_explicit_stop2_changes_only_after_target1():
    r = run(
        bar(1, 10, 11, 9, 10),
        bar(2, 12, 13, 12, 12),
        bar(3, 10, 11, 9, 10),
        rules=Rules("stop2"),
        stop2=11,
    )
    assert r["exit_reason"] == "target1_then_stop"
    assert r["events"][-1]["at_price"] == "10"


def test_unknown_for_invalid_rules_and_times():
    b = bar(1, 10, 11, 9, 10)
    assert run(b, rules=Rules("invented"))["status"] == "unknown"
    assert run(b, rules=Rules(close_after_days=20))["status"] == "unknown"
    assert (
        run(b, rules=Rules(close_after_days=True, close_unit="calendar_days"))["status"]
        == "unknown"
    )
    assert run(b, horizon=t.replace(tzinfo=None))["reason"] == "invalid_horizon"
    with pytest.raises(ValueError):
        Bar(t.replace(tzinfo=None), Decimal(10), Decimal(11), Decimal(9), Decimal(10))
    result = simulate_stock(
        available_at=t,
        bars=[b],
        target1=Decimal("NaN"),
        target2=15,
        stop1=8,
        rules=Rules(),
    )
    assert result["reason"] == "missing_or_invalid_targets"


def test_calendar_weekend_uses_last_known_close_and_requires_coverage():
    bars = [bar(1, 10, 11, 9, 10), bar(2, 10, 11, 9, 11), bar(5, 10, 11, 9, 10)]
    rules = Rules(close_after_days=2, close_unit="calendar_days")
    assert run(*bars[:2], rules=rules)["status"] == "not_triggered"
    r = run(*bars, rules=rules)
    assert r["status"] == "expired"
    assert r["events"][-1]["at"] == (t + timedelta(days=2)).isoformat()
    assert Decimal(r["modeled_return_pct"]) == 10


def test_intrabar_event_has_interval_precision():
    r = run(bar(1, 10, 11, 7, 9, end_at=t + timedelta(days=1, hours=8)))
    assert r["events"][0]["time_precision"] == "bar_interval"
    assert r["events"][0]["interval_end"] == (t + timedelta(days=1, hours=8)).isoformat()
    assert r["realized_return_pct"] is None


def test_collision_has_interval_audit_without_modeled_return():
    b = bar(1, 10, 13, 7, 10, end_at=t + timedelta(days=1, hours=8))
    r = run(b)
    assert r["status"] == "ambiguous"
    assert r["modeled_return_pct"] is None
    collision = r["events"][-1]
    assert collision["event"] == "ambiguous_intrabar"
    assert collision["at"] == b.at.isoformat()
    assert collision["interval_start"] == b.at.isoformat()
    assert collision["interval_end"] == b.end_at.isoformat()
    assert collision["time_precision"] == "bar_interval"
    assert collision["fraction"] is None
    assert "at_price" not in collision
