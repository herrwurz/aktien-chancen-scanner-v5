from scanner.hebeltrader.detective.clues import extract_atomic_clues, extract_clues
from scanner.hebeltrader.detective.schemas import DetectiveRequest, SourceSpan
from tests.hebeltrader.test_detective_hypothesis_benchmark import _service

HEALTH = (
    "Rekordjagd im Gesundheitssektor – dieser Titel gehört ins Depot! "
    "Ein Gesundheitsriese mit prall gefüllter Kasse. "
    "Die Rallye hat begonnen – Wall-Street-Schwergewicht im Ausbruch! "
    "bis zu plus 1.761 Prozent"
)
FINANCE = (
    "zieht ein Finanzschwergewicht still und leise davon: Gewinne im Aufwind. "
    "bis zu plus 1.705 Prozent"
)
RETAIL = (
    "Wachstum ohne Ende – Handels-Gigant vor der Mega-Aufholjagd! "
    "Aufholjagd im Handel! bis zu 1.438 Prozent"
)


def test_real_teaser_lexicon_extracts_sector_and_geo():
    health = extract_clues(HEALTH)["structured"]
    assert "healthcare" in health["sectors"]
    assert "US" in health["countries"]
    finance = extract_clues(FINANCE)["structured"]
    assert "finance" in finance["sectors"]
    retail = extract_clues(RETAIL)["structured"]
    assert "retail" in retail["sectors"]


def test_handelsraum_does_not_count_as_retail():
    text = "Stille im Handelsraum. Dann ein Signal."
    assert "retail" not in extract_clues(text)["structured"]["sectors"]


def test_wall_street_health_does_not_fake_eu_likely_candidate():
    """EU-only seed cannot confirm a Wall-Street name; abstain rather than invent."""
    result = _service().analyze(
        DetectiveRequest(teaser_text=HEALTH, publication_at="2025-10-01T12:00:00+02:00")
    )
    assert result["identification"]["status"] in {"unresolved", "hypothesis_top3"}
    if result["identification"]["status"] == "hypothesis_top3":
        # Any hypothesis must be flagged for manual review and not auto-confirmed.
        assert result["identification"]["requires_manual_review"] is True
        assert result["automatic_confirmation"] is False
    # Must not claim a strict likely EU stock for an explicit Wall-Street teaser.
    assert result["identification"]["status"] != "likely_candidate"


def test_finance_and_retail_abstain_without_universe_coverage():
    for text in (FINANCE, RETAIL):
        result = _service().analyze(
            DetectiveRequest(teaser_text=text, publication_at="2025-10-01T12:00:00+02:00")
        )
        assert result["identification"]["status"] == "unresolved"
        assert result["identification"]["failure_code"] in {
            "retrieval_missed",
            "not_in_universe",
            "evidence_missing",
            "all_candidates_contradicted",
            "insufficiently_constrained",
        }
        clues = extract_atomic_clues(text, [SourceSpan(source_id="t", start=0, end=len(text))])
        assert any(clue.category == "sectors" for clue in clues)
