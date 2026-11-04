"""Market-page search keeps names that show up on two fixed news hosts."""

from datetime import UTC, datetime

from scanner.hebeltrader.detective.investigation import InvestigationRequest, Investigator
from scanner.hebeltrader.detective.market_pages import (
    news_queries,
    read_backlog_and_profit,
    teaser_asks_market_pages,
    teaser_market_terms,
)
from scanner.hebeltrader.detective.source_kind import MARKET_NEWS_HOSTS

TEASER = (
    "Goldgrube entdeckt: So nutzen clevere Anleger den Aufwärtstrend! "
    "Die Wall Street hat diesen schlafenden Riesen längst auf dem Radar. "
    "Die Gewinne wachsen rasant und die Auftragsbücher versprechen Einnahmen. "
    "Nach einer kräftigen Korrektur mehren sich die Signale für eine Trendwende."
)
WHEN = datetime(2026, 10, 27, 7, 15, tzinfo=UTC)

FN = "https://www.finanznachrichten.de/nachrichten-2026-10/rtx.htm"
WSO = "https://www.wallstreet-online.de/nachricht/21553109-rtx"
MW = "https://www.marketwatch.com/story/eaton-pullback"
SEC_RTX = "https://www.sec.gov/Archives/edgar/data/1/rtx.htm"
SEC_NOC = "https://www.sec.gov/Archives/edgar/data/2/noc.htm"


def test_any_two_market_terms_open_the_same_pages():
    found = set(teaser_market_terms(TEASER))
    assert {"order_book", "profit_growth", "correction", "wall_street", "uptrend"} <= found
    assert teaser_asks_market_pages(TEASER) is True
    other = teaser_market_terms("Nach der Korrektur steigt die Dividende.")
    assert set(other) == {"correction", "dividend"}
    assert teaser_asks_market_pages("Nach der Korrektur steigt die Dividende.") is True
    german, english = news_queries(other)
    assert "Korrektur" in german and "Dividende" in german
    assert "pullback" in english and "dividend" in english
    assert (
        teaser_asks_market_pages("Der heimliche Gewinner der nächsten Finanzrevolution!") is False
    )
    assert teaser_asks_market_pages("Die Auftragsbücher sind voll.") is False


def test_primary_lead_reads_backlog_and_profit_direction():
    backlog, profit = read_backlog_and_profit(
        "Total backlog reached a record. Earnings per share increased 33 percent."
    )
    assert backlog is True and profit == "up"
    backlog, profit = read_backlog_and_profit(
        "Backlog reached a record. Net income decreased 7 percent."
    )
    assert backlog is True and profit == "down"


class _Pages:
    def __init__(self):
        self.calls = []
        self.pages = {
            FN: "RTX und Northrop Grumman mit vollem Auftragsbestand.",
            WSO: "RTX und Northrop Grumman nach der Korrektur.",
            MW: "Eaton Corporation backlog stays high.",
            SEC_RTX: (
                "RTX Corporation total backlog reached a record. "
                "Earnings per share increased 33 percent."
            ),
            SEC_NOC: ("Northrop Grumman backlog reached a record. Net income decreased 7 percent."),
        }

    def search(self, query, limit=10, include_domains=None, start_date=None, end_date=None):
        self.calls.append(
            {
                "query": query,
                "include_domains": list(include_domains) if include_domains else None,
                "start_date": start_date,
                "end_date": end_date,
                "limit": limit,
            }
        )
        domains = set(include_domains or [])
        if "sec.gov" in domains:
            if "RTX" in query:
                return [{"url": SEC_RTX, "title": "RTX", "content": self.pages[SEC_RTX]}]
            if "Northrop" in query:
                return [{"url": SEC_NOC, "title": "Northrop", "content": self.pages[SEC_NOC]}]
            return []
        if include_domains is None:
            return []
        return [
            {"url": url, "title": "tape", "content": text, "published_at": "2026-10-20T12:00:00Z"}
            for url, text in self.pages.items()
            if url not in {SEC_RTX, SEC_NOC}
        ]

    def fetch(self, url):
        return {
            "url": url,
            "title": "tape",
            "text": self.pages[url],
            "published_at": "2026-10-20T12:00:00+00:00",
        }


def test_two_hosts_keep_a_cluster_and_block_identification(tmp_path):
    web = _Pages()
    report = Investigator(tmp_path, web=web, clock=lambda: WHEN).analyze(
        InvestigationRequest(teaser_text=TEASER, publication_at=WHEN)
    )
    pages = report["market_pages"]
    assert pages["status"] == "cluster"
    assert {"order_book", "profit_growth", "correction"} <= set(pages["terms"])
    assert pages["hosts"] == list(MARKET_NEWS_HOSTS)
    assert pages["window"] == {"start": "2026-10-06", "end": "2026-10-27"}
    by_name = {item["name"]: item for item in pages["names"]}
    assert set(by_name) == {"RTX", "Northrop Grumman"}
    assert by_name["RTX"]["ticker"] == "RTX"
    assert by_name["RTX"]["hosts"] == [
        "finanznachrichten.de",
        "wallstreet-online.de",
    ]
    assert by_name["RTX"]["backlog"] is True
    assert by_name["RTX"]["profit"] == "up"
    assert by_name["Northrop Grumman"]["profit"] == "down"
    assert by_name["RTX"]["sec_url"] == SEC_RTX
    assert report["identification"]["status"] == "not_identified"
    assert "market_page_name_cluster" in report["limitations"]
    news_calls = [call for call in web.calls if call["include_domains"] == list(MARKET_NEWS_HOSTS)]
    assert len(news_calls) == 2
    assert {call["start_date"] for call in news_calls} == {"2026-10-06"}
    assert any(call["include_domains"] == ["sec.gov"] for call in web.calls)
