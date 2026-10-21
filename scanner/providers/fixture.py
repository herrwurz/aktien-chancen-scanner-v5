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
        # Replay complete 21-bar blocks so the default demo always has a spike
        # with 20 baseline bars. Values depend on timestamps, never fetch position.
        block_seconds = seconds * 21
        boundary = datetime.fromtimestamp(
            int(now.timestamp()) // block_seconds * block_seconds, tz=UTC
        )
        result = []
        for i in range(limit):
            close_time = boundary - step * (limit - i - 1)
            spike = int(close_time.timestamp()) // seconds % 21 == 0
            result.append(
                Candle(
                    provider=self.name,
                    asset_class=self.asset_class,
                    symbol=symbol,
                    interval=interval,
                    open_time=boundary - step * (limit - i),
                    close_time=close_time,
                    open=Decimal("100"),
                    high=Decimal("110"),
                    low=Decimal("90"),
                    close=Decimal("105"),
                    volume=Decimal("4000") if spike else Decimal("1000"),
                    quote_volume=Decimal("420000") if spike else Decimal("105000"),
                )
            )
        return result
