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
        exchange_response = await client.get(
            "https://data-api.binance.vision/api/v3/exchangeInfo", timeout=20
        )
        exchange_response.raise_for_status()
        exchange_payload = exchange_response.json()
        if not isinstance(exchange_payload, dict) or not isinstance(
            exchange_payload.get("symbols"), list
        ):
            raise ValueError("Invalid exchange info")
        trading = {
            row["symbol"]
            for row in exchange_payload["symbols"]
            if isinstance(row, dict)
            and isinstance(row.get("symbol"), str)
            and row.get("status") == "TRADING"
            and row.get("isSpotTradingAllowed") is True
            and row.get("quoteAsset") == "USDT"
        }
        rows = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            symbol = item.get("symbol")
            if not isinstance(symbol, str) or not symbol.endswith("USDT"):
                continue
            if symbol not in trading:
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
            try:
                last_price = Decimal(str(item["lastPrice"]))
            except (KeyError, InvalidOperation, TypeError):
                last_price = Decimal(0)
            if not last_price.is_finite() or last_price < 0:
                last_price = Decimal(0)
            rows.append((symbol, quote, change, last_price))
        # Prioritize unusual 24h moves without restricting the market overview to top volume.
        # Quote-volume floor protects against trivially illiquid prints; 5m confirmation follows.
        rows.sort(key=lambda row: (-abs(row[2]), -row[1], row[0]))
        return {
            "status": "complete",
            "source": "binance_spot_24h_ticker",
            "symbols": [symbol for symbol, _, _, _ in rows],
            "ticker_snapshot": {
                symbol: {"price": str(price), "quote_volume_24h": str(quote)}
                for symbol, quote, _, price in rows
            },
            "screened_symbols": len(payload),
            "eligible_symbols": len(rows),
            "trading_pairs": len(trading),
            "eligibility_source": "binance_exchange_info_trading_spot",
            "selection": "absolute_24h_price_change_then_quote_volume",
            "limitations": (
                "24h change is not early momentum; one exchange only; "
                "Bitpanda listing and executable spread not confirmed"
            ),
        }
    except (httpx.HTTPError, ValueError) as exc:
        return {"status": "unavailable", "error_type": type(exc).__name__, "symbols": []}
