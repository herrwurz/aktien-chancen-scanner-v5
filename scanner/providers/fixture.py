from datetime import UTC, datetime
from decimal import Decimal

from scanner.domain import INTERVALS, Candle


class FixtureProvider:
    """Synthetic offline data, explicitly labelled; never historical evidence."""

    name = "fixture"
    asset_class = "crypto"

    async def fetch_candles(self, symbol, interval, *, limit, now):
        step = INTERVALS[interval]
        seconds = int(step.total_seconds())
        boundary = datetime.fromtimestamp(int(now.timestamp()) // seconds * seconds, tz=UTC)
        return [
            Candle(
                provider=self.name,
                asset_class=self.asset_class,
                symbol=symbol,
                interval=interval,
                open_time=boundary - step * (limit - i),
                close_time=boundary - step * (limit - i - 1),
                open=Decimal("100"),
                high=Decimal("110"),
                low=Decimal("90"),
                close=Decimal("105"),
                volume=Decimal("4000") if i == limit - 1 else Decimal("1000"),
                quote_volume=Decimal("420000") if i == limit - 1 else Decimal("105000"),
            )
            for i in range(limit)
        ]
