"""URL-based primary source_kind classification for live Tavily docs."""

from scanner.hebeltrader.detective.source_kind import (
    classify_live_source_kind,
    document_is_primary,
    effective_source_kind,
)


def test_sec_and_investor_urls_are_primary():
    assert (
        classify_live_source_kind(
            "https://www.sec.gov/Archives/edgar/data/4904/000000490426000073/aep-20260930.htm"
        )
        == "regulatory"
    )
    assert (
        classify_live_source_kind(
            "https://investor.nexteraenergy.com/news-and-events/news-releases"
        )
        == "issuer"
    )
    assert classify_live_source_kind("https://www.aep.com/investors/financials") == "issuer"


def test_aggregators_are_not_upgraded_to_issuer():
    assert (
        classify_live_source_kind(
            "https://www.alphaspread.com/security/nyse/aee/investor-relations"
        )
        is None
    )
    assert (
        classify_live_source_kind(
            "https://seekingalpha.com/article/4869572-ameren-corporation-aee-q4-2025"
        )
        is None
    )
    assert classify_live_source_kind("https://finance.yahoo.com/quote/AEP") is None
    assert classify_live_source_kind("https://www.marketwatch.com/story/rtx") == "news"
    assert classify_live_source_kind("https://www.finanznachrichten.de/nachricht") == "news"
    assert classify_live_source_kind("https://www.wallstreet-online.de/nachricht/1") == "news"
    assert document_is_primary({"url": "https://www.marketwatch.com/story/rtx"}) is False


def test_effective_kind_upgrades_tavily_tags_from_url():
    doc = {
        "url": "https://investor.nexteraenergy.com/overview",
        "source_kind": "search_snippet",
    }
    assert effective_source_kind(doc) == "issuer"
    assert document_is_primary(doc) is True
    news = {
        "url": "https://www.fool.com/investing/2026/07/28/nextera",
        "source_kind": "tavily_extract",
    }
    assert document_is_primary(news) is False


def test_stocktitan_sec_filings_count_as_regulatory():
    assert (
        classify_live_source_kind("https://www.stocktitan.net/sec-filings/AEP/8-k.html")
        == "regulatory"
    )
