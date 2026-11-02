"""Golden-Cross teaser claims are confirmed/contradicted from PIT chart features."""

from scanner.hebeltrader.detective.investigation import (
    _apply_golden_cross_matrix,
    _teaser_claims_golden_cross,
)
from scanner.hebeltrader.detective.market_screen import match_score, teaser_chart_clues


def test_teaser_detects_german_and_english_golden_cross():
    assert _teaser_claims_golden_cross(
        "Charttechnisch hat sich zudem ein kraftvolles Golden Cross gebildet."
    )
    assert "golden_cross" in teaser_chart_clues("ein goldenes Kreuz im Tageschart")
    assert not _teaser_claims_golden_cross("nur ein Aufwärtstrend ohne Kreuz")


def test_matrix_confirms_when_chart_shows_recent_cross():
    ranked = [
        {
            "chart": {"status": "ok", "golden_cross": True},
            "evidence_matrix": [
                {
                    "clue_id": "ai:gc",
                    "status": "unknown",
                    "reason": "unsupported_by_archived_sources",
                    "quote": "Charttechnisch hat sich zudem ein kraftvolles Golden Cross gebildet.",
                    "category": "semantic_fact",
                }
            ],
            "unknown_clues": ["ai:gc"],
        }
    ]
    _apply_golden_cross_matrix(
        ranked, "Charttechnisch hat sich zudem ein kraftvolles Golden Cross gebildet."
    )
    cell = ranked[0]["evidence_matrix"][0]
    assert cell["status"] == "confirmed"
    assert cell["reason"] == "eod_golden_cross_within_20d_pit"
    assert ranked[0]["unknown_clues"] == []


def test_matrix_contradicts_absent_recent_cross():
    ranked = [
        {
            "chart": {"status": "ok", "golden_cross": False},
            "evidence_matrix": [
                {
                    "clue_id": "ai:gc",
                    "status": "unknown",
                    "quote": "Golden Cross gebildet.",
                    "category": "semantic_fact",
                }
            ],
            "unknown_clues": ["ai:gc"],
        }
    ]
    _apply_golden_cross_matrix(ranked, "Golden Cross gebildet.")
    assert ranked[0]["evidence_matrix"][0]["status"] == "contradicted"
    assert ranked[0]["evidence_matrix"][0]["reason"] == "eod_no_recent_golden_cross_pit"


def test_match_score_rewards_golden_cross_clue():
    features = {
        "above_gd50": True,
        "above_gd200": True,
        "gd200_rising": False,
        "return_1y_pct": 0,
        "near_high_pct": -1,
        "breakout": False,
        "golden_cross": True,
    }
    with_clue = match_score(features, ["golden_cross"])
    without = match_score({**features, "golden_cross": False}, ["golden_cross"])
    assert with_clue > without
