from scanner.hebeltrader.detective import market_screen as ms
from scanner.hebeltrader.detective.chart_check import trend_features
from scanner.hebeltrader.detective.index_pool import (
    apply_ticker_remap,
    load_pool_assets,
    load_ticker_remaps,
    market_universe_list,
    normalize_eodhd_ticker,
    normalize_sector,
    pool_stats,
)


def test_normalize_eodhd_ticker_maps_de_to_xetra_and_keeps_us_bare():
    assert normalize_eodhd_ticker("DBK.DE") == "DBK.XETRA"
    assert normalize_eodhd_ticker("AAPL") == "AAPL"
    assert normalize_eodhd_ticker("AIXA", country="Germany") == "AIXA.XETRA"
    assert normalize_eodhd_ticker("ZURN", country="Switzerland") == "ZURN.SW"
    assert normalize_eodhd_ticker("IMO1.F") == "IMO1.F"
    assert normalize_eodhd_ticker("ASSAB", country="Sweden") == "ASSA-B.ST"
    assert normalize_eodhd_ticker("ASSA-B.ST") == "ASSA-B.ST"
    assert normalize_eodhd_ticker("AMBUB", country="Denmark") == "AMBU-B.CO"
    assert normalize_eodhd_ticker("BF.B") == "BF-B"
    assert normalize_eodhd_ticker("BT.A", country="United Kingdom") == "BT-A.LSE"
    assert normalize_eodhd_ticker("NDA.FI", country="Finland") == "NDA-FI.HE"


def test_normalize_sector_maps_financial_and_pharma():
    assert normalize_sector("Financial Services") == "financial services"
    assert normalize_sector("Pharmaceuticals") == "pharmaceutical"
    assert normalize_sector("Semiconductor industry") == "semiconductor"


def test_pool_v1_includes_deutsche_bank_and_index_union_size():
    stats = pool_stats()
    assert stats["asset_count"] >= 1000
    assert set(stats["indexes"]) >= {"spx", "ndx", "dax", "mdax", "sx5e", "sxxp", "atx"}
    assets = load_pool_assets()
    deutsche = [a for a in assets if a["name"] == "Deutsche Bank"]
    assert len(deutsche) == 1
    assert deutsche[0]["ticker"] == "DBK.XETRA"
    assert "dax" in deutsche[0]["sources"]
    assert deutsche[0]["sector"] == "financial services"


def test_pool_v1_includes_atx_austria():
    assets = load_pool_assets()
    atx = [a for a in assets if "atx" in (a.get("sources") or [])]
    assert len(atx) >= 20
    by_name = {a["name"]: a for a in atx}
    assert by_name["BAWAG Group"]["ticker"] == "BG.VI"
    assert by_name["Austrian Post"]["ticker"] == "POST.VI"
    assert by_name["Immofinanz"]["ticker"] == "IMO1.F"
    assert "Austria" in by_name["BAWAG Group"].get("countries", [])


def test_ticker_remaps_cover_nordic_and_french_pit_misses():
    remaps = load_ticker_remaps()
    assert remaps["ASSAB.ST"] == "ASSA-B.ST"
    assert remaps["CAPP.PA"] == "CAP.PA"
    assert remaps["ENI.MI"] == "ENI.XETRA"
    assert apply_ticker_remap("ASSAB.ST") == "ASSA-B.ST"
    assets = {a["name"]: a for a in load_pool_assets()}
    assert assets["Assa Abloy"]["ticker"] == "ASSA-B.ST"
    assert assets["Capgemini"]["ticker"] == "CAP.PA"
    assert assets["Eni"]["ticker"] == "ENI.XETRA"


def test_market_universe_overlays_curated_and_keeps_pool_names():
    market = market_universe_list()
    names = {a["name"] for a in market}
    assert "Deutsche Bank" in names
    assert "ASML Holding" in names  # curated structure name
    asml = next(a for a in market if a["name"] == "ASML Holding")
    assert asml.get("structure") in {"monopoly", "duopoly", "oligopoly", "fragmented"}


def test_market_universe_dedupes_same_ticker_across_indexes():
    market = market_universe_list()
    tickers = [a["ticker"] for a in market if a.get("ticker")]
    assert len(tickers) == len(set(tickers))
    amgn = [a for a in market if a.get("ticker") == "AMGN"]
    assert len(amgn) == 1
    cost = next(a for a in market if a.get("ticker") == "COST")
    assert cost.get("structure") == "oligopoly"
    assert "curated_global_universe" in cost["sources"]
    assert "spx" in cost["sources"] or "ndx" in cost["sources"]
    db1 = next(a for a in market if a.get("ticker") == "DB1.XETRA")
    assert db1.get("structure") == "oligopoly"
    assert "dax" in db1["sources"]


def test_market_rank_can_surface_deutsche_bank_without_sector_clue():
    universe = [
        {
            "name": "Deutsche Bank",
            "ticker": "DBK.XETRA",
            "sector": "financial services",
        },
        {"name": "Eli Lilly", "ticker": "LLY", "sector": "pharmaceutical"},
    ]
    up = [100 + i * 0.3 for i in range(300)]
    snaps = {"DBK.XETRA": trend_features(up), "LLY": trend_features(up)}
    text = "Branchenriese, die 200-Tage-Linie zurückerobert, Aktienrückkäufe."
    ranked = ms.rank(text, snaps, universe=universe, sector_filter=True)
    assert ranked["sectors"] == []
    assert {r["ticker"] for r in ranked["ranking"]} == {"DBK.XETRA", "LLY"}
