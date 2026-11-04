"""Sector shortlist is a filter. Layer membership does not score."""

from scanner.hebeltrader.detective.clue_matrix import (
    apply_clue_matrix,
    eligible_shortlist,
    shortlist_queries,
)

HT200 = (
    "Aufgrund der geringen Liquidität an den deutschen Börsen wird das Derivat "
    "erst ab Handelsbeginn in den USA um 14:30 Uhr fortlaufend quotiert. "
    "Während alle auf die großen KI-Namen starren, wächst im Hintergrund ein "
    "Halbleiter-Schwergewicht zur wahren Gewinnmaschine! Der Umsatz hat "
    "Rekordniveau erreicht, der Gewinn je Aktie ist kräftig explodiert und die "
    "Bruttomarge gehört zur absoluten Weltklasse. Auch der freie Cashflow "
    "sprudelt. Dazu kommen Zukäufe bei KI-Rechenzentren und Robotik."
)


def test_shortlist_keeps_every_analog_name_and_searches_them():
    names = [asset["name"] for asset in eligible_shortlist(HT200)]
    for analog in ("Texas Instruments", "Analog Devices", "NXP Semiconductors"):
        assert analog in names
    assert "Infineon Technologies" not in names
    queries = shortlist_queries(HT200, eligible_shortlist(HT200), limit=8)
    assert any("Analog Devices" in query for query in queries)
    assert all("analog-mcu" not in query for query in queries)


def test_layer_bonus_is_removed_and_not_applied_twice():
    ranked = [
        {
            "asset_id": "adi",
            "evidence_score": 46,
            "hard_contradictions": [],
            "identity": {"name": "Analog Devices"},
            "background_chip": {"role": "analog", "layer": "analog-mcu", "delta": 36},
            "evidence_matrix": [
                {"status": "confirmed", "category": "financial_metric", "quote": "Bruttomarge"}
            ],
        },
        {
            "asset_id": "nvda",
            "evidence_score": 4,
            "hard_contradictions": [],
            "identity": {"name": "NVIDIA"},
            "background_chip": {"role": "obvious_ai", "layer": "ai-processors", "delta": -36},
        },
    ]
    summary = apply_clue_matrix(ranked, teaser_text=HT200)
    assert summary["layer_points"] == 0
    assert ranked[0]["asset_id"] == "nvda"
    assert ranked[0]["evidence_score"] == 40
    assert ranked[1]["evidence_score"] == 10
    assert ranked[1]["clue_matrix"]["layer_points"] == 0
    assert ranked[1]["clue_matrix"]["confirmed"] == 1
    assert ranked[1]["clue_matrix"]["layer"] == "analog-mcu"
    apply_clue_matrix(ranked, teaser_text=HT200)
    assert ranked[0]["evidence_score"] == 40
    assert ranked[1]["evidence_score"] == 10


def test_unrelated_sector_does_not_pull_chip_names():
    names = {asset["name"] for asset in eligible_shortlist("Der Versicherer hebt die Prognose an.")}
    assert names
    assert "Analog Devices" not in names
