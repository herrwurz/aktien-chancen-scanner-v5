"""Sector queries and SEC/IR reads run before chart and peer searches."""

from datetime import UTC, datetime
from time import monotonic

import pytest

from scanner.hebeltrader.detective.investigation import _filing_targets
from scanner.hebeltrader.detective.market_pages import collect_issuer_filings
from scanner.hebeltrader.detective.research_plan import prioritize_queries

WHEN = datetime(2026, 10, 26, 8, tzinfo=UTC)
SEC = "https://www.sec.gov/Archives/edgar/data/1/slb.htm"


def test_sector_and_filing_queries_precede_chart_and_peer_queries():
    ordered = prioritize_queries(
        [
            "company stock 200 day moving average support",
            "oilfield services company AI data center cooling",
            '"MSCI" competitors peer group annual report',
            "semiconductor earnings quarterly results",
        ]
    )
    assert ordered[0].startswith("oilfield")
    assert "earnings" in ordered[1]
    assert "200 day" in ordered[2]
    assert "peer group" in ordered[3]


def test_filing_targets_keep_the_sector_pool_ahead_of_name_guesses():
    blocked = {"tickers": set(), "names": set(), "status": "ok"}
    rows = _filing_targets(
        [{"asset": {"name": "SLB", "ticker": "SLB"}}],
        [{"name": "Baker Hughes", "ticker": "BKR"}],
        ["MSCI", "Equinix", "SLB"],
        blocked,
    )
    assert [row["name"] for row in rows[:2]] == ["SLB", "Baker Hughes"]
    assert rows[2]["name"] == "MSCI"
    assert len(rows) == 4


class _Web:
    def __init__(self):
        self.queries = []

    def search(self, query, limit=10, include_domains=None, start_date=None, end_date=None):
        self.queries.append((query, list(include_domains) if include_domains else None))
        if include_domains and "sec.gov" in include_domains:
            return [
                {
                    "url": SEC,
                    "title": "SLB 8-K",
                    "content": "SLB earnings",
                    "published_at": "2026-10-20T12:00:00Z",
                }
            ]
        return [
            {
                "url": "https://www.marketwatch.com/story/slb",
                "title": "roundup",
                "content": "SLB mentioned",
                "published_at": "2026-10-20T12:00:00Z",
            }
        ]

    def fetch(self, url):
        return {
            "url": url,
            "title": "SLB 8-K",
            "text": "SLB earnings release",
            "published_at": "2026-10-20T12:00:00+00:00",
        }


def test_issuer_filing_stops_at_the_sec_page():
    web = _Web()
    report, docs = collect_issuer_filings(
        web, [{"name": "SLB", "ticker": "SLB"}], publication_at=WHEN
    )
    assert report["status"] == "read"
    assert report["names"] == [{"name": "SLB", "ticker": "SLB", "surface": "sec"}]
    assert docs[0]["url"] == SEC
    assert docs[0]["company_name"] == "SLB"
    assert docs[0]["identity_basis"] == "issuer_filing"
    assert len(web.queries) == 1
    assert web.queries[0][1] == ["sec.gov"]


def test_external_duration_uses_the_configured_limit(tmp_path):
    from scanner.hebeltrader.detective.api_budget import ApiBudget
    from scanner.hebeltrader.detective.external_research import ResearchApis

    api = ResearchApis(
        root=tmp_path,
        budget=ApiBudget(tmp_path / "budget.db"),
        approved=False,
        max_duration_seconds=60,
    )
    api.started = monotonic() - 61
    with pytest.raises(ValueError, match="duration limit"):
        api.check_deadline()
    assert api.max_duration_seconds == 60
