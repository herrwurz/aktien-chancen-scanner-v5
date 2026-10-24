from datetime import UTC, datetime

from scanner.news import NewsItem
from scanner.research import AssetIdentity

NOW = datetime(2026, 10, 24, 12, tzinfo=UTC)


def asset(index, *, name=None, sector="insurance", available=NOW):
    return AssetIdentity(
        asset_type="stock",
        name=name or f"Company {index}",
        ticker=f"C{index}",
        cik=str(index),
        country="US",
        sector=sector,
        retrieved_at=available,
        source_available_at=available,
    )


def news(index, identity, *, title="Insurer raises guidance", available=NOW):
    return NewsItem(
        source_id=f"news:{index}",
        source_type="PRIMARY",
        url=f"https://issuer.example/{index}",
        title=title,
        published_at=available,
        first_seen_at=available,
        retrieved_at=available,
        source_available_at=available,
        company_identifiers={"cik": [identity.cik]},
        event_type="guidance_raise",
        event_confidence="source_claim",
        evidence_status="issuer_publication",
        license_status="permitted_metadata",
        content_hash=f"{index:064x}",
        origin_id=f"issuer:{index}",
    )


def test_index_build_is_reproducible_and_sha_guarded(tmp_path):
    from scanner.research_index.builder import build_index
    from scanner.research_index.repository import ResearchIndex

    assets = [asset(1), asset(2)]
    first = build_index(tmp_path / "a.db", assets=assets, events=[], facts=[], news=[])
    second = build_index(
        tmp_path / "b.db", assets=list(reversed(assets)), events=[], facts=[], news=[]
    )
    assert first.payload_sha256 == second.payload_sha256
    assert first.counts == {"assets": 2, "events": 0, "facts": 0, "news": 0}
    assert ResearchIndex(tmp_path / "a.db").coverage(NOW)["indexed_assets"] == 2
    with (tmp_path / "a.db").open("ab") as handle:
        handle.write(b"tamper")
    try:
        ResearchIndex(tmp_path / "a.db")
    except ValueError as exc:
        assert "integrity" in str(exc)
    else:
        raise AssertionError("tampered index accepted")


def test_candidate_search_uses_entire_index_and_caps_at_fifty(tmp_path):
    from scanner.research_index.builder import build_index
    from scanner.research_index.models import CandidateQuery
    from scanner.research_index.repository import ResearchIndex

    assets = [asset(index) for index in range(75)]
    build_index(tmp_path / "index.db", assets=assets, events=[], facts=[], news=[])
    result = ResearchIndex(tmp_path / "index.db").candidates(
        CandidateQuery(sectors=["insurance"], countries=["US"]), as_of=NOW, limit=50
    )
    assert result.status == "ok"
    assert result.full_universe_size == 75
    assert result.matched_before_limit == 75
    assert len(result.candidates) == 50
    assert result.limit == 50


def test_candidate_search_excludes_news_and_identity_unavailable_as_of(tmp_path):
    from scanner.research_index.builder import build_index
    from scanner.research_index.models import CandidateQuery
    from scanner.research_index.repository import ResearchIndex

    old = asset(1, name="Old Insurer", available=datetime(2025, 1, 1, tzinfo=UTC))
    late = asset(2, name="Late Insurer", available=datetime(2025, 6, 1, tzinfo=UTC))
    late_news = news(2, late, available=datetime(2025, 6, 2, tzinfo=UTC))
    build_index(tmp_path / "index.db", assets=[old, late], events=[], facts=[], news=[late_news])
    index = ResearchIndex(tmp_path / "index.db")
    query = CandidateQuery(text="raises guidance", event_types=["guidance_raise"])
    before = index.candidates(query, as_of=datetime(2025, 5, 1, tzinfo=UTC), limit=50)
    after = index.candidates(query, as_of=datetime(2025, 7, 1, tzinfo=UTC), limit=50)
    assert before.candidates == []
    assert [row.identity.ticker for row in after.candidates] == ["C2"]


def test_unknown_sector_is_not_a_match_and_contradiction_is_reported(tmp_path):
    from scanner.research_index.builder import build_index
    from scanner.research_index.models import CandidateQuery
    from scanner.research_index.repository import ResearchIndex

    unknown = asset(1, sector=None)
    bank = asset(2, sector="banking")
    insurer = asset(3, sector="insurance")
    build_index(
        tmp_path / "index.db", assets=[unknown, bank, insurer], events=[], facts=[], news=[]
    )
    result = ResearchIndex(tmp_path / "index.db").candidates(
        CandidateQuery(sectors=["insurance"]), as_of=NOW, limit=50
    )
    rows = {row.identity.ticker: row for row in result.candidates}
    assert rows["C3"].confirmed == ["sector:insurance"]
    assert rows["C1"].unknown == ["sector:insurance"]
    assert rows["C2"].contradicted == ["sector:insurance"]
    assert [row.identity.ticker for row in result.candidates][:2] == ["C3", "C1"]


def test_unconstrained_and_out_of_index_search_abstain(tmp_path):
    from scanner.research_index.builder import build_index
    from scanner.research_index.models import CandidateQuery
    from scanner.research_index.repository import ResearchIndex

    build_index(tmp_path / "index.db", assets=[asset(1)], events=[], facts=[], news=[])
    index = ResearchIndex(tmp_path / "index.db")
    broad = index.candidates(CandidateQuery(), as_of=NOW, limit=50)
    missing = index.candidates(
        CandidateQuery(text="nonexistent quantum banana"), as_of=NOW, limit=50
    )
    assert broad.status == "insufficiently_constrained"
    assert missing.status == "unresolved"
    assert missing.candidates == []


def test_same_company_name_does_not_assign_an_unproven_identifier(tmp_path):
    from scanner.research_index.builder import build_index
    from scanner.research_index.models import CandidateQuery
    from scanner.research_index.repository import ResearchIndex

    first = asset(1, name="Example Holdings")
    second = asset(2, name="Example Holdings")
    mention = news(1, first, title="Example Holdings wins contract")
    build_index(tmp_path / "index.db", assets=[first, second], events=[], facts=[], news=[mention])
    result = ResearchIndex(tmp_path / "index.db").candidates(
        CandidateQuery(text="wins contract", event_types=["guidance_raise"]), as_of=NOW, limit=50
    )
    assert [
        row.identity.cik for row in result.candidates if "event:guidance_raise" in row.confirmed
    ] == ["1"]


def test_detective_uses_full_index_retrieval_before_top_three(tmp_path):
    from scanner.hebeltrader.detective.index_source import IndexCandidateSource
    from scanner.hebeltrader.detective.schemas import DetectiveRequest
    from scanner.hebeltrader.detective.service import DetectiveService
    from scanner.research_index.builder import build_index
    from scanner.research_index.repository import ResearchIndex

    assets = [asset(index, sector="banking") for index in range(59)]
    target = asset(99, name="Target Insurance", sector="insurance")
    build_index(tmp_path / "index.db", assets=[*assets, target], events=[], facts=[], news=[])
    source = IndexCandidateSource(ResearchIndex(tmp_path / "index.db"))
    report = DetectiveService(
        candidate_source=source,
        news_source=source,
        products=[],
        research_mode="cached_research",
    ).analyze(DetectiveRequest(teaser_text="US-Versicherer", publication_at=NOW))
    assert report["candidates"][0]["ticker"] == "C99"
    assert report["candidate_source"]["coverage"]["full_universe_size"] == 60
    assert report["candidate_source"]["coverage"]["stage_a_limit"] == 50


def test_shared_research_service_exposes_index_without_strategy_signal(tmp_path):
    from scanner.research_index.builder import build_index
    from scanner.research_index.models import CandidateQuery
    from scanner.research_index.repository import ResearchIndex
    from scanner.research_service import IndexedResearchService

    build_index(tmp_path / "index.db", assets=[asset(1)], events=[], facts=[], news=[])
    service = IndexedResearchService(ResearchIndex(tmp_path / "index.db"))
    candidates = service.candidates(CandidateQuery(sectors=["insurance"]), as_of=NOW)
    assert candidates["strategy_decision"] is None
    assert candidates["strategy_consumers"] == [
        "HEBELTRADER_DETECTIVE",
        "short_term_trading",
        "medium_term_investing",
    ]
    availability = service.strategy_availability(asset(1), as_of=NOW)
    assert availability["short_term_trading"]["decision_status"] == "unavailable"
    assert availability["medium_term_investing"]["decision_status"] == "unavailable"


def test_configured_indexed_research_mode_uses_same_cli_service_factory(tmp_path):
    from scanner.config import Settings
    from scanner.hebeltrader.detective.factory import build_detective
    from scanner.hebeltrader.detective.schemas import DetectiveRequest
    from scanner.research_index.builder import build_index

    path = tmp_path / "index.db"
    build_index(path, assets=[asset(1)], events=[], facts=[], news=[])
    settings = Settings(
        _env_file=None,
        detective_research_mode="indexed_research",
        detective_research_index=path,
    )
    report = build_detective(settings).analyze(
        DetectiveRequest(teaser_text="US-Versicherer", publication_at=NOW)
    )
    assert report["research_mode"] == "indexed_research"
    assert report["candidates"][0]["ticker"] == "C1"
    assert report["candidate_source"]["coverage"]["full_universe_size"] == 1


def test_index_stage_b_receives_time_valid_news_evidence(tmp_path):
    from scanner.hebeltrader.detective.index_source import IndexCandidateSource
    from scanner.hebeltrader.detective.schemas import DetectiveRequest
    from scanner.hebeltrader.detective.service import DetectiveService
    from scanner.research_index.builder import build_index
    from scanner.research_index.repository import ResearchIndex

    target = asset(1, name="Evidence Corp", sector=None)
    other = asset(2, name="Other Corp", sector=None)
    announcement = news(1, target, title="Evidence Corp raises guidance")
    build_index(
        tmp_path / "index.db",
        assets=[target, other],
        events=[],
        facts=[],
        news=[announcement],
    )
    source = IndexCandidateSource(ResearchIndex(tmp_path / "index.db"))
    report = DetectiveService(
        candidate_source=source,
        news_source=source,
        products=[],
        research_mode="indexed_research",
    ).analyze(
        DetectiveRequest(teaser_text="US Unternehmen, Prognose angehoben", publication_at=NOW)
    )
    assert report["candidates"][0]["ticker"] == "C1"
    assert {row["value"] for row in report["candidates"][0]["supporting_clues"]} >= {
        "US",
        "guidance_raise",
    }
    assert report["candidates"][0]["eligible_evidence"][0]["source_id"] == "news:1"
