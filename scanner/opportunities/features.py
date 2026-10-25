"""Pure, past-bounded technical feature calculations."""

from datetime import date
from decimal import Decimal, InvalidOperation
from statistics import median

from .models import TechnicalFeatures

FIELDS = ("open", "high", "low", "close", "volume")


def _number(value) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("complete adjusted OHLCV required") from None
    if not result.is_finite() or result <= 0:
        raise ValueError("complete adjusted OHLCV required")
    return result


def _prepare(bars, signal_date):
    prepared = []
    for row in bars:
        day = date.fromisoformat(str(row["session_date"]))
        if day > signal_date:
            continue
        adjusted = row.get("adjusted") or {}
        values = {field: _number(adjusted.get(field)) for field in FIELDS}
        raw_close = _number((row.get("raw") or {}).get("close"))
        prepared.append((day, values, raw_close))
    prepared.sort(key=lambda value: value[0])
    if len({row[0] for row in prepared}) != len(prepared):
        raise ValueError("duplicate feature session")
    if len(prepared) < 21:
        raise ValueError("at least 21 complete sessions required")
    return prepared


def _return(rows, sessions):
    return rows[-1][1]["close"] / rows[-1 - sessions][1]["close"] - 1


def compute_features(bars, *, signal_date, benchmark_bars=None) -> TechnicalFeatures:
    rows = _prepare(bars, signal_date)
    current = rows[-1]
    prior = rows[-21:-1]
    current_values = current[1]
    prior_volumes = [row[1]["volume"] for row in prior]
    average_volume = sum(prior_volumes, Decimal(0)) / Decimal(20)
    if average_volume <= 0:
        raise ValueError("positive prior volume required")

    true_ranges = []
    for index in range(len(rows) - 14, len(rows)):
        values = rows[index][1]
        previous_close = rows[index - 1][1]["close"]
        true_ranges.append(
            max(
                values["high"] - values["low"],
                abs(values["high"] - previous_close),
                abs(values["low"] - previous_close),
            )
        )
    atr = sum(true_ranges, Decimal(0)) / Decimal(14)
    close = current_values["close"]
    momentum_20 = _return(rows, 20)
    sma_5 = sum((row[1]["close"] for row in rows[-5:]), Decimal(0)) / Decimal(5)
    sma_20 = sum((row[1]["close"] for row in rows[-20:]), Decimal(0)) / Decimal(20)
    if sma_5 > sma_20 and momentum_20 > 0:
        trend = "up"
    elif sma_5 < sma_20 and momentum_20 < 0:
        trend = "down"
    else:
        trend = "flat"
    prior_high = max(row[1]["high"] for row in prior)
    relative_strength = None
    benchmark_status = "unavailable"
    if benchmark_bars is not None:
        benchmark_rows = _prepare(benchmark_bars, signal_date)
        relative_strength = momentum_20 - _return(benchmark_rows, 20)
        benchmark_status = "available"

    return TechnicalFeatures(
        signal_date=current[0],
        session_count_available=len(rows),
        raw_reference_close=current[2],
        adjusted_reference_close=close,
        momentum_5=_return(rows, 5),
        momentum_10=_return(rows, 10),
        momentum_20=momentum_20,
        average_volume_prior_20=average_volume,
        volume_ratio=current_values["volume"] / average_volume,
        median_dollar_volume_20=median(row[1]["close"] * row[1]["volume"] for row in rows[-20:]),
        atr_14=atr,
        atr_percent=atr / close,
        gap_percent=current_values["open"] / rows[-2][1]["close"] - 1,
        trend=trend,
        prior_20_high=prior_high,
        distance_to_prior_20_high=close / prior_high - 1,
        breakout_20=close > prior_high,
        relative_strength_20=relative_strength,
        benchmark_status=benchmark_status,
    )
