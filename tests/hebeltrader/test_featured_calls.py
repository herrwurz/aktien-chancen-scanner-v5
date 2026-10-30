from scanner.hebeltrader.detective.featured_calls import blocked_features, is_blocked
from scanner.hebeltrader.detective.market_screen import rank
from scanner.hebeltrader.detective.structure_screen import screen

FEATURED = {
    "kind": "hebeltrader_featured_calls_blocklist",
    "default_lookback_days": 180,
    "calls": [
        {
            "company": "Analog Devices",
            "ticker": "ADI",
            "featured_date": "2026-10-28",
            "featured_issue": "200/26",
            "source_case_id": "HT-001",
        },
        {
            "company": "Synopsys",
            "ticker": "SNPS",
            "featured_date": "2026-10-29",
            "featured_issue": "201/26",
            "source_case_id": "HT-020",
        },
        {
            "company": "Adidas",
            "ticker": "ADS",
            "featured_date": "2025-12-01",
            "featured_issue": "1/25",
            "source_case_id": "HT-OLD",
        },
    ],
}


def test_blocks_recent_features_before_as_of_within_lookback():
    blocked = blocked_features("2026-10-30", lookback_days=180, featured=FEATURED)
    assert blocked["status"] == "ok"
    assert {"ADI", "SNPS"} <= blocked["tickers"]
    assert "ADS" not in blocked["tickers"]  # older than 180-day lookback
    assert is_blocked({"name": "Analog Devices", "ticker": "ADI"}, blocked)
    assert not is_blocked({"name": "Eli Lilly", "ticker": "LLY"}, blocked)


def test_same_day_feature_is_not_blocked():
    blocked = blocked_features("2026-10-28", lookback_days=180, featured=FEATURED)
    assert "ADI" not in blocked["tickers"]
    assert "SNPS" not in blocked["tickers"]


def test_market_rank_skips_blocked_tickers():
    snaps = {
        "ADI": {
            "above_gd50": True,
            "above_gd200": True,
            "gd200_rising": True,
            "return_1y_pct": 20,
            "near_high_pct": -1,
            "breakout": True,
            "last": 1,
            "gd50": 1,
            "gd200": 1,
        },
        "LLY": {
            "above_gd50": True,
            "above_gd200": True,
            "gd200_rising": True,
            "return_1y_pct": 20,
            "near_high_pct": -1,
            "breakout": True,
            "last": 1,
            "gd50": 1,
            "gd200": 1,
        },
    }
    universe = [
        {
            "name": "Analog Devices",
            "ticker": "ADI",
            "sector": "semiconductor",
            "layer": "x",
            "structure": "oligopoly",
        },
        {
            "name": "Eli Lilly",
            "ticker": "LLY",
            "sector": "pharmaceutical",
            "layer": "y",
            "structure": "oligopoly",
        },
    ]
    blocked = blocked_features("2026-10-30", lookback_days=30, featured=FEATURED)
    result = rank(
        "200-Tage-Linie zurückerobert",
        snaps,
        universe=universe,
        blocked=blocked,
        sector_filter=False,
    )
    assert [row["ticker"] for row in result["ranking"]] == ["LLY"]


def test_structure_screen_skips_blocked_names():
    universe = [
        {
            "name": "Analog Devices",
            "ticker": "ADI",
            "sector": "semiconductor",
            "layer": "analog-mcu",
            "structure": "oligopoly",
        },
        {
            "name": "NXP Semiconductors",
            "ticker": "NXPI",
            "sector": "semiconductor",
            "layer": "analog-mcu",
            "structure": "oligopoly",
        },
    ]
    blocked = blocked_features("2026-10-30", lookback_days=30, featured=FEATURED)
    picked = screen("Halbleiter Chip", universe=universe, blocked=blocked)
    assert [a["ticker"] for a in picked] == ["NXPI"]
