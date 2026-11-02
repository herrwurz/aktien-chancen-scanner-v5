"""Chart-first index-pool expansion: sector slice without issuer hardcoding."""

from scanner.hebeltrader.detective.investigation import (
    _chart_rank_pool_assets,
    _merge_pool_seed_rows,
    _pool_assets_for_teaser,
    _pool_seed_queries,
    canonical_company,
)

TEASER = (
    "Der KI-Boom braucht gewaltige Energiemengen, und genau dort sitzt ein "
    "US-Versorger an einer der lukrativsten Schaltstellen des Megatrends! "
    "Charttechnisch hat sich zudem ein kraftvolles Golden Cross gebildet."
)


def test_pool_assets_us_utility_excludes_eu_and_grid_equipment():
    assets = _pool_assets_for_teaser(TEASER)
    tickers = {a["ticker"] for a in assets}
    names = {a["name"] for a in assets}
    assert tickers, "expected US power-infra utilities from the index pool"
    assert all("." not in t for t in tickers)
    assert "Iberdrola" not in names
    assert "Eaton" not in names
    assert "Vertiv" not in names
    assert "Costco Wholesale" not in names
    assert "American Water Works" not in names  # water ≠ Stromversorger
    # Curated-thin utilities must still appear via index_pool, not a hard-coded list.
    assert "Ameren" in names or "AEE" in tickers
    assert "American Electric Power" in names or "AEP" in tickers


def test_handelsstrategie_does_not_add_retail_sector():
    from scanner.hebeltrader.detective.structure_screen import sectors_in

    text = TEASER + " Smarte Anleger sichern sich die Analyse mit klarer Handelsstrategie."
    assert "retail" not in sectors_in(text)
    assert "power infrastructure" in sectors_in(text)


def test_pool_assets_inactive_without_sector_cue():
    assert _pool_assets_for_teaser("Allgemeiner Tech-Titel ohne Branchenhinweis") == []


def test_chart_rank_prefers_golden_cross_match(monkeypatch):
    assets = [
        {"name": "Alpha Utility", "ticker": "AAA", "sector": "power infrastructure"},
        {"name": "Beta Utility", "ticker": "BBB", "sector": "power infrastructure"},
    ]

    def fake_chart(ticker, **_kwargs):
        if ticker == "AAA":
            return {
                "status": "ok",
                "golden_cross": True,
                "above_gd50": True,
                "above_gd200": True,
                "gd200_rising": True,
                "return_1y_pct": 10,
                "near_high_pct": -2,
                "breakout": False,
            }
        return {
            "status": "ok",
            "golden_cross": False,
            "above_gd50": True,
            "above_gd200": False,
            "gd200_rising": False,
            "return_1y_pct": 0,
            "near_high_pct": -20,
            "breakout": False,
        }

    monkeypatch.setattr(
        "scanner.hebeltrader.detective.investigation.chart_check",
        fake_chart,
    )
    ranked, cache = _chart_rank_pool_assets(assets, TEASER, limit=2)
    assert ranked[0]["asset"]["ticker"] == "AAA"
    assert ranked[0]["chart"]["golden_cross"] is True
    assert ranked[0]["score"] > ranked[1]["score"]
    assert "pool:AAA" in cache


def test_merge_injects_missing_pool_seeds_and_fills_ticker():
    seeds = [
        {
            "asset": {
                "name": "Ameren",
                "ticker": "AEE",
                "countries": ["United States"],
            },
            "chart": {
                "status": "ok",
                "golden_cross": True,
                "above_gd50": True,
                "above_gd200": True,
                "gd200_rising": True,
                "return_1y_pct": 12,
                "near_high_pct": -3,
                "breakout": False,
            },
            "score": 20,
        }
    ]
    web_row = {
        "asset_id": "company:"
        + __import__("hashlib").sha256(canonical_company("Dominion Energy").encode()).hexdigest(),
        "identity": {"name": "Dominion Energy", "ticker": None},
        "evidence_score": 5,
        "hard_contradictions": [],
        "evidence_matrix": [],
        "confirmed_specific_clues": [],
        "cited_findings": [],
        "unknown_clues": [],
        "sources": [],
        "comparison_evidence_available": True,
        "counterarguments": [],
    }
    merged = _merge_pool_seed_rows([web_row], seeds, retrieved="2026-11-02T00:00:00Z", text=TEASER)
    names = [r["identity"]["name"] for r in merged]
    assert "Ameren" in names
    assert "Dominion Energy" in names
    ameren = next(r for r in merged if r["identity"]["name"] == "Ameren")
    assert ameren["identity"]["ticker"] == "AEE"
    assert ameren["pool_seed"] is True
    assert ameren["chart"]["golden_cross"] is True


def test_pool_seed_queries_include_chart_ranked_names():
    seeds = [
        {
            "asset": {"name": "Ameren", "ticker": "AEE"},
            "chart": {"status": "ok"},
            "score": 1,
        }
    ]
    queries = _pool_seed_queries(seeds, TEASER, limit=3)
    assert queries
    assert "Ameren" in queries[0]
    assert "AEE" in queries[0]
