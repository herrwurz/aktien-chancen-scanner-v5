from datetime import UTC, datetime

import pytest

from scanner.news import NewsItem
from scanner.research import AssetIdentity

NOW = datetime(2026, 10, 24, 12, tzinfo=UTC)


def asset(index, *, name=None, sector="insurance", available=NOW):
    return AssetIdentity(
        asset_type="stock",
        name=name or f"Company {index}",
        ticker=f"C{index}",
        cik="9999999999" if index == 0 else str(index),
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
    assert first.schema_version == 3
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


def test_legacy_index_schema_is_rejected_before_query(tmp_path):
    import json

    from scanner.research_index.builder import build_index
    from scanner.research_index.repository import ResearchIndex

    path = tmp_path / "index.db"
    build_index(path, assets=[asset(1)], events=[], facts=[], news=[])
    manifest_path = path.with_suffix(".db.manifest.json")
    manifest = json.loads(manifest_path.read_text())
    manifest["schema_version"] = 1
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="schema version"):
        ResearchIndex(path)


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
    ] == ["0000000001"]


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


def test_evidence_text_outranks_identity_words_and_funds_are_not_false_candidates(tmp_path):
    from scanner.research_index.builder import build_index
    from scanner.research_index.models import CandidateQuery
    from scanner.research_index.repository import ResearchIndex

    apple = asset(1, name="Apple Inc.", sector="technology").model_copy(
        update={"instrument_type": "operating_company", "instrument_type_status": "source_verified"}
    )
    funds = [
        asset(2, name="BlackRock MuniHoldings New Jersey Quality Fund", sector=None).model_copy(
            update={"instrument_type": "fund", "instrument_type_status": "inferred"}
        ),
        asset(3, name="BlackRock MuniYield New York Quality Fund", sector=None).model_copy(
            update={"instrument_type": "fund", "instrument_type_status": "inferred"}
        ),
    ]
    announcement = news(1, apple, title="Issuer unveils new product")
    build_index(
        tmp_path / "index.db", assets=[apple, *funds], events=[], facts=[], news=[announcement]
    )
    result = ResearchIndex(tmp_path / "index.db").candidates(
        CandidateQuery(text="new product", event_types=["guidance_raise"]),
        as_of=NOW,
        limit=50,
    )
    assert [row.identity.name for row in result.candidates] == ["Apple Inc."]
    assert result.candidates[0].retrieval_channels == ["evidence_text"]
    assert result.weak_match_count == 0


def test_weak_identity_text_alone_abstains_instead_of_forcing_identification(tmp_path):
    from scanner.research_index.builder import build_index
    from scanner.research_index.models import CandidateQuery
    from scanner.research_index.repository import ResearchIndex

    fund = asset(1, name="New Product Opportunities Fund", sector=None).model_copy(
        update={"instrument_type": "fund", "instrument_type_status": "inferred"}
    )
    build_index(tmp_path / "index.db", assets=[fund], events=[], facts=[], news=[])
    result = ResearchIndex(tmp_path / "index.db").candidates(
        CandidateQuery(text="new product"), as_of=NOW, limit=50
    )
    assert result.status == "unresolved"
    assert result.candidates == []
    assert result.weak_match_count == 1
    assert result.coverage_warnings == ["no_candidate_with_sufficient_evidence"]


def test_sec_universe_marks_name_based_fund_classification_as_inferred():
    from scanner.research_providers.sec_edgar import normalize_universe

    record = {
        "payload": {
            "fields": ["cik", "name", "ticker", "exchange"],
            "data": [
                [1, "Example Manufacturing Inc.", "EXM", "NYSE"],
                [2, "Example Income Fund", "EXF", "NYSE"],
            ],
        },
        "retrieved_at": NOW.isoformat(),
    }
    company, fund = normalize_universe(record)
    assert company.instrument_type == "unknown"
    assert company.instrument_type_status == "unknown"
    assert fund.instrument_type == "fund"
    assert fund.instrument_type_status == "inferred"
    assert fund.instrument_type_evidence == "sec_legal_name_pattern"


def test_news_revision_replaces_original_only_after_revision_is_available(tmp_path):
    from scanner.research_index.builder import build_index
    from scanner.research_index.models import CandidateQuery
    from scanner.research_index.repository import ResearchIndex

    company = asset(1, available=datetime(2025, 1, 1, tzinfo=UTC))
    original = news(
        1,
        company,
        title="Issuer raises guidance",
        available=datetime(2025, 2, 1, tzinfo=UTC),
    )
    correction = news(
        2,
        company,
        title="Correction: Issuer withdraws guidance",
        available=datetime(2025, 2, 3, tzinfo=UTC),
    ).model_copy(update={"revision_of_source_id": original.source_id})
    build_index(
        tmp_path / "index.db", assets=[company], events=[], facts=[], news=[original, correction]
    )
    index = ResearchIndex(tmp_path / "index.db")
    before = index.candidates(
        CandidateQuery(text="raises guidance"),
        as_of=datetime(2025, 2, 2, tzinfo=UTC),
    )
    after = index.candidates(
        CandidateQuery(text="raises guidance"),
        as_of=datetime(2025, 2, 4, tzinfo=UTC),
    )
    corrected = index.candidates(
        CandidateQuery(text="withdraws guidance"),
        as_of=datetime(2025, 2, 4, tzinfo=UTC),
    )
    assert [row.identity.cik for row in before.candidates] == ["0000000001"]
    assert after.status == "unresolved"
    assert [row.identity.cik for row in corrected.candidates] == ["0000000001"]


def test_fact_revision_is_point_in_time_and_does_not_rewrite_history(tmp_path):
    from scanner.research import CompanyFact
    from scanner.research_index.builder import build_index
    from scanner.research_index.repository import ResearchIndex

    company = asset(1, available=datetime(2025, 1, 1, tzinfo=UTC))

    def fact(fact_id, value, available, supersedes=None):
        return CompanyFact(
            fact_id=fact_id,
            asset=company,
            metric="Revenue",
            claim="reported_value",
            value=value,
            unit="USD",
            period_start="2024-01-01",
            period_end="2024-12-31",
            source_url=f"https://sec.example/{fact_id}",
            source_location="XBRL",
            published_at=available,
            source_available_at=available,
            retrieved_at=available,
            extraction_method="sec_xbrl",
            verification_status="source_verified",
            content_sha256=f"{value:064d}",
            supersedes_fact_id=supersedes,
        )

    original = fact("fact:original", 100, datetime(2025, 2, 1, tzinfo=UTC))
    revised = fact("fact:revised", 90, datetime(2025, 3, 1, tzinfo=UTC), supersedes="fact:original")
    build_index(
        tmp_path / "index.db", assets=[company], events=[], facts=[original, revised], news=[]
    )
    index = ResearchIndex(tmp_path / "index.db")
    before = index.evidence(company, as_of=datetime(2025, 2, 15, tzinfo=UTC), kinds={"fact"})
    after = index.evidence(company, as_of=datetime(2025, 3, 2, tzinfo=UTC), kinds={"fact"})
    assert [row["source_id"] for row in before["records"]] == ["fact:original"]
    assert [row["source_id"] for row in after["records"]] == ["fact:revised"]


def test_news_without_required_availability_timestamp_is_rejected():
    from scanner.news import NewsItem

    values = news(1, asset(1)).model_dump()
    values["source_available_at"] = None
    with pytest.raises(ValueError):
        NewsItem(**values)
