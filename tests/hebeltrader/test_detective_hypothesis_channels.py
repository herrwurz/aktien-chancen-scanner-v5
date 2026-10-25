import json
from datetime import UTC, datetime

from scanner.hebeltrader.detective.clue_enrichment import (
    HttpJsonLlmEnricher,
    LlmEnrichmentPayload,
)
from scanner.hebeltrader.detective.clues import extract_atomic_clues
from scanner.hebeltrader.detective.eu_universe import (
    assets_for_research_index,
    build_index_with_eu_universe,
    load_eu_dach_assets,
    load_openfigi_identity_records,
)
from scanner.hebeltrader.detective.news_channel import (
    FixtureNewsSearcher,
    NewsHit,
    match_news_to_assets,
)
from scanner.hebeltrader.detective.schemas import SourceSpan
from scanner.research_index.repository import ResearchIndex

NOW = datetime(2025, 6, 5, 12, tzinfo=UTC)


def test_llm_enrichment_falls_back_on_http_failure(httpx_mock=None):
    enricher = HttpJsonLlmEnricher("https://example.test/enrich")
    text = "Die Schienen glühen bei der Übernahmefantasie."
    clues = extract_atomic_clues(text, [SourceSpan(source_id="t", start=0, end=len(text))])
    # No live HTTP: post will fail and baseline heuristic must remain.
    result = enricher.enrich(text, clues, [SourceSpan(source_id="t", start=0, end=len(text))])
    assert result.provider == "heuristic"
    assert any(note.startswith("llm_enrichment_failed:") for note in result.notes)
    assert result.search_queries


def test_llm_payload_schema_rejects_invalid_shape():
    try:
        LlmEnrichmentPayload.model_validate({"search_queries": "not-a-list"})
        raised = False
    except Exception:
        raised = True
    assert raised


def test_llm_enrichment_merges_validated_queries(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "search_queries": ["rail logistics takeover", "ticker: DHL"],
                "synonyms": ["bahn logistik"],
                "notes": ["structured"],
            }

    def fake_post(*args, **kwargs):
        return FakeResponse()

    monkeypatch.setattr("scanner.hebeltrader.detective.clue_enrichment.httpx.post", fake_post)
    enricher = HttpJsonLlmEnricher("https://example.test/enrich")
    text = "Logistik Übernahme"
    clues = extract_atomic_clues(text, [SourceSpan(source_id="t", start=0, end=len(text))])
    result = enricher.enrich(text, clues, [SourceSpan(source_id="t", start=0, end=len(text))])
    assert result.provider == "llm_http_json"
    assert "rail logistics takeover" in result.search_queries
    assert "bahn logistik" in result.search_queries
    assert not any("ticker:" in query.casefold() for query in result.search_queries)


def test_openfigi_merge_and_index_build(tmp_path):
    openfigi = tmp_path / "openfigi.json"
    openfigi.write_text(
        json.dumps(
            {
                "records": [
                    {
                        "query_wkn": "555200",
                        "candidates": [
                            {
                                "name": "Deutsche Post DHL Group OpenFIGI",
                                "ticker": "DHL",
                                "isin": "DE0005552004",
                                "exchange": "GY",
                                "country": "DE",
                                "sector": "logistics",
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    figi_assets = load_openfigi_identity_records(openfigi)
    assert figi_assets and figi_assets[0].wkn == "555200"
    merged = assets_for_research_index(openfigi_path=openfigi)
    assert len(merged) >= len(load_eu_dach_assets())
    index_path = tmp_path / "eu-index.db"
    manifest = build_index_with_eu_universe(index_path, openfigi_path=openfigi)
    assert manifest.counts["assets"] >= 8
    index = ResearchIndex(index_path)
    assert index.coverage(NOW)["indexed_assets"] >= 8


def test_news_channel_maps_titles_to_universe():
    assets = load_eu_dach_assets()
    hits = [
        NewsHit(
            title="DHL Group Logistik Übernahme Fantasie",
            url="fixture://dhl",
            published_at=NOW,
            source_id="n1",
        )
    ]
    ranked = match_news_to_assets(hits, assets)
    assert ranked
    assert ranked[0][0].isin == "DE0005552004"
    searcher = FixtureNewsSearcher(
        [
            {
                "source_id": "n1",
                "title": "Kuehne + Nagel Logistik Schienen",
                "url": "fixture://kn",
                "published_at": "2025-06-02T10:00:00+00:00",
                "themes": ["logistik", "schienen"],
            }
        ]
    )
    found = searcher.search(["logistik übernahme"], start=datetime(2025, 5, 1, tzinfo=UTC), end=NOW)
    assert found and "Kuehne" in found[0].title
