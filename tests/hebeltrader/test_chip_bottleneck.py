"""HT-201: the hidden chip ruler is the EDA/IP layer, not the famous equipment name."""

from scanner.hebeltrader.detective.chip_bottleneck import (
    apply_hidden_chip_bottleneck,
    teaser_wants_hidden_chip_bottleneck,
)
from scanner.hebeltrader.detective.metric_fingerprint import apply_metric_fingerprints
from scanner.hebeltrader.detective.research_plan import build_queries

HT201 = (
    "Der heimliche Herrscher über die globale Chipindustrie! "
    "Stellen Sie sich vor, ein Unternehmen wird in der Branche so unverzichtbar, "
    "dass seine Kunden kaum noch eine Wahl haben. "
    "Aufgrund der geringen Liquidität wird das Derivat erst ab Handelsbeginn in den USA "
    "um 14:30 Uhr quotiert."
)


def test_hidden_ruler_wording_is_detected():
    assert teaser_wants_hidden_chip_bottleneck(HT201)
    assert not teaser_wants_hidden_chip_bottleneck(
        "Der EUV-Lithographie-Monopolist der Chipindustrie lässt Kunden kaum eine Wahl."
    )


def test_eda_layer_ranks_above_equipment_foundry_and_chart_only_products():
    ranked = [
        {
            "asset_id": "asml",
            "evidence_score": 69,
            "hard_contradictions": [],
            "identity": {"name": "ASML"},
        },
        {
            "asset_id": "tsm",
            "evidence_score": 33,
            "hard_contradictions": [],
            "identity": {"name": "TSMC"},
        },
        {
            "asset_id": "nxpi",
            "evidence_score": 26,
            "hard_contradictions": [],
            "identity": {"name": "NXP Semiconductors"},
        },
        {
            "asset_id": "snps",
            "evidence_score": 24,
            "hard_contradictions": [],
            "identity": {"name": "Synopsys"},
        },
        {
            "asset_id": "cdns",
            "evidence_score": 24,
            "hard_contradictions": [],
            "identity": {"name": "Cadence Design Systems"},
        },
    ]
    summary = apply_hidden_chip_bottleneck(ranked, teaser_text=HT201)
    assert summary["status"] == "applied"
    leaders = {ranked[0]["identity"]["name"], ranked[1]["identity"]["name"]}
    assert leaders == {"Synopsys", "Cadence Design Systems"}
    assert ranked[0]["evidence_score"] == ranked[1]["evidence_score"]
    assert all(row["identity"]["name"] not in leaders for row in ranked[2:])


def test_hidden_chip_queries_lead_with_design_software_and_name_no_winner():
    queries = build_queries(HT201, [], [])
    blob = " ".join(queries).casefold()
    assert "chip design software" in blob
    assert "synopsys" not in blob
    assert "cadence" not in blob
    assert len(queries) <= 10


def test_impossible_operating_margin_does_not_crown_equipment_maker():
    ranked = [{"asset_id": "asml", "evidence_score": 23, "hard_contradictions": []}]
    docs = {
        "asml": [
            {
                "title": "ASML results",
                "text": "Operating margin was 134.5 percent. Markets grew 100 percent.",
            }
        ]
    }
    summary = apply_metric_fingerprints(ranked, docs, teaser_text=HT201)
    assert summary["status"] == "recorded_not_applied"
    assert ranked[0]["evidence_score"] == 23
    assert ranked[0]["metric_fingerprint"]["operating_margin_pct"] is None
