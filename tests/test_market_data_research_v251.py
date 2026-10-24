from datetime import UTC, datetime

import pytest

from scanner.market_data.models import InstrumentListing
from scanner.market_data.providers import normalize_tiingo
from scanner.research import AssetIdentity

NOW = datetime(2025, 1, 7, tzinfo=UTC)


def identity(ticker="AAPL"):
    return AssetIdentity(
        asset_type="stock",
        name="Apple Inc.",
        ticker=ticker,
        cik="0000320193",
        exchange="NASDAQ",
        mic="XNAS",
        country="US",
        source_available_at=datetime(2024, 1, 1, tzinfo=UTC),
        retrieved_at=datetime(2024, 1, 1, tzinfo=UTC),
    )


def import_price(archive):
    listing = InstrumentListing(
        asset_id="cik:0000320193",
        cik="0000320193",
        ticker="AAPL",
        exchange="NASDAQ",
        mic="XNAS",
        currency="USD",
        timezone="America/New_York",
        provider_symbol="AAPL",
    )
    archive.import_batch(
        normalize_tiingo(
            {
                "vendor": "Tiingo",
                "request": {
                    "dataset": "daily_prices",
                    "symbol": "AAPL",
                    "start": "2025-01-02",
                    "end": "2025-01-02",
                },
                "payload": [
                    {
                        "date": "2025-01-02T00:00:00Z",
                        "open": 100,
                        "high": 110,
                        "low": 90,
                        "close": 105,
                        "volume": 1000,
                        "adjOpen": 100,
                        "adjHigh": 110,
                        "adjLow": 90,
                        "adjClose": 105,
                        "adjVolume": 1000,
                        "divCash": 0,
                        "splitFactor": 1,
                    }
                ],
                "retrieved_at": "2025-01-06T12:00:00+00:00",
                "manifest_sha256": "a" * 64,
                "raw_sha256": "b" * 64,
                "source_reference": "https://api.tiingo.com/tiingo/daily/AAPL/prices",
                "license": "https://www.tiingo.com/documentation/general/overview",
            },
            listing,
        )
    )


def service(tmp_path, *, with_prices):
    from scanner.market_data.archive import MarketDataArchive
    from scanner.research_index.builder import build_index
    from scanner.research_index.repository import ResearchIndex
    from scanner.research_service import IndexedResearchService

    index_path = tmp_path / "research.db"
    build_index(index_path, assets=[identity()], events=[], facts=[], news=[])
    archive = (
        MarketDataArchive(tmp_path / "prices.db", now=lambda: datetime(2025, 1, 6, 13, tzinfo=UTC))
        if with_prices
        else None
    )
    if archive:
        import_price(archive)
    return IndexedResearchService(ResearchIndex(index_path), price_archive=archive)


def test_research_prices_resolves_exact_sec_identity(tmp_path):
    result = service(tmp_path, with_prices=True).prices(
        identity(),
        start="2025-01-02",
        end="2025-01-02",
        as_of=NOW,
        availability_mode="strict",
    )
    assert result["status"] == "available"
    assert result["asset_id"] == "cik:0000320193"
    assert result["prices"][0]["raw"]["close"] == "105"
    assert result["strategy_decision"] is None


def test_research_prices_does_not_link_conflicting_ticker_to_cik(tmp_path):
    result = service(tmp_path, with_prices=True).prices(
        identity(ticker="MSFT"),
        start="2025-01-02",
        end="2025-01-02",
        as_of=NOW,
    )
    assert result["status"] == "identity_conflict"
    assert result["prices"] == []


def test_research_prices_reports_unavailable_without_price_archive(tmp_path):
    result = service(tmp_path, with_prices=False).prices(
        identity(), start="2025-01-02", end="2025-01-02", as_of=NOW
    )
    assert result == {
        "status": "unavailable",
        "prices": [],
        "as_of": NOW.isoformat(),
        "reason": "market_data_archive_not_configured",
        "strategy_decision": None,
    }


def test_cik_padding_uses_one_canonical_asset_id_end_to_end(tmp_path):
    unpadded = identity().model_copy(update={"cik": "320193"})
    result = service(tmp_path, with_prices=True).prices(
        unpadded,
        start="2025-01-02",
        end="2025-01-02",
        as_of=NOW,
        availability_mode="strict",
    )
    assert result["asset_id"] == "cik:0000320193"
    assert result["prices"][0]["raw"]["close"] == "105"


def test_index_fails_closed_for_unresolved_multiple_listings(tmp_path):
    from scanner.research_index.builder import build_index

    with pytest.raises(ValueError, match="multiple listings"):
        build_index(
            tmp_path / "research.db",
            assets=[identity(), identity(ticker="AAPL.B")],
            events=[],
            facts=[],
            news=[],
        )
