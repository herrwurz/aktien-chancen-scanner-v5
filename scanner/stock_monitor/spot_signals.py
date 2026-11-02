"""Conservative, auditable spot momentum candidate filter (not a buy recommendation)."""

from __future__ import annotations

from decimal import Decimal

from scanner.domain import Candle


def evaluate_spot_candidate(candles: list[Candle]) -> dict:
    """Return evidence and a candidate flag, never a trade instruction.

    Uses 20 preceding closed five-minute bars as baseline; rejects stale,
    discontinuous, illiquid or invalid samples.
    """
    if len(candles) < 21:
        return {"qualified": False, "reason": "insufficient_history"}
    bars = candles[-21:]
    if any(bar.interval != "5m" or bar.market != bars[0].market for bar in bars):
        return {"qualified": False, "reason": "mixed_market"}
    if any(left.close_time != right.open_time for left, right in zip(bars, bars[1:], strict=False)):
        return {"qualified": False, "reason": "discontinuous_candles"}
    baseline = bars[:-1]
    current = bars[-1]
    if any(bar.close <= 0 for bar in bars):
        return {"qualified": False, "reason": "invalid_close"}
    avg_quote = sum((bar.quote_volume for bar in baseline), Decimal(0)) / 20
    if avg_quote <= 0:
        return {"qualified": False, "reason": "no_baseline_liquidity"}
    volume_ratio = current.quote_volume / avg_quote
    return_pct = (current.close / bars[-4].close - 1) * 100
    return_5m_pct = (current.close / baseline[-1].close - 1) * 100
    return_60m_pct = (current.close / bars[-13].close - 1) * 100
    prior_peak = max(bar.high for bar in baseline)
    breakout_pct = (current.close / prior_peak - 1) * 100
    overheated = return_60m_pct > Decimal("15") or return_5m_pct > Decimal("8")
    qualified = (
        not overheated
        and current.quote_volume >= Decimal("100000")
        and volume_ratio >= Decimal("3")
        and return_pct >= Decimal("1.5")
    )
    return {
        "qualified": qualified,
        "reason": "overheated_move" if overheated else (
            "momentum_candidate" if qualified else "thresholds_not_met"
        ),
        "volume_ratio": round(float(volume_ratio), 3),
        "return_5m_pct": round(float(return_5m_pct), 3),
        "return_60m_pct": round(float(return_60m_pct), 3),
        "breakout_above_prior_20_bar_high_pct": round(float(breakout_pct), 3),
        "overheated": overheated,
        "return_15m_pct": round(float(return_pct), 3),
        "quote_volume_5m": round(float(current.quote_volume), 2),
        "candle_closed_at": current.close_time.isoformat(),
        "requires_listing_and_spread_validation": True,
    }
