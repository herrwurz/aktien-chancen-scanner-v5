import asyncio
from datetime import UTC, datetime, timedelta

import httpx

from scanner.domain import INTERVALS, Candle
from scanner.providers.base import ProviderError


class BinanceSpotProvider:
    name = "binance_spot"
    asset_class = "crypto"
    base_url = "https://data-api.binance.vision"

    def __init__(self, client: httpx.AsyncClient, retry_delay: float = 1):
        self.client = client
        self.retry_delay = retry_delay

    async def fetch_candles(self, symbol, interval, *, limit, now):
        if interval not in INTERVALS or not 1 <= limit <= 1000:
            raise ValueError("Unsupported interval or limit")
        if now.tzinfo is None:
            raise ValueError("Timezone required")
        response = None
        for attempt in range(3):
            try:
                response = await self.client.get(
                    f"{self.base_url}/api/v3/klines",
                    params={"symbol": symbol, "interval": interval, "limit": limit},
                    timeout=15,
                )
                if response.status_code == 418:
                    raise ProviderError("Binance IP temporarily banned (418)")
                if response.status_code == 429 or response.status_code >= 500:
                    response.raise_for_status()
                elif response.is_error:
                    raise ProviderError(f"Binance rejected request ({response.status_code})")
                break
            except (httpx.TransportError, httpx.HTTPStatusError) as exc:
                if attempt == 2:
                    raise ProviderError("Binance unavailable after 3 attempts") from exc
                delay = self.retry_delay * (2**attempt)
                if response is not None:
                    try:
                        delay = min(30, max(delay, float(response.headers.get("Retry-After", 0))))
                    except ValueError:
                        pass
                await asyncio.sleep(delay)
        try:
            payload = response.json()
            if not isinstance(payload, list):
                raise ValueError("Expected array")
            result = []
            seen = set()
            for row in payload:
                if not isinstance(row, list) or len(row) != 12:
                    raise ValueError("Invalid kline")
                start = datetime.fromtimestamp(int(row[0]) / 1000, tz=UTC)
                end = datetime.fromtimestamp(int(row[6]) / 1000, tz=UTC) + timedelta(milliseconds=1)
                candle = Candle(
                    provider=self.name,
                    asset_class=self.asset_class,
                    symbol=symbol,
                    interval=interval,
                    open_time=start,
                    close_time=end,
                    open=row[1],
                    high=row[2],
                    low=row[3],
                    close=row[4],
                    volume=row[5],
                    quote_volume=row[7],
                )
                if start in seen:
                    raise ValueError("Duplicate candle")
                seen.add(start)
                if end <= now:
                    result.append(candle)
            return sorted(result, key=lambda c: c.open_time)
        except (ValueError, TypeError, OverflowError, OSError) as exc:
            raise ProviderError("Invalid Binance candle payload") from exc
