"""HT-200: the profit machine behind the famous AI names is the analog layer."""

from scanner.hebeltrader.detective.background_chip import (
    apply_background_chip_profit,
    teaser_wants_background_chip_profit,
)
from scanner.hebeltrader.detective.research_plan import build_queries
from scanner.hebeltrader.detective.structure_screen import screen
from scanner.hebeltrader.detective.utility_fingerprint import (
    apply_utility_fingerprints,
    teaser_wants_utility_fingerprint,
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


def _row(asset_id, name, score):
    return {
        "asset_id": asset_id,
        "evidence_score": score,
        "hard_contradictions": [],
        "identity": {"name": name},
    }


def test_background_profit_wording_is_detected_and_hidden_ruler_is_not():
    assert teaser_wants_background_chip_profit(HT200)
    hidden = (
        "Der heimliche Herrscher über die globale Chipindustrie. Kunden haben kaum noch eine Wahl."
    )
    assert not teaser_wants_background_chip_profit(hidden)
    assert not teaser_wants_background_chip_profit(
        "Halbleiter-Schwergewicht mit Rekordumsatz, ohne den Blick weg von den KI-Namen."
    )


def test_analog_layer_ties_ahead_of_the_names_everyone_stares_at():
    ranked = [
        _row("tsm", "TSMC", 31),
        _row("snps", "Synopsys", 14),
        _row("asml", "ASML Holding N.V.", 13),
        _row("adi", "Analog Devices", 8),
        _row("txn", "Texas Instruments", 8),
        _row("nxpi", "NXP Semiconductors", 8),
    ]
    summary = apply_background_chip_profit(ranked, teaser_text=HT200)
    assert summary["status"] == "applied"
    leaders = {row["identity"]["name"] for row in ranked if row["evidence_score"] == 44}
    assert leaders == {"Analog Devices", "Texas Instruments", "NXP Semiconductors"}
    assert ranked[0]["evidence_score"] == ranked[2]["evidence_score"] == 44
    order = [row["identity"]["name"] for row in ranked]
    assert order.index("Synopsys") == 3
    assert order.index("TSMC") > order.index("Synopsys")
    assert order.index("ASML Holding N.V.") > order.index("Synopsys")
    assert "analog devices" not in HT200.casefold()


def test_queries_and_shortlist_cover_the_analog_layer_without_naming_a_winner():
    queries = build_queries(HT200, [], [])
    blob = " ".join(queries).casefold()
    assert "analog mixed-signal" in blob
    assert "analog devices" not in blob
    assert "texas instruments" not in blob
    names = {asset["name"] for asset in screen(HT200)}
    assert {"Analog Devices", "Texas Instruments", "NXP Semiconductors"} <= names


def test_chip_data_center_wording_does_not_award_a_utility_bonus():
    assert not teaser_wants_utility_fingerprint(HT200)
    ranked = [_row("tsm", "TSMC", 15)]
    docs = {
        "tsm": [
            {
                "title": "TSMC update",
                "text": "Data center demand and a $100 billion capital investment plan.",
            }
        ]
    }
    summary = apply_utility_fingerprints(ranked, docs, teaser_text=HT200)
    assert summary["status"] == "skipped_no_utility_cues"
    assert ranked[0]["evidence_score"] == 15
