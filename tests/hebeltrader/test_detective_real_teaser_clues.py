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


def test_wall_street_health_hypotheses_include_jnj_not_likely():
    result = _service().analyze(
        DetectiveRequest(teaser_text=HEALTH, publication_at="2025-10-01T12:00:00+02:00")
    )
    assert result["identification"]["status"] == "hypothesis_top3"
    assert result["identification"]["requires_manual_review"] is True
    assert result["automatic_confirmation"] is False
    assert result["identification"]["status"] != "likely_candidate"
    top_ids = [row["asset_id"] for row in result["candidates"][:3]]
    assert "cik:0000200406" in top_ids  # JNJ


def test_finance_and_retail_include_gold_peers():
    cases = [
        (FINANCE, "cik:0000019617"),  # JPM
        (RETAIL, "cik:0000909832"),  # COST
    ]
    for text, expected in cases:
        result = _service().analyze(
            DetectiveRequest(teaser_text=text, publication_at="2025-10-01T12:00:00+02:00")
        )
        assert result["identification"]["status"] == "hypothesis_top3"
        top_ids = [row["asset_id"] for row in result["candidates"][:3]]
        assert expected in top_ids
        clues = extract_atomic_clues(text, [SourceSpan(source_id="t", start=0, end=len(text))])
        assert any(clue.category == "sectors" for clue in clues)
