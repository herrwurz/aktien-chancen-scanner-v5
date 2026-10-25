from scanner.hebeltrader.detective.clues import extract_atomic_clues, extract_clues
from scanner.hebeltrader.detective.schemas import DetectiveRequest, SourceSpan
from tests.hebeltrader.test_detective_hypothesis_benchmark import _service


def test_deutscher_adjective_maps_to_de_country():
    text = "Deutscher Logistik-Gigant: Übernahmefantasie und steigende Gewinne."
    legacy = extract_clues(text)
    assert "DE" in legacy["structured"]["countries"]
    clues = extract_atomic_clues(text, [SourceSpan(source_id="t", start=0, end=len(text))])
    assert any(
        clue.category == "countries" and clue.value == "DE" and clue.polarity == "asserted"
        for clue in clues
    )


def test_german_logistics_hypothesis_prefers_de_over_ch():
    result = _service().analyze(
        DetectiveRequest(
            teaser_text=(
                "Deutscher Logistik-Gigant: Übernahmefantasie und steigende Gewinne "
                "– Call mit Hebel. Bis zu plus 900 Prozent."
            ),
            publication_at="2025-06-05T12:00:00Z",
        )
    )
    assert result["identification"]["status"] == "hypothesis_top3"
    top = result["candidates"][0]
    assert top["asset_id"] != "isin:CH0025238863"
    assert (top.get("country") or top.get("identity", {}).get("country")) == "DE"
    assert "isin:DE0005552004" in [row["asset_id"] for row in result["candidates"][:3]]
