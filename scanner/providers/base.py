from datetime import datetime
from typing import Literal, Protocol

from scanner.domain import Candle


class ProviderError(Exception):
    """A bounded, sanitized provider failure (never include request credentials)."""


class MarketDataProvider(Protocol):
    name: str
    asset_class: Literal["crypto", "stock"]

    async def fetch_candles(
        self, symbol: str, interval: str, *, limit: int, now: datetime
    ) -> list[Candle]: ...


# Future stock, DEX and authorized community adapters are registered separately.
# They must normalize to Candle or define a separate domain for non-OHLCV data.
