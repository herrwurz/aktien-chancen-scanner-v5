"""Deterministic cross-run spot ticker acceleration ranking.

Rolling 24h quote-volume differences are NOT hourly traded volume.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation


def rank_snapshot(
    symbols: list[str], current: dict, previous: dict | None
) -> tuple[list[str], str]:
    """Prioritize hourly price acceleration when a previous snapshot exists."""
    if not previous:
        return symbols, "no_previous_snapshot"
    scores = {}
    for symbol in symbols:
        now = current.get(symbol)
        old = previous.get(symbol)
        if not isinstance(now, dict) or not isinstance(old, dict):
            continue
        try:
            price = Decimal(str(now["price"]))
            prior = Decimal(str(old["price"]))
        except (KeyError, InvalidOperation, TypeError):
            continue
        if not price.is_finite() or not prior.is_finite() or prior <= 0:
            continue
        scores[symbol] = (price / prior - 1) * 100
    if not scores:
        return symbols, "no_comparable_prices"
    original_order = {symbol: i for i, symbol in enumerate(symbols)}
    ranked = sorted(
        symbols,
        key=lambda symbol: (
            -scores.get(symbol, Decimal("-999999")),
            original_order[symbol],
        ),
    )
    return ranked, "cross_run_price_change"
