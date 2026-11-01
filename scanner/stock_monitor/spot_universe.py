"""Market-wide Binance USDT ticker screening with bounded candle follow-up."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

import httpx


async def discover_spot_symbols(
    client: httpx.AsyncClient,
    *,
    max_symbols: int = 40,
    min_quote_volume: Decimal = Decimal("100000"),
) -> dict:
    """Screen all returned spot ticker rows; bound only expensive candle requests."""
    if not 1 <= max_symbols <= 50:
        raise ValueError("Candle follow-up budget must be 1..50")
    try:
        response = await client.get(
            "https://data-api.binance.vision/api/v3/ticker/24hr", timeout=20
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise ValueError("Invalid ticker response")
        rows = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            symbol = item.get("symbol")
            if not isinstance(symbol, str) or not symbol.endswith("USDT"):
                continue
            if symbol.endswith(("UPUSDT", "DOWNUSDT", "BULLUSDT", "BEARUSDT")):
                continue
            try:
                quote = Decimal(str(item["quoteVolume"]))
                change = Decimal(str(item["priceChangePercent"]))
            except (KeyError, InvalidOperation, TypeError):
                continue
            if not quote.is_finite() or not change.is_finite() or quote < min_quote_volume:
                continue
            rows.append((symbol, quote, change))
        # Prioritize unusual 24h moves without restricting the market overview to top volume.
        # Quote-volume floor protects against trivially illiquid prints; 5m confirmation follows.
        rows.sort(key=lambda row: (-abs(row[2]), -row[1], row[0]))
        selected = rows[:max_symbols]
        return {
            "status": "complete",
            "source": "binance_spot_24h_ticker",
            "symbols": [symbol for symbol, _, _ in selected],
            "screened_symbols": len(payload),
            "eligible_symbols": len(rows),
            "detail_budget": max_symbols,
            "selection": "absolute_24h_price_change_then_quote_volume",
            "limitations": (
                "24h change is not early momentum; one exchange only; "
                "spot eligibility not independently confirmed"
            ),
        }
    except (httpx.HTTPError, ValueError) as exc:
        return {"status": "unavailable", "error_type": type(exc).__name__, "symbols": []}
