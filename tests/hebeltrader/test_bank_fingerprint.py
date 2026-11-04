"""HT-202: a capital-base teaser must not be led by an industrial chart/ARR hit."""

from scanner.hebeltrader.detective.bank_fingerprint import (
    apply_bank_capital_fingerprints,
    teaser_wants_bank_capital,
)
from scanner.hebeltrader.detective.research_plan import build_queries
from scanner.hebeltrader.detective.resolution import draft_error_analysis

HT202 = (
    "Zum dritten Mal in Folge melden die Bücher Rekordgewinne. "
    "Die Kapitalbasis ist so stark wie lange nicht, Dividenden und Aktienrückkäufe "
    "rücken in greifbare Nähe. Die 200-Tage-Linie wurde zurückerobert."
)


def test_capital_base_language_is_a_bank_teaser():
    assert teaser_wants_bank_capital(HT202)
    assert not teaser_wants_bank_capital("US-Versorger mit Abnahmeverträgen und Golden Cross")


def test_bank_ranks_above_industrial_chart_leader():
    ranked = [
        {
            "asset_id": "sie",
            "evidence_score": 60,
            "hard_contradictions": [],
            "identity": {"name": "Siemens AG"},
        },
        {
            "asset_id": "vow",
            "evidence_score": 30,
            "hard_contradictions": [],
            "identity": {"name": "Volkswagen Group"},
        },
        {
            "asset_id": "alv",
            "evidence_score": 27,
            "hard_contradictions": [],
            "identity": {"name": "Allianz SE"},
        },
        {
            "asset_id": "dbk",
            "evidence_score": 8,
            "hard_contradictions": [],
            "identity": {"name": "Deutsche Bank AG", "ticker": "DB"},
        },
    ]
    summary = apply_bank_capital_fingerprints(ranked, teaser_text=HT202)
    assert summary["status"] == "applied"
    assert ranked[0]["identity"]["name"] == "Deutsche Bank AG"
    assert ranked[0]["evidence_score"] > ranked[1]["evidence_score"]
    assert any(row["asset_id"] == "sie" and row["bank_fingerprint"]["delta"] < 0 for row in ranked)


def test_capital_base_queries_search_banks_without_naming_a_winner():
    queries = build_queries(HT202, [], [])
    blob = " ".join(queries).casefold()
    assert "cet1" in blob or "tier 1" in blob
    assert "deutsche bank" not in blob
    assert "siemens" not in blob


def test_error_text_explains_unconfirmed_capital_base_and_checked_bank():
    report = {
        "candidates": [
            {
                "asset_id": "sie",
                "identity": {"name": "Siemens AG"},
                "ranking_reason": "Chart-Clue am Kandidaten bestätigt.",
                "metric_fingerprint": {
                    "bonus": 50,
                    "arr_billions": 11.0,
                    "segment_growth": {"segment": "markets", "pct": 50.0},
                },
                "evidence_matrix": [
                    {
                        "quote": "Kapitalbasis ist so stark wie lange nicht",
                        "status": "unknown",
                        "reason": "unsupported_by_archived_sources",
                    },
                    {
                        "quote": "200-Tage-Linie zurückerobert",
                        "status": "confirmed",
                        "reason": "eod_price_above_sma200_pit",
                    },
                ],
            }
        ],
        "checked_candidates": [
            {
                "asset_id": "dbk",
                "identity": {"name": "Deutsche Bank AG"},
                "evidence_matrix": [
                    {
                        "quote": "Kapitalbasis ist so stark wie lange nicht",
                        "status": "unknown",
                        "reason": "unsupported_by_archived_sources",
                    },
                    {
                        "quote": "200-Tage-Linie zurückerobert",
                        "status": "contradicted",
                        "reason": "eod_price_below_sma200_pit",
                    },
                ],
            }
        ],
    }
    text = draft_error_analysis(report, resolved_name="Deutsche Bank", resolved_asset_id="dbk")
    assert text.startswith("Abweichung:")
    assert "nicht unter den Top-3" in text
    assert "Kapitalbasis ist so stark wie lange nicht" in text
    assert "nicht belegt" in text
    assert "Kurs unter der 200-Tage-Linie" in text
    assert "jährlich wiederkehrende Erlöse" in text
    assert "Deutsche Bank AG wurde geprüft" in text
    assert "Score" not in text
