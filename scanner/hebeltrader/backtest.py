"""Evidence-first OHLC event replay. No derivative execution or inferred labels."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

VERSION = "hebel-stock-ohlc-v1"
UNKNOWN = "unknown"


@dataclass(frozen=True)
class Bar:
    at: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal

    def __post_init__(self):
        if self.at.tzinfo is None:
            raise ValueError("bar timestamp needs a timezone")
        if (
            not 0
            < self.low
            <= min(self.open, self.close)
            <= max(self.open, self.close)
            <= self.high
        ):
            raise ValueError("invalid OHLC bar")


def _decimal(value):
    return Decimal(str(value)) if value is not None else None


def simulate_stock(
    *,
    available_at: datetime,
    bars: Iterable[Bar],
    target1,
    target2,
    stop1,
    stop2=None,
    horizon=None,
):
    """Conservative event replay: same-bar target/stop is ambiguous, not a win."""
    result = dict(
        method=VERSION,
        status=UNKNOWN,
        events=[],
        realized_return_pct=None,
        reason=None,
        instrument="stock",
        caveat="OHLC indicative; no executed trades",
    )
    if available_at.tzinfo is None:
        result["reason"] = "missing_availability_timezone"
        return result
    t1, t2, s1, s2 = map(_decimal, (target1, target2, stop1, stop2))
    if t1 is None or t2 is None or s1 is None or not (0 < s1 < t1 < t2):
        result["reason"] = "missing_or_invalid_targets"
        return result
    ordered = sorted(bars, key=lambda b: b.at)
    if len({b.at for b in ordered}) != len(ordered):
        result["reason"] = "duplicate_bar_timestamps"
        return result
    ordered = [b for b in ordered if b.at > available_at and (horizon is None or b.at <= horizon)]
    if not ordered:
        result["reason"] = "no_post_publication_bars"
        return result
    # The first observed OPEN is an indicative entry, not the publication quote.
    entry = ordered[0].open
    result["indicative_entry"] = str(entry)
    if not (s1 < entry < t1):
        result["reason"] = "entry_outside_stop_target_range"
        return result
    first_hit = False
    first_exit = None
    for b in ordered:
        # On overnight gaps, observe executable open before any intrabar highs/lows.
        active_stop = s2 if first_hit and s2 is not None else (entry if first_hit else s1)
        if b.open <= active_stop:
            result["events"].append(
                {"event": "stop", "at": b.at.isoformat(), "at_price": str(b.open), "phase": "open"}
            )
            if first_hit:
                result["status"] = "target1_then_stop"
                result["realized_return_pct"] = str(
                    100 * ((first_exit + b.open) / 2 - entry) / entry
                )
            else:
                result["status"] = "stop_first"
                result["realized_return_pct"] = str(100 * (b.open - entry) / entry)
            return result
        if b.open >= (t2 if first_hit else t1):
            if not first_hit:
                first_hit, first_exit = True, b.open
                result["events"].append(
                    {
                        "event": "target1",
                        "at": b.at.isoformat(),
                        "at_price": str(b.open),
                        "phase": "open",
                    }
                )
            if b.open >= t2:
                result["events"].append(
                    {
                        "event": "target2",
                        "at": b.at.isoformat(),
                        "at_price": str(b.open),
                        "phase": "open",
                    }
                )
                result["status"] = "target2_after_target1"
                result["realized_return_pct"] = str(
                    100 * (((first_exit + b.open) / 2) - entry) / entry
                )
                return result
        hit_stop = b.low <= active_stop
        hit_target = b.high >= (t2 if first_hit else t1)
        if hit_stop and hit_target:
            result["status"] = "ambiguous"
            result["reason"] = "intrabar_stop_and_target"
            result["events"].append({"event": "ambiguous", "at": b.at.isoformat()})
            return result
        if hit_stop:
            result["events"].append(
                {
                    "event": "stop",
                    "at": b.at.isoformat(),
                    "at_price": str(active_stop),
                    "phase": "intrabar",
                }
            )
            result["status"] = "target1_then_stop" if first_hit else "stop_first"
            price = (first_exit + active_stop) / 2 if first_hit else active_stop
            result["realized_return_pct"] = str(100 * (price - entry) / entry)
            return result
        if hit_target:
            if first_hit:
                result["status"] = "target2_after_target1"
                result["events"].append(
                    {
                        "event": "target2",
                        "at": b.at.isoformat(),
                        "at_price": str(t2),
                        "phase": "intrabar",
                    }
                )
                result["realized_return_pct"] = str(100 * ((first_exit + t2) / 2 - entry) / entry)
                return result
            first_hit, first_exit = True, t1
            result["events"].append(
                {
                    "event": "target1",
                    "at": b.at.isoformat(),
                    "at_price": str(t1),
                    "phase": "intrabar",
                }
            )
            # With daily OHLC, target1 and target2 in same candle imply unknown order of exit.
            if b.high >= t2:
                result["status"] = "ambiguous"
                result["reason"] = "intrabar_target1_and_target2"
                return result
    result["status"] = "target1_open" if first_hit else "not_triggered"
    result["reason"] = "observation_window_ended"
    return result
