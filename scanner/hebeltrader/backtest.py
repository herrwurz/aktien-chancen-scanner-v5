"""Conservative stock OHLC modeling; never evidence of executed trades."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

VERSION = "hebel-stock-ohlc-v1.2"
UNKNOWN = "unknown"


def _aware(value):
    return (
        isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None
    )


def _decimal(value):
    try:
        number = Decimal(str(value))
        return number if number.is_finite() else None
    except (InvalidOperation, ValueError, TypeError):
        return None


@dataclass(frozen=True)
class Bar:
    """Timestamp is session OPEN; end_at marks the completed interval."""

    at: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    end_at: datetime | None = None
    volume: Decimal | None = None

    def __post_init__(self):
        if not _aware(self.at) or (
            self.end_at is not None and (not _aware(self.end_at) or self.end_at < self.at)
        ):
            raise ValueError("invalid bar interval/timezone")
        values = [_decimal(v) for v in (self.open, self.high, self.low, self.close)]
        if any(v is None for v in values):
            raise ValueError("nonfinite OHLC")
        opening, high, low, close = values
        if not 0 < low <= min(opening, close) <= max(opening, close) <= high:
            raise ValueError("invalid OHLC bar")
        for field, value in zip(("open", "high", "low", "close"), values, strict=True):
            object.__setattr__(self, field, value)
        if self.volume is not None:
            volume = _decimal(self.volume)
            if volume is None or volume < 0:
                raise ValueError("invalid volume")
            object.__setattr__(self, "volume", volume)


@dataclass(frozen=True)
class Rules:
    after_target1: str = "unchanged"
    close_after_days: int | None = None
    close_unit: str | None = None
    version: str = "1.2"
    partial_fraction: Decimal = Decimal("0.5")
    loss_after_days: int | None = None
    loss_unit: str | None = None
    loss_basis: str | None = None


def simulate_stock(
    *,
    available_at: datetime,
    bars: Iterable[Bar],
    target1,
    target2,
    stop1,
    stop2=None,
    horizon=None,
    rules: Rules | None = None,
):
    """Sell half at target1. Expiry sessions count entry as day one.

    Calendar expiry uses the last session opening on/before entry+N days,
    only once completed coverage reaches that deadline. Its known close is
    used. No implicit expiry. Missing end_at is a synthetic instantaneous bar.
    Intrabar event timestamps identify intervals, never exact fill times.
    """
    if isinstance(rules, Rules) and rules.version == "1.6":
        from .backtest_v16 import simulate_v16

        return simulate_v16(
            available_at=available_at,
            bars=bars,
            target1=target1,
            target2=target2,
            stop1=stop1,
            stop2=stop2,
            horizon=horizon,
            rules=rules,
        )
    result = dict(
        method=VERSION,
        status=UNKNOWN,
        events=[],
        realized_return_pct=None,
        modeled_return_pct=None,
        modeled_entry=None,
        costs="unknown",
        reason=None,
        exit_reason=None,
        instrument="stock",
        caveat="OHLC indicative; no executed trades",
        expiry_semantics=(
            "trading_sessions: entry session is 1; calendar_days: last session opening "
            "on/before entry+N days, requiring completed coverage through deadline"
        ),
    )

    def unknown(reason):
        result["reason"] = reason
        return result

    if rules is None:
        return unknown("missing_documented_rules")
    if not isinstance(rules, Rules) or rules.after_target1 not in {"unchanged", "entry", "stop2"}:
        return unknown("invalid_rules")
    days = rules.close_after_days
    if (days is None) != (rules.close_unit is None) or (
        days is not None
        and (
            type(days) is not int
            or days <= 0
            or rules.close_unit not in {"calendar_days", "trading_sessions"}
        )
    ):
        return unknown("invalid_expiry_rules")
    if not _aware(available_at):
        return unknown("missing_availability_timezone")
    if horizon is not None and (not _aware(horizon) or horizon < available_at):
        return unknown("invalid_horizon")
    t1, t2, s1, s2 = map(_decimal, (target1, target2, stop1, stop2))
    if any(v is None for v in (t1, t2, s1)) or not 0 < s1 < t1 < t2:
        return unknown("missing_or_invalid_targets")
    if rules.after_target1 == "stop2" and (s2 is None or not 0 < s2 < t1):
        return unknown("missing_or_invalid_stop2")
    ordered = sorted(bars, key=lambda b: b.at)
    if len({b.at for b in ordered}) != len(ordered):
        return unknown("duplicate_bar_timestamps")
    if any((a.end_at or a.at) > b.at for a, b in zip(ordered, ordered[1:], strict=False)):
        return unknown("overlapping_bar_intervals")
    ordered = [
        b
        for b in ordered
        if b.at > available_at and (horizon is None or (b.end_at or b.at) <= horizon)
    ]
    if not ordered:
        return unknown("no_post_publication_bars")
    entry = ordered[0].open
    result["modeled_entry"] = result["indicative_entry"] = str(entry)
    if not s1 < entry < t1:
        return unknown("entry_outside_stop_target_range")
    expiry_index = None
    if days is not None:
        if rules.close_unit == "trading_sessions":
            # Multiple intervals on a date count as one session.
            session_dates = list(dict.fromkeys(b.at.date() for b in ordered))
            if len(session_dates) >= days:
                expiry_index = max(
                    i for i, b in enumerate(ordered) if b.at.date() == session_dates[days - 1]
                )
        else:
            deadline = ordered[0].at + timedelta(days=days)
            if (ordered[-1].end_at or ordered[-1].at) >= deadline:
                expiry_index = max(i for i, b in enumerate(ordered) if b.at <= deadline)
    first_exit = None

    def active_stop():
        if first_exit is None or rules.after_target1 == "unchanged":
            return s1
        return entry if rules.after_target1 == "entry" else s2

    def event(name, b, price, phase, fraction):
        result["events"].append(
            dict(
                event=name,
                at=(b.end_at if phase == "close" and b.end_at else b.at).isoformat(),
                at_price=str(price),
                phase=phase,
                fraction=str(fraction),
                time_precision="bar_interval" if phase == "intrabar" else "observed",
                interval_start=b.at.isoformat(),
                interval_end=(b.end_at or b.at).isoformat(),
            )
        )

    def finish(status, reason, price):
        result.update(status=status, exit_reason=reason)
        average = price if first_exit is None else (first_exit + price) / 2
        result["modeled_return_pct"] = str(100 * (average - entry) / entry)
        return result

    def ambiguous(reason, b):
        result["events"].append(
            dict(
                event="ambiguous_intrabar",
                at=b.at.isoformat(),
                phase="intrabar",
                fraction=None,
                time_precision="bar_interval",
                interval_start=b.at.isoformat(),
                interval_end=(b.end_at or b.at).isoformat(),
            )
        )
        result.update(status="ambiguous", reason=reason)
        return result

    for index, b in enumerate(ordered):
        if b.open <= active_stop():
            event(
                "stop", b, b.open, "open", Decimal("0.5") if first_exit is not None else Decimal(1)
            )
            return finish(
                "target1_first" if first_exit is not None else "stop_first",
                "target1_then_stop" if first_exit is not None else "stop_first",
                b.open,
            )
        if first_exit is None and b.open >= t1:
            first_exit = b.open
            event("target1", b, b.open, "open", Decimal("0.5"))
        if first_exit is not None and b.open >= t2:
            event("target2", b, b.open, "open", Decimal("0.5"))
            return finish("target2_after_target1", "target2", b.open)
        stop = active_stop()
        target = t1 if first_exit is None else t2
        if b.low <= stop and b.high >= target:
            return ambiguous("intrabar_stop_and_target", b)
        if b.low <= stop:
            event(
                "stop",
                b,
                stop,
                "intrabar",
                Decimal("0.5") if first_exit is not None else Decimal(1),
            )
            return finish(
                "target1_first" if first_exit is not None else "stop_first",
                "target1_then_stop" if first_exit is not None else "stop_first",
                stop,
            )
        if b.high >= target:
            if first_exit is not None:
                event("target2", b, t2, "intrabar", Decimal("0.5"))
                return finish("target2_after_target1", "target2", t2)
            first_exit = t1
            event("target1", b, t1, "intrabar", Decimal("0.5"))
            if b.low <= active_stop():
                return ambiguous("intrabar_target1_and_new_stop", b)
            if b.high >= t2:
                return ambiguous("intrabar_target1_and_target2", b)
        if index == expiry_index:
            event(
                "expiry",
                b,
                b.close,
                "close",
                Decimal("0.5") if first_exit is not None else Decimal(1),
            )
            return finish("expired", "documented_expiry", b.close)
    result.update(
        status="target1_first" if first_exit is not None else "not_triggered",
        reason="observation_window_ended",
    )
    return result
