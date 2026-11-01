"""Bounded Binance spot universe discovery; never interprets listings as buy signals."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

import httpx


async def discover_spot_symbols(
    client: httpx.AsyncClient, *, max_symbols: int = 40, min_quote_volume: Decimal = Decimal("1000000")
) -> dict:
    if not 1 <= max_symbols <= 50:
        raise ValueError("max_symbols must be 1..50")
    try:
        response = await client.get(
            "https://data-api.binance.vision/api/v3/ticker/24hr", timeout=20
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise ValueError("Invalid ticker response")
        candidates = []
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
            except (KeyError, InvalidOperation, TypeError):
                continue
            if not quote.is_finite() or quote < min_quote_volume:
                continue
            candidates.append((symbol, quote))
        candidates.sort(key=lambda pair: (-pair[1], pair[0]))
        return {
            "status": "complete",
            "source": "binance_spot_24h_ticker",
            "symbols": [symbol for symbol, _ in candidates[:max_symbols]],
            "eligible_symbols": len(candidates),
            "selection": "top_quote_volume_24h",
            "limitations": "volume-ranked universe; may miss low-volume early movers",
        }
    except (httpx.HTTPError, ValueError) as exc:
        return {"status": "unavailable", "error_type": type(exc).__name__, "symbols": []}
