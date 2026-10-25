import hashlib
from datetime import UTC, date, datetime, timedelta

import pytest


def market_batch(*, asset_id="cik:0000320193", cik="0000320193", ticker="AAPL"):
    from scanner.market_data.models import InstrumentListing
    from scanner.market_data.providers import normalize_tiingo

    rows = []
    for offset in range(2):
        day = date(2025, 1, 2) + timedelta(days=offset)
        rows.append(
            {
                "date": f"{day.isoformat()}T00:00:00Z",
                "open": 100 + offset,
                "high": 102 + offset,
                "low": 99 + offset,
                "close": 101 + offset,
                "volume": 1000 + offset,
                "adjOpen": 100 + offset,
                "adjHigh": 102 + offset,
                "adjLow": 99 + offset,
                "adjClose": 101 + offset,
                "adjVolume": 1000 + offset,
                "divCash": 0,
                "splitFactor": 1,
            }
        )
    record = {
        "vendor": "Tiingo",
        "request": {
            "dataset": "daily_prices",
            "symbol": ticker,
            "start": "2025-01-02",
            "end": "2025-01-03",
        },
        "payload": rows,
        "retrieved_at": "2026-10-25T08:00:00+00:00",
        "manifest_sha256": hashlib.sha256(f"{ticker}:manifest".encode()).hexdigest(),
        "raw_sha256": hashlib.sha256(f"{ticker}:raw".encode()).hexdigest(),
        "source_reference": f"https://api.tiingo.com/tiingo/daily/{ticker}/prices",
        "license": "https://www.tiingo.com/documentation/general/overview",
    }
    listing = InstrumentListing(
        asset_id=asset_id,
        cik=cik,
        ticker=ticker,
        exchange="NASDAQ",
        mic="XNAS",
        currency="USD",
        timezone="America/New_York",
        provider_symbol=ticker,
    )
    return normalize_tiingo(record, listing)


def test_read_only_archive_does_not_create_missing_database(tmp_path):
    from scanner.market_data.archive import MarketDataArchive

    path = tmp_path / "missing.sqlite"
    with pytest.raises(FileNotFoundError):
        MarketDataArchive(path, read_only=True)

    assert not path.exists()


def test_read_only_archive_lists_canonical_instruments_without_mutation(tmp_path):
    from scanner.market_data.archive import MarketDataArchive

    path = tmp_path / "market.sqlite"
    writer = MarketDataArchive(
        path,
        now=lambda: datetime(2026, 10, 25, 9, tzinfo=UTC),
    )
    writer.import_batch(market_batch())
    digest_before = hashlib.sha256(path.read_bytes()).hexdigest()

    reader = MarketDataArchive(path, read_only=True)

    assert reader.list_instruments() == [
        {
            "asset_id": "cik:0000320193",
            "cik": "0000320193",
            "ticker": "AAPL",
            "exchange": "NASDAQ",
            "mic": "XNAS",
            "currency": "USD",
            "timezone": "America/New_York",
            "provider_symbol": "AAPL",
            "isin": None,
        }
    ]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest_before
