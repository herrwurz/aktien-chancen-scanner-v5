"""Market-wide Binance USDT ticker screening for all eligible symbols."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

import httpx


async def discover_spot_symbols(
    client: httpx.AsyncClient,
    *,
    min_quote_volume: Decimal = Decimal("100000"),
) -> dict:
    """Screen all returned spot ticker rows without a top-N cutoff."""
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
        return {
            "status": "complete",
            "source": "binance_spot_24h_ticker",
            "symbols": [symbol for symbol, _, _ in rows],
            "screened_symbols": len(payload),
            "eligible_symbols": len(rows),
            "selection": "absolute_24h_price_change_then_quote_volume",
            "limitations": (
                "24h change is not early momentum; one exchange only; "
                "spot eligibility not independently confirmed"
            ),
        }
    except (httpx.HTTPError, ValueError) as exc:
        return {"status": "unavailable", "error_type": type(exc).__name__, "symbols": []}
