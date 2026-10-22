"""Daily stock model; a completed-close decision can only fill at a later open."""

from decimal import Decimal

from .backtest import _aware, _decimal

VERSION = "hebel-stock-ohlc-v1.6"


def number(value):
    return format(value.normalize(), "f")


def simulate_v16(*, available_at, bars, target1, target2, stop1, stop2, horizon, rules):
    result = dict(
        method=VERSION,
        status="unknown",
        reason=None,
        events=[],
        fully_evaluable=False,
        modeled_entry=None,
        modeled_return_pct=None,
        conservative_return_pct=None,
        realized_return_pct=None,
        instrument="stock",
        training_eligible=False,
        execution="hypothetical_gross_prices; not observed trades",
        ambiguity_policy="stop_first_lower_bound; exclude from fully evaluable outcomes",
        metrics={},
    )

    def unknown(reason):
        result["reason"] = reason
        return result

    if (
        not _aware(available_at)
        or horizon is not None
        and (not _aware(horizon) or horizon < available_at)
    ):
        return unknown("invalid_window")
    if (
        rules.after_target1 not in {"entry", "unchanged", "stop2", "target1"}
        or _decimal(rules.partial_fraction) != Decimal("0.5")
        or type(rules.loss_after_days) is not int
        or rules.loss_after_days <= 0
        or rules.loss_unit not in {"calendar_days", "trading_sessions"}
        or rules.loss_basis not in {"total_position", "remaining_position"}
        or rules.close_after_days is not None
    ):
        return unknown("incomplete_or_invalid_v16_rules")
    t1, t2, s1, s2 = map(_decimal, (target1, target2, stop1, stop2))
    if any(v is None for v in (t1, t2, s1)) or not 0 < s1 < t1 < t2:
        return unknown("invalid_price_levels")
    if rules.after_target1 == "stop2" and (s2 is None or not 0 < s2 < t1):
        return unknown("invalid_stop2")
    eligible = [
        b
        for b in bars
        if b.at > available_at and (horizon is None or (b.end_at or b.at) <= horizon)
    ]
    eligible.sort(key=lambda b: b.at)
    if not eligible:
        return unknown("no_complete_post_publication_session")
    if (
        any(b.end_at is None or b.end_at <= b.at for b in eligible)
        or len({b.at.date() for b in eligible}) != len(eligible)
        or any(a.end_at > b.at for a, b in zip(eligible, eligible[1:], strict=False))
    ):
        return unknown("invalid_daily_sessions")
    entry = eligible[0].open
    if not s1 < entry < t1:
        return unknown("entry_outside_stop_target_range")
    cash, qty = Decimal(0), Decimal(1)
    first = False
    pending = None
    peak = entry
    drawdown = Decimal(0)
    result["modeled_entry"] = number(entry)
    metrics = result["metrics"]
    metrics.update(
        initial_crv_target1=number((t1 - entry) / (entry - s1)),
        initial_crv_target2=number((t2 - entry) / (entry - s1)),
        drawdown_method=(
            "modeled equity at completed closes and known fills; intraday maximum unknown"
        ),
        max_intraday_drawdown_pct=None,
    )

    def observe(equity):
        nonlocal peak, drawdown
        peak = max(peak, equity)
        drawdown = max(drawdown, 100 * (peak - equity) / peak)
        metrics["observed_equity_max_drawdown_pct"] = number(drawdown)

    def stop():
        if not first or rules.after_target1 == "unchanged":
            return s1
        return {"entry": entry, "stop2": s2, "target1": t1}[rules.after_target1]

    def sell(kind, b, price, amount, index, phase="intrabar", signal=None):
        nonlocal cash, qty
        cash += amount * price
        qty -= amount
        at = b.at if phase != "close" else b.end_at
        event = dict(
            event=kind,
            at=at.isoformat(),
            at_price=number(price),
            fraction=number(amount),
            phase=phase,
            interval_start=b.at.isoformat(),
            interval_end=b.end_at.isoformat(),
            time_precision="bar_interval" if phase == "intrabar" else "observed",
            elapsed_calendar_days=(at.date() - eligible[0].at.date()).days,
            session_number=index + 1,
            elapsed_seconds_lower=str((at - eligible[0].at).total_seconds()),
            elapsed_seconds_upper=str(
                ((b.end_at if phase == "intrabar" else at) - eligible[0].at).total_seconds()
            ),
        )
        if signal:
            event["signal_at"] = signal.isoformat()
        result["events"].append(event)
        metrics[kind + "_modeled"] = True
        if qty == 0:
            observe(cash)

    def finish(reason, ambiguous=False):
        result["reason"] = result["exit_reason"] = reason
        value = number(100 * (cash - entry) / entry)
        result["status"] = "ambiguous" if ambiguous else "closed"
        result["fully_evaluable"] = not ambiguous
        result["conservative_return_pct" if ambiguous else "modeled_return_pct"] = value
        return result

    for index, b in enumerate(eligible):
        if b.open <= stop():
            sell("stop", b, b.open, qty, index, "open")
            return finish("stop_gap")
        if pending is not None:
            sell("conditional_loss_exit", b, b.open, qty, index, "open", pending)
            return finish("conditional_loss_exit")
        if not first and b.open >= t1:
            sell("target1", b, t1, Decimal("0.5"), index, "open")
            first = True
            if b.open <= stop():
                sell("stop", b, b.open, qty, index, "open")
                return finish("new_stop_at_open")
        if first and b.open >= t2:
            sell("target2", b, t2, qty, index, "open")
            return finish("target2")
        active = stop()
        target = t2 if first else t1
        if b.low <= active:
            collision = b.high >= target
            sell("stop", b, active, qty, index)
            return finish("intrabar_stop_and_target" if collision else "stop", collision)
        if not first and b.high >= t1:
            sell("target1", b, t1, Decimal("0.5"), index)
            first = True
            if b.low <= stop():
                sell("stop", b, stop(), qty, index)
                return finish("intrabar_target1_and_new_stop", True)
        if first and b.high >= t2:
            sell("target2", b, t2, qty, index)
            return finish("target2")
        equity = cash + qty * b.close
        observe(equity)
        age = (
            (b.end_at.date() - eligible[0].at.date()).days
            if rules.loss_unit == "calendar_days"
            else index + 1
        )
        losing = equity < entry if rules.loss_basis == "total_position" else b.close < entry
        if age >= rules.loss_after_days and losing:
            pending = b.end_at
    result.update(
        status="open",
        reason="pending_exit_no_next_session" if pending else "observation_window_ended",
    )
    return result
