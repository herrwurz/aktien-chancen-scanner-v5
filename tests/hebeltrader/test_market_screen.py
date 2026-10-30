from datetime import date

from scanner.hebeltrader.detective import market_screen as ms

UP = [100 + i * 0.3 for i in range(300)]
DOWN = [300 - i * 0.5 for i in range(300)]
UNIVERSE = [
    {"name": "Up Bank", "sector": "financial services", "ticker": "UPB"},
    {"name": "Down Bank", "sector": "financial services", "ticker": "DNB"},
    {"name": "Up Chip", "sector": "semiconductor", "ticker": "UPC"},
    {"name": "No Data", "sector": "financial services", "ticker": "NOD"},
]
TEXT_202 = "Charttechnisch hat die Aktie die 200-Tage-Linie zurückerobert, ein zusätzliches Kaufsignal."


def test_clues_are_detected_from_teaser():
    assert teaser_clues(TEXT_202) == ["above_gd200", "breakout"]
    assert teaser_clues("Nach der Korrektur ... seit Jahren kontinuierlich nach oben") == [
        "correction",
        "steady_uptrend",
    ]


def teaser_clues(text):
    return ms.teaser_chart_clues(text)


def test_rank_prefers_matching_chart_and_skips_missing_snapshots():
    fetch = {"UPB": UP, "DNB": DOWN, "UPC": UP}.get
    snaps = ms.export_snapshots(universe=UNIVERSE, fetch=fetch, today=date(2026, 10, 30))
    assert snaps["as_of"] == "2026-10-30" and set(snaps["snapshots"]) == {"UPB", "DNB", "UPC"}
    result = ms.rank(TEXT_202, snaps["snapshots"], universe=UNIVERSE)
    assert [r["ticker"] for r in result["ranking"]] == ["UPB", "UPC", "DNB"]
    assert result["ranking"][0]["score"] > result["ranking"][-1]["score"]


def test_sector_filter_applies_only_when_teaser_names_a_sector():
    snaps = ms.export_snapshots(universe=UNIVERSE, fetch={"UPB": UP, "UPC": UP}.get)["snapshots"]
    banks = ms.rank("Ein Bank mit Ausbruch", snaps, universe=UNIVERSE)
    assert [r["ticker"] for r in banks["ranking"]] == ["UPB"]
    assert len(ms.rank("Ausbruch", snaps, universe=UNIVERSE)["ranking"]) == 2
