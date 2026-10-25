from datetime import UTC, datetime

from scanner.hebeltrader.detective.clue_enrichment import HeuristicClueEnricher
from scanner.hebeltrader.detective.clues import extract_atomic_clues
from scanner.hebeltrader.detective.eu_universe import load_eu_dach_assets
from scanner.hebeltrader.detective.hypothesis import decide_hypothesis
from scanner.hebeltrader.detective.hypothesis_source import HypothesisCandidateSource
from scanner.hebeltrader.detective.news_channel import FixtureNewsSearcher
from scanner.hebeltrader.detective.schemas import DetectiveRequest, SourceSpan
from scanner.hebeltrader.detective.service import DetectiveService

NOW = datetime(2025, 6, 5, 12, tzinfo=UTC)


def _news():
    return FixtureNewsSearcher(
        [
            {
                "source_id": "n1",
                "title": "DHL Group Logistik Übernahme Fantasie",
                "url": "fixture://dhl",
                "published_at": "2025-06-01T10:00:00+00:00",
                "themes": ["logistik", "übernahme", "logistics", "takeover"],
            },
            {
                "source_id": "n2",
                "title": "Kuehne + Nagel Logistik Schienen Übernahme",
                "url": "fixture://kn",
                "published_at": "2025-06-02T10:00:00+00:00",
                "themes": ["logistik", "schienen", "übernahme", "logistics"],
            },
        ]
    )


def test_hypothesis_mode_returns_top3_for_logistics_takeover_teaser():
    source = HypothesisCandidateSource(
        eu_assets=load_eu_dach_assets(),
        news_searcher=_news(),
    )
    service = DetectiveService(
        candidate_source=source,
        news_source=source,
        products=[],
        enricher=HeuristicClueEnricher(),
        clock=lambda: NOW,
    )
    result = service.analyze(
        DetectiveRequest(
            analysis_mode="hypothesis",
            teaser_text=(
                "Gewinne steigen, Synergien locken – Logistik-Schwergewicht im Ausbruch! "
                "Die Schienen glühen. Ein Logistik-Gigant ist ins Visier einer "
                "Übernahmefantasie geraten. Call-Optionsschein: bis zu plus 1.610 Prozent."
            ),
            publication_at=NOW,
        )
    )
    assert result["analysis_mode"] == "hypothesis"
    assert result["identification"]["status"] == "hypothesis_top3"
    assert 1 <= len(result["candidates"]) <= 3
    assert result["identification"]["failure_code"] is None
    assert result["search_queries"]
    names = [row["name"] for row in result["candidates"]]
    assert any("DHL" in name or "Kuehne" in name or "Hapag" in name for name in names)


def test_promo_only_teaser_stays_unresolved_in_hypothesis_mode():
    source = HypothesisCandidateSource(eu_assets=load_eu_dach_assets(), news_searcher=_news())
    service = DetectiveService(
        candidate_source=source, news_source=source, products=[], clock=lambda: NOW
    )
    result = service.analyze(
        DetectiveRequest(
            analysis_mode="hypothesis",
            teaser_text="Einmalige Chance mit 1.717 Prozent Rendite.",
            publication_at=NOW,
        )
    )
    assert result["identification"]["status"] == "unresolved"
    assert result["identification"]["failure_code"] == "insufficiently_constrained"
    assert result["candidates"] == []


def test_heuristic_enrichment_adds_rail_logistics_and_queries():
    text = "Die Schienen glühen bei der Übernahmefantasie."
    clues = extract_atomic_clues(text, [SourceSpan(source_id="t", start=0, end=len(text))])
    enriched = HeuristicClueEnricher().enrich(
        text, clues, [SourceSpan(source_id="t", start=0, end=len(text))]
    )
    assert any(clue.value == "logistics" for clue in enriched.extra_clues)
    assert enriched.search_queries


def test_swiss_logistics_hypothesis_prefers_kuehne():
    source = HypothesisCandidateSource(
        eu_assets=load_eu_dach_assets(),
        news_searcher=_news(),
    )
    service = DetectiveService(
        candidate_source=source, news_source=source, products=[], clock=lambda: NOW
    )
    result = service.analyze(
        DetectiveRequest(
            analysis_mode="hypothesis",
            teaser_text=(
                "Schweizer Logistik-Konzern mit Übernahmefantasie und steigenden Gewinnen."
            ),
            publication_at=NOW,
        )
    )
    assert result["identification"]["status"] == "hypothesis_top3"
    assert result["candidates"][0]["isin"] == "CH0025238863"


def test_decide_hypothesis_keeps_strict_path_separate():
    decision = decide_hypothesis([], "insufficiently_constrained", analysis_mode="strict")
    assert decision.status == "unresolved"
    assert decision.reason == "insufficiently_constrained"
