from datetime import UTC, datetime, timedelta

from scanner.hebeltrader.backtest import Bar, Rules, simulate_stock

START = datetime(2025, 1, 1, 9, tzinfo=UTC)


def bar(day, o=100, h=105, low=95, c=100):
    at = START + timedelta(days=day)
    return Bar(at, o, h, low, c, end_at=at + timedelta(hours=8))


def run(bars, **kwargs):
    rule = Rules(
        version="1.6",
        after_target1="entry",
        loss_after_days=2,
        loss_unit="trading_sessions",
        loss_basis="total_position",
        **kwargs,
    )
    return simulate_stock(
        available_at=START - timedelta(days=1),
        bars=bars,
        target1=120,
        target2=140,
        stop1=80,
        rules=rule,
    )


def test_profit_after_threshold_never_becomes_unconditional_exit():
    result = run([bar(0), bar(1, c=103), bar(2, c=104)])
    assert result["status"] == "open"
    assert not any(e["event"] == "conditional_loss_exit" for e in result["events"])


def test_loss_signal_at_close_executes_only_at_next_open_even_after_gap_recovery():
    result = run([bar(0), bar(1, c=99), bar(2, o=110, h=115, low=108, c=112)])
    event = result["events"][-1]
    assert event["event"] == "conditional_loss_exit"
    assert event["phase"] == "open" and event["at_price"] == "110"
    assert event["signal_at"] == bar(1).end_at.isoformat()
    assert result["fully_evaluable"] is True
    assert result["modeled_return_pct"] == "10"


def test_last_loss_close_does_not_invent_next_open_or_fill_at_close():
    result = run([bar(0), bar(1, c=99)])
    assert result["reason"] == "pending_exit_no_next_session"
    assert result["modeled_return_pct"] is None


def test_calendar_and_session_age_differ_across_weekend():
    bars = [bar(0), bar(4, c=99), bar(5)]
    calendar = simulate_stock(
        available_at=START - timedelta(days=1),
        bars=bars,
        target1=120,
        target2=140,
        stop1=80,
        rules=Rules(
            version="1.6", loss_after_days=3, loss_unit="calendar_days", loss_basis="total_position"
        ),
    )
    sessions = run(
        bars,
    )
    assert calendar["events"][-1]["event"] == "conditional_loss_exit"
    assert sessions["events"][-1]["event"] == "conditional_loss_exit"
    three = simulate_stock(
        available_at=START - timedelta(days=1),
        bars=bars,
        target1=120,
        target2=140,
        stop1=80,
        rules=Rules(
            version="1.6",
            loss_after_days=3,
            loss_unit="trading_sessions",
            loss_basis="total_position",
        ),
    )
    assert three["status"] == "open"


def test_partial_then_target2_and_weighted_return():
    result = run(
        [bar(0), bar(1, o=110, h=125, low=105, c=121), bar(2, o=130, h=145, low=125, c=142)]
    )
    assert [e["event"] for e in result["events"]] == ["target1", "target2"]
    assert result["modeled_return_pct"] == "30"
    assert result["metrics"]["initial_crv_target1"] == "1"
    assert result["metrics"]["initial_crv_target2"] == "2"


def test_collision_returns_only_pessimistic_bound_not_confirmed_success():
    result = run([bar(0, h=145, low=70, c=100)])
    assert result["status"] == "ambiguous"
    assert result["conservative_return_pct"] == "-20"
    assert result["modeled_return_pct"] is None
    assert result["fully_evaluable"] is False


def test_unfinished_or_future_bars_cannot_change_result():
    bars = [bar(0), bar(1, c=99)]
    cutoff = bars[-1].end_at
    rule = Rules(
        version="1.6", loss_after_days=2, loss_unit="trading_sessions", loss_basis="total_position"
    )
    a = simulate_stock(
        available_at=START - timedelta(days=1),
        bars=bars,
        target1=120,
        target2=140,
        stop1=80,
        rules=rule,
        horizon=cutoff,
    )
    b = simulate_stock(
        available_at=START - timedelta(days=1),
        bars=bars + [bar(2, o=150, h=160, low=140, c=155)],
        target1=120,
        target2=140,
        stop1=80,
        rules=rule,
        horizon=cutoff,
    )
    assert a == b


def test_exact_twentieth_session_signals_and_twenty_first_fills():
    result = simulate_stock(
        available_at=START - timedelta(days=1),
        bars=[bar(i, c=99) for i in range(21)],
        target1=120,
        target2=140,
        stop1=80,
        rules=Rules(
            version="1.6",
            loss_after_days=20,
            loss_unit="trading_sessions",
            loss_basis="total_position",
        ),
    )
    event = result["events"][-1]
    assert event["session_number"] == 21
    assert event["signal_at"] == bar(19).end_at.isoformat()


def test_profit_on_whole_position_and_loss_on_remaining_half_are_distinct():
    bars = [bar(0, h=125, low=95, c=121), bar(1, c=99), bar(2)]
    outcomes = {}
    for basis in ("total_position", "remaining_position"):
        outcomes[basis] = simulate_stock(
            available_at=START - timedelta(days=1),
            bars=bars,
            target1=120,
            target2=140,
            stop1=80,
            rules=Rules(
                version="1.6",
                after_target1="unchanged",
                loss_after_days=2,
                loss_unit="trading_sessions",
                loss_basis=basis,
            ),
        )
    assert outcomes["total_position"]["status"] == "open"
    assert outcomes["remaining_position"]["exit_reason"] == "conditional_loss_exit"


def test_new_stop_collision_and_worse_gap_are_not_optimistic():
    ambiguous = run([bar(0, h=125, low=95, c=121)])
    assert ambiguous["status"] == "ambiguous"
    assert ambiguous["conservative_return_pct"] == "10"
    gap = run([bar(0), bar(1, o=70, h=75, low=65, c=71)])
    assert gap["modeled_return_pct"] == "-30"
    assert gap["metrics"]["observed_equity_max_drawdown_pct"] == "30"
    assert gap["metrics"]["max_intraday_drawdown_pct"] is None
