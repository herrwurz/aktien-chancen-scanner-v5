import json
from datetime import UTC, datetime

import httpx
import pytest

from scanner.research import AssetIdentity, CompanyEvent, CompanyFact, EvidenceRecord
from scanner.research_facts import extract_sec_company_facts
from scanner.research_snapshot import load_snapshot, write_snapshot

NOW = datetime(2026, 10, 24, 12, tzinfo=UTC)


def sec_record(payload, sha="a" * 64):
    return {
        "payload": payload,
        "retrieved_at": NOW.isoformat(),
        "raw_sha256": sha,
        "source_reference": "https://data.sec.gov/api/xbrl/companyfacts/CIK0000000042.json",
    }


def companyfacts(values):
    return {
        "cik": 42,
        "entityName": "Example Corp",
        "facts": {
            "us-gaap": {
                "NetIncomeLoss": {
                    "label": "Net Income (Loss)",
                    "description": "Net income attributable to the entity.",
                    "units": {"USD": values},
                }
            }
        },
    }


def fact_row(*, value, start, end, filed, accn, fy, fp="Q1", form="10-Q"):
    return {
        "val": value,
        "start": start,
        "end": end,
        "filed": filed,
        "accn": accn,
        "fy": fy,
        "fp": fp,
        "form": form,
    }


def test_sec_filing_form_alone_does_not_claim_positive_result():
    facts = extract_sec_company_facts(
        sec_record(
            companyfacts(
                [
                    fact_row(
                        value=8,
                        start="2025-01-01",
                        end="2025-03-31",
                        filed="2025-05-01",
                        accn="a",
                        fy=2025,
                    )
                ]
            )
        ),
        AssetIdentity(asset_type="stock", name="Example Corp", ticker="EX", cik="42"),
    )
    assert len(facts) == 1
    assert facts[0].verification_status == "unknown"
    assert facts[0].comparison_value is None
    assert facts[0].claim == "reported_value"


def test_comparable_xbrl_periods_prove_increase_without_calling_it_surprise():
    facts = extract_sec_company_facts(
        sec_record(
            companyfacts(
                [
                    fact_row(
                        value=10,
                        start="2024-01-01",
                        end="2024-03-31",
                        filed="2024-05-01",
                        accn="prior",
                        fy=2024,
                    ),
                    fact_row(
                        value=15,
                        start="2025-01-01",
                        end="2025-03-31",
                        filed="2025-05-01",
                        accn="current",
                        fy=2025,
                    ),
                ]
            )
        ),
        AssetIdentity(asset_type="stock", name="Example Corp", ticker="EX", cik="42"),
    )
    current = next(row for row in facts if row.value == 15)
    assert current.claim == "year_over_year_increase"
    assert current.comparison_value == 10
    assert current.verification_status == "source_verified"
    assert current.extraction_method == "sec_xbrl_exact_duration_fiscal_period_v1"


def test_snapshot_hash_and_raw_provenance_are_checked(tmp_path):
    raw = tmp_path / "raw" / "source.json"
    raw.parent.mkdir()
    raw.write_bytes(b'{"real":"archived"}')
    identity = AssetIdentity(asset_type="stock", name="Example", ticker="EX", cik="42")
    path = tmp_path / "snapshot.json"
    write_snapshot(
        path,
        assets=[identity],
        events=[],
        facts=[],
        coverage={"kind": "real_archived", "candidate_selection": "stable_sha256_v1"},
        raw_sources=[raw],
        generated_at=datetime(2025, 10, 24, 12, tzinfo=UTC),
    )
    snapshot = load_snapshot(path)
    assert snapshot["coverage"]["kind"] == "real_archived"
    raw.write_bytes(b'{"substituted":true}')
    with pytest.raises(ValueError, match="raw source integrity"):
        load_snapshot(path)


def test_snapshot_rejects_tampered_normalized_content(tmp_path):
    raw = tmp_path / "raw.json"
    raw.write_text("{}")
    path = tmp_path / "snapshot.json"
    write_snapshot(
        path,
        assets=[],
        events=[],
        facts=[],
        coverage={"kind": "fixture"},
        raw_sources=[raw],
        generated_at=NOW,
    )
    data = json.loads(path.read_text())
    data["payload"]["coverage"]["kind"] = "real_archived"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="snapshot integrity"):
        load_snapshot(path)


def test_missing_historical_identity_timestamp_is_not_time_verified():
    identity = AssetIdentity(
        asset_type="stock",
        name="Today Known Inc",
        ticker="NOW",
        retrieved_at=NOW,
    )
    assert identity.historically_available_at(datetime(2025, 1, 1, tzinfo=UTC)) is False


def test_company_fact_requires_source_and_location():
    with pytest.raises(ValueError):
        CompanyFact(
            fact_id="bad",
            asset=AssetIdentity(asset_type="stock", name="Example"),
            metric="net_income",
            claim="reported_value",
            value=1,
            unit="USD",
            period_start="2025-01-01",
            period_end="2025-03-31",
            published_at=NOW,
            source_url="",
            source_location="",
            extraction_method="sec_xbrl_v1",
            verification_status="unknown",
        )


def test_sec_client_archives_companyfacts_and_10q_is_only_document_event(tmp_path):
    from scanner.research_providers.sec_edgar import (
        SecEdgarClient,
        normalize_submission_events,
    )

    calls = []

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(200, json=companyfacts([]))

    client = SecEdgarClient(
        tmp_path,
        user_agent="Scanner research@example.org",
        allow_network=True,
        max_requests=1,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        now=lambda: NOW,
        sleeper=lambda _: None,
    )
    record = client.fetch("companyfacts", "42")
    cached = client.fetch("companyfacts", "42")
    assert record["raw_sha256"] == cached["raw_sha256"]
    assert cached["cache_hit"] is True
    assert calls == ["https://data.sec.gov/api/xbrl/companyfacts/CIK0000000042.json"]

    identity = AssetIdentity(asset_type="stock", name="Example", ticker="EX", cik="42")
    events = normalize_submission_events(
        {
            "payload": {
                "filings": {
                    "recent": {
                        "accessionNumber": ["0000000042-25-000001"],
                        "filingDate": ["2025-05-01"],
                        "acceptanceDateTime": ["2025-05-01T16:30:00Z"],
                        "form": ["10-Q"],
                        "items": [""],
                    }
                }
            },
            "retrieved_at": NOW.isoformat(),
            "raw_sha256": "b" * 64,
        },
        identity,
    )
    assert events[0].category == "regulatory_filing"
    assert events[0].facts["document_type"] == "10-Q"
    assert "positive" not in events[0].facts


def make_cached_snapshot(tmp_path):
    raw = tmp_path / "raw.json"
    raw.write_text('{"source":"SEC"}')
    identity = AssetIdentity(
        asset_type="stock",
        name="Example Corp",
        ticker="EX",
        cik="42",
        country="US",
        sector="insurance",
        retrieved_at=NOW,
    )
    evidence = EvidenceRecord(
        source_id="sec:test",
        url="https://www.sec.gov/test",
        title="SEC filing 8-K",
        published_at=datetime(2025, 5, 1, 16, tzinfo=UTC),
        retrieved_at=NOW,
        effective_at=datetime(2025, 5, 1, 16, tzinfo=UTC),
        source_available_at=datetime(2025, 5, 1, 16, tzinfo=UTC),
        source_kind="regulatory",
        facts={"document_type": "8-K"},
        content_sha256="a" * 64,
    )
    event = CompanyEvent(
        event_id="sec:test",
        asset=identity,
        category="regulatory_filing",
        headline="Example filing",
        published_at=evidence.published_at,
        retrieved_at=NOW,
        effective_at=evidence.effective_at,
        evidence=evidence,
    )
    snapshot = tmp_path / "snapshot.json"
    write_snapshot(
        snapshot,
        assets=[identity],
        events=[event],
        facts=[],
        coverage={
            "kind": "real_archived",
            "markets": ["US"],
            "universe_total": 10425,
            "candidate_count": 1,
            "candidate_selection": "stable_sha256_v1",
        },
        raw_sources=[raw],
        generated_at=datetime(2025, 10, 24, 12, tzinfo=UTC),
    )
    return snapshot


def test_configured_cached_mode_uses_real_snapshot_and_reports_coverage(tmp_path):
    from scanner.config import Settings
    from scanner.hebeltrader.detective.factory import build_detective
    from scanner.hebeltrader.detective.schemas import DetectiveRequest

    snapshot = make_cached_snapshot(tmp_path)
    settings = Settings(
        _env_file=None,
        detective_research_mode="cached_research",
        detective_research_snapshot=str(snapshot),
    )
    report = build_detective(settings).analyze(
        DetectiveRequest(
            teaser_text="US-Versicherer mit neuer regulatorischer Meldung",
            publication_at="2025-06-01T00:00:00Z",
        )
    )
    assert report["research_mode"] == "cached_research"
    assert report["candidate_source"]["coverage"]["kind"] == "real_archived"
    assert report["candidate_source"]["coverage"]["universe_total"] == 10425
    assert report["candidate_source"]["coverage"]["data_age_seconds"] > 0


def test_fixture_mode_is_explicitly_labeled_and_never_claims_real_coverage():
    from scanner.config import Settings
    from scanner.hebeltrader.detective.factory import build_detective
    from scanner.hebeltrader.detective.schemas import DetectiveRequest

    report = build_detective(Settings(_env_file=None)).analyze(
        DetectiveRequest(teaser_text="Pharmakonzern", publication_at=NOW)
    )
    assert report["research_mode"] == "fixture"
    assert report["candidate_source"]["coverage"]["status"] == "fixture_limited"
    assert report["candidate_source"]["coverage"]["real_market_data"] is False


def test_api_startup_in_live_mode_does_not_access_network(monkeypatch, tmp_path):
    from scanner.config import Settings
    from scanner.main import create_app

    def forbidden(*args, **kwargs):
        raise AssertionError("network access during app construction")

    monkeypatch.setattr(httpx.Client, "get", forbidden)
    app = create_app(
        Settings(
            _env_file=None,
            database_url="sqlite+pysqlite:///:memory:",
            detective_research_mode="live_research",
            detective_research_cache_dir=str(tmp_path / "cache"),
            detective_research_snapshot=str(tmp_path / "snapshot.json"),
            detective_live_allow_network=True,
            detective_live_max_requests=3,
            sec_user_agent="Scanner research@example.org",
        )
    )
    assert app.title == "Multi-Asset Chancen-Scanner V6"


def test_live_mode_requires_explicit_network_and_provider_configuration(tmp_path):
    from scanner.config import Settings
    from scanner.hebeltrader.detective.factory import build_detective
    from scanner.hebeltrader.detective.schemas import DetectiveRequest

    settings = Settings(
        _env_file=None,
        detective_research_mode="live_research",
        detective_research_cache_dir=str(tmp_path / "cache"),
        detective_research_snapshot=str(tmp_path / "snapshot.json"),
    )
    report = build_detective(settings).analyze(
        DetectiveRequest(teaser_text="Unbekannter Versicherer", publication_at=NOW)
    )
    assert report["identification"]["status"] == "unresolved"
    assert report["candidate_source"]["coverage"]["status"] == "unavailable"
    assert report["candidate_source"]["coverage"]["error_code"] == "live_not_authorized"


def test_live_collector_selects_candidates_before_teaser_and_respects_bound(tmp_path):
    from scanner.research_live import collect_sec_snapshot
    from scanner.research_providers.sec_edgar import SecEdgarClient

    def handler(request):
        path = request.url.path
        if path.endswith("company_tickers_exchange.json"):
            payload = {
                "fields": ["cik", "name", "ticker", "exchange"],
                "data": [
                    [1, "Alpha", "AAA", "NYSE"],
                    [2, "Beta", "BBB", "Nasdaq"],
                    [3, "Gamma", "CCC", "NYSE"],
                ],
            }
        elif "/submissions/" in path:
            cik = int(path.split("CIK")[1].split(".")[0])
            payload = {
                "sicDescription": "Fire, Marine & Casualty Insurance" if cik == 2 else "Mining",
                "filings": {
                    "recent": {
                        "accessionNumber": [f"000000000{cik}-25-000001"],
                        "filingDate": ["2025-05-01"],
                        "acceptanceDateTime": ["2025-05-01T16:30:00Z"],
                        "form": ["10-Q"],
                        "items": [""],
                    }
                },
            }
        else:
            payload = companyfacts([])
        return httpx.Response(200, json=payload)

    client = SecEdgarClient(
        tmp_path / "cache",
        user_agent="Scanner research@example.org",
        allow_network=True,
        max_requests=5,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        now=lambda: NOW,
        sleeper=lambda _: None,
    )
    output = tmp_path / "snapshot.json"
    report = collect_sec_snapshot(client, output, max_candidates=2)
    snapshot = load_snapshot(output)
    assert report["selection_method"] == "stable_sha256_cik_v1"
    assert report["selected_count"] == len(snapshot["assets"]) == 2
    assert report["universe_total"] == 3
    assert report["network_request_limit"] == 5
    assert all(row["sha256"] for row in snapshot["raw_sources"])


def test_cli_and_service_cached_reports_have_identical_schema(tmp_path):
    from scanner.config import Settings
    from scanner.hebeltrader.detective.cli import main
    from scanner.hebeltrader.detective.factory import build_detective
    from scanner.hebeltrader.detective.schemas import DetectiveRequest

    snapshot = make_cached_snapshot(tmp_path)
    teaser = tmp_path / "teaser.txt"
    teaser.write_text("US-Versicherer mit regulatorischer Meldung")
    output = tmp_path / "result.json"
    assert (
        main(
            [
                "--text-file",
                str(teaser),
                "--publication-at",
                "2025-06-01T00:00:00Z",
                "--research-mode",
                "cached_research",
                "--research-snapshot",
                str(snapshot),
                "--output",
                str(output),
            ]
        )
        == 0
    )
    cli_report = json.loads(output.read_text())
    service_report = build_detective(
        Settings(
            _env_file=None,
            detective_research_mode="cached_research",
            detective_research_snapshot=snapshot,
        )
    ).analyze(
        DetectiveRequest(teaser_text=teaser.read_text(), publication_at="2025-06-01T00:00:00Z")
    )
    assert cli_report.keys() == service_report.keys()
    assert cli_report["candidate_source"].keys() == service_report["candidate_source"].keys()
    assert cli_report["candidates"] == service_report["candidates"]


def test_blind_ranking_uses_verified_fact_and_exposes_unknown_and_contradiction():
    from scanner.hebeltrader.detective.research_source import ResearchCandidateSource
    from scanner.hebeltrader.detective.schemas import DetectiveRequest
    from scanner.hebeltrader.detective.service import DetectiveService

    assets = [
        AssetIdentity(
            asset_type="stock",
            name=name,
            ticker=ticker,
            cik=str(index),
            country=country,
            sector=sector,
            source_available_at="2024-01-01T00:00:00Z",
        )
        for index, (name, ticker, country, sector) in enumerate(
            [
                ("Alpha", "AAA", "US", "insurance"),
                ("Beta", "BBB", "US", "mining"),
                ("Gamma", "CCC", "DE", "insurance"),
                ("Delta", "DDD", "US", "insurance"),
            ],
            1,
        )
    ]
    facts = [
        CompanyFact(
            fact_id="verified-increase",
            asset=assets[0],
            metric="net_income",
            claim="year_over_year_increase",
            value=15,
            unit="USD",
            period_start="2025-01-01",
            period_end="2025-03-31",
            comparison_value=10,
            comparison_period_start="2024-01-01",
            comparison_period_end="2024-03-31",
            source_url="https://www.sec.gov/a",
            source_location="/facts/a",
            published_at="2025-05-01T16:00:00Z",
            source_available_at="2025-05-01T16:00:00Z",
            retrieved_at=NOW,
            extraction_method="sec_xbrl_exact_duration_fiscal_period_v1",
            verification_status="source_verified",
            content_sha256="a" * 64,
        )
    ]
    source = ResearchCandidateSource(
        assets,
        [],
        facts=facts,
        coverage={"kind": "real_archived", "candidate_count": 4},
    )
    report = DetectiveService(
        candidate_source=source,
        news_source=source,
        products=[],
        research_mode="cached_research",
    ).analyze(
        DetectiveRequest(
            teaser_text=(
                "Ein US-Versicherer meldet einen Gewinnanstieg und eine angehobene Prognose."
            ),
            publication_at="2025-06-01T00:00:00Z",
        )
    )
    assert report["candidates"][0]["ticker"] == "AAA"
    assert {row["value"] for row in report["candidates"][0]["supporting_clues"]} >= {
        "insurance",
        "US",
        "net_income_increase",
    }
    assert "guidance_raise" in report["candidates"][0]["unverified_clues"]["events"]
    beta = next(row for row in report["candidates"] if row["ticker"] == "BBB")
    assert any(row["type"] == "sectors_mismatch" for row in beta["contradictions"])


def test_live_source_is_lazy_and_collects_only_when_analysis_starts(tmp_path):
    from scanner.config import Settings
    from scanner.hebeltrader.detective.factory import build_detective
    from scanner.hebeltrader.detective.schemas import DetectiveRequest
    from scanner.research_providers.sec_edgar import SecEdgarClient

    calls = []

    def handler(request):
        calls.append(request.url.path)
        if request.url.path.endswith("company_tickers_exchange.json"):
            payload = {
                "fields": ["cik", "name", "ticker", "exchange"],
                "data": [[42, "Example Corp", "EX", "NYSE"]],
            }
        elif "/submissions/" in request.url.path:
            payload = {
                "sicDescription": "Fire, Marine & Casualty Insurance",
                "filings": {
                    "recent": {
                        "accessionNumber": ["0000000042-25-000001"],
                        "filingDate": ["2025-05-01"],
                        "acceptanceDateTime": ["2025-05-01T16:30:00Z"],
                        "form": ["10-Q"],
                        "items": [""],
                    }
                },
            }
        else:
            payload = companyfacts([])
        return httpx.Response(200, json=payload)

    client = SecEdgarClient(
        tmp_path / "cache",
        user_agent="Scanner research@example.org",
        allow_network=True,
        max_requests=3,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        now=lambda: NOW,
        sleeper=lambda _: None,
    )
    settings = Settings(
        _env_file=None,
        detective_research_mode="live_research",
        detective_research_cache_dir=tmp_path / "cache",
        detective_research_snapshot=tmp_path / "snapshot.json",
        detective_live_allow_network=True,
        detective_live_max_requests=3,
        detective_live_max_candidates=1,
        sec_user_agent="Scanner research@example.org",
    )
    detective = build_detective(settings, sec_client=client)
    assert calls == []
    report = detective.analyze(DetectiveRequest(teaser_text="US-Versicherer", publication_at=NOW))
    assert len(calls) == 3
    assert report["candidate_source"]["coverage"]["kind"] == "real_archived"
    assert report["candidate_source"]["coverage"]["candidate_count"] == 1
    detective.analyze(DetectiveRequest(teaser_text="US-Versicherer", publication_at=NOW))
    assert len(calls) == 3


def test_gleif_adapter_is_real_cached_cc0_identity_evidence_without_historical_claim(tmp_path):
    from scanner.research_providers.gleif import GleifClient, normalize_legal_entity

    lei = "529900T8BM49AURSDO55"
    payload = {
        "data": {
            "type": "lei-records",
            "id": lei,
            "attributes": {
                "lei": lei,
                "entity": {
                    "legalName": {"name": "Example AG", "language": "de"},
                    "legalAddress": {"country": "DE"},
                    "jurisdiction": "DE",
                    "legalForm": {"id": "6QQB"},
                    "entityStatus": "ACTIVE",
                },
                "registration": {
                    "initialRegistrationDate": "2014-02-06T00:00:00Z",
                    "lastUpdateDate": "2026-08-01T00:00:00Z",
                    "status": "ISSUED",
                },
            },
        }
    }
    calls = []

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(200, json=payload)

    client = GleifClient(
        tmp_path,
        allow_network=True,
        max_requests=1,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        now=lambda: NOW,
    )
    record = client.fetch_lei(lei)
    assert client.fetch_lei(lei)["cache_hit"] is True
    identity = normalize_legal_entity(record)
    assert identity.lei == lei
    assert identity.name == "Example AG"
    assert identity.country == "DE"
    assert identity.source_available_at is None
    assert identity.historically_available_at(datetime(2020, 1, 1, tzinfo=UTC)) is False
    assert record["license"] == "CC0-1.0"
    assert len(calls) == 1


def test_strategy_requirements_report_missing_inputs_without_signal():
    from scanner.strategy_contracts import assess_strategy_inputs

    short = assess_strategy_inputs(
        "short_term_trading",
        {"price": "available", "company_event": "available"},
    )
    medium = assess_strategy_inputs(
        "medium_term_investing",
        {"fundamentals": "available", "growth": "unknown"},
    )
    assert short["required_fields"] == [
        "price",
        "volume",
        "company_event",
        "timestamp",
        "liquidity",
    ]
    assert set(short["missing_fields"]) == {"volume", "timestamp", "liquidity"}
    assert medium["required_fields"] == [
        "fundamentals",
        "growth",
        "valuation",
        "trend",
        "catalyst",
    ]
    assert medium["status"] == "incomplete"
    assert short["strategy_decision"] is None


def test_xbrl_filed_date_is_end_of_day_unless_acceptance_time_is_proven():
    identity = AssetIdentity(asset_type="stock", name="Example", ticker="EX", cik="42")
    payload = companyfacts(
        [
            fact_row(
                value=8,
                start="2025-01-01",
                end="2025-03-31",
                filed="2025-05-01",
                accn="accepted-late",
                fy=2025,
            )
        ]
    )
    conservative = extract_sec_company_facts(sec_record(payload), identity)[0]
    assert conservative.source_available_at.hour == 23
    exact = extract_sec_company_facts(
        sec_record(payload),
        identity,
        availability_by_accession={"accepted-late": datetime(2025, 5, 1, 20, 30, tzinfo=UTC)},
    )[0]
    assert exact.source_available_at == datetime(2025, 5, 1, 20, 30, tzinfo=UTC)
    evidence = EvidenceRecord(
        source_id=exact.fact_id,
        url=exact.source_url,
        title="fact",
        published_at=exact.published_at,
        retrieved_at=exact.retrieved_at,
        effective_at=exact.published_at,
        source_available_at=exact.source_available_at,
        source_kind="regulatory",
        content_sha256=exact.content_sha256,
    )
    assert not evidence.available_at(datetime(2025, 5, 1, 19, tzinfo=UTC))


def test_live_collector_records_missing_companyfacts_as_partial_instead_of_faking_data(
    tmp_path,
):
    from scanner.research_live import collect_sec_snapshot
    from scanner.research_providers.sec_edgar import SecEdgarClient

    def handler(request):
        if request.url.path.endswith("company_tickers_exchange.json"):
            return httpx.Response(
                200,
                json={
                    "fields": ["cik", "name", "ticker", "exchange"],
                    "data": [[42, "Example", "EX", "NYSE"]],
                },
            )
        if "/submissions/" in request.url.path:
            return httpx.Response(
                200,
                json={
                    "sicDescription": "Insurance",
                    "filings": {
                        "recent": {
                            "accessionNumber": [],
                            "filingDate": [],
                            "acceptanceDateTime": [],
                            "form": [],
                            "items": [],
                        }
                    },
                },
            )
        return httpx.Response(404, json={"error": "not found"})

    client = SecEdgarClient(
        tmp_path / "cache",
        user_agent="Scanner research@example.org",
        allow_network=True,
        max_requests=3,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        now=lambda: NOW,
        sleeper=lambda _: None,
    )
    report = collect_sec_snapshot(client, tmp_path / "snapshot.json", max_candidates=1)
    assert report["status"] == "partial"
    assert report["errors"] == [{"cik": "42", "dataset": "companyfacts"}]
    assert load_snapshot(tmp_path / "snapshot.json")["facts"] == []


def test_live_collector_selects_unique_issuers_before_fetching_company_data(tmp_path):
    from scanner.research_live import collect_sec_snapshot
    from scanner.research_providers.sec_edgar import SecEdgarClient

    calls = []

    def handler(request):
        calls.append(request.url.path)
        if request.url.path.endswith("company_tickers_exchange.json"):
            return httpx.Response(
                200,
                json={
                    "fields": ["cik", "name", "ticker", "exchange"],
                    "data": [
                        [42, "Example", "EX-A", "NYSE"],
                        [42, "Example", "EX-B", "NYSE"],
                        [43, "Other", "OTH", "Nasdaq"],
                    ],
                },
            )
        if "/submissions/" in request.url.path:
            return httpx.Response(
                200,
                json={
                    "sicDescription": "State Commercial Banks",
                    "filings": {
                        "recent": {
                            "accessionNumber": [],
                            "filingDate": [],
                            "acceptanceDateTime": [],
                            "form": [],
                            "items": [],
                        }
                    },
                },
            )
        return httpx.Response(200, json=companyfacts([]))

    client = SecEdgarClient(
        tmp_path / "cache",
        user_agent="Scanner research@example.org",
        allow_network=True,
        max_requests=3,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        now=lambda: NOW,
        sleeper=lambda _: None,
    )
    output = tmp_path / "snapshot.json"
    collect_sec_snapshot(client, output, max_candidates=1)
    snapshot = load_snapshot(output)
    assert len(snapshot["assets"]) == 1
    assert snapshot["coverage"]["universe_total"] == 3
    assert snapshot["coverage"]["unique_issuer_total"] == 2
    assert snapshot["assets"][0].sector == "banking"
    assert len([path for path in calls if "/submissions/" in path]) == 1


def test_current_identity_identifier_is_not_treated_as_historical_proof():
    from scanner.hebeltrader.detective.research_source import ResearchCandidateSource
    from scanner.hebeltrader.detective.schemas import DetectiveRequest
    from scanner.hebeltrader.detective.service import DetectiveService

    identity = AssetIdentity(
        asset_type="stock",
        name="Renamed Today",
        ticker="NOW",
        wkn="ABC123",
        country="US",
        retrieved_at=NOW,
        source_available_at=None,
    )
    source = ResearchCandidateSource(
        [identity], [], coverage={"kind": "real_archived", "candidate_count": 1}
    )
    report = DetectiveService(
        candidate_source=source,
        news_source=source,
        products=[],
        research_mode="cached_research",
    ).analyze(
        DetectiveRequest(
            teaser_text="Aktien-WKN ABC123",
            publication_at="2020-01-01T00:00:00Z",
        )
    )
    assert report["identification"]["status"] == "unresolved"
    assert report["candidates"] == []


def test_sample_coverage_never_claims_full_candidate_search(tmp_path):
    from scanner.research_live import collect_sec_snapshot
    from scanner.research_providers.sec_edgar import SecEdgarClient

    def handler(request):
        if request.url.path.endswith("company_tickers_exchange.json"):
            return httpx.Response(
                200,
                json={
                    "fields": ["cik", "name", "ticker", "exchange"],
                    "data": [
                        [1, "Covered", "COV", "NYSE"],
                        [2, "Outside", "OUT", "Nasdaq"],
                    ],
                },
            )
        if "/submissions/" in request.url.path:
            return httpx.Response(
                200,
                json={
                    "sicDescription": "Unknown",
                    "filings": {
                        "recent": {
                            "accessionNumber": [],
                            "filingDate": [],
                            "acceptanceDateTime": [],
                            "form": [],
                            "items": [],
                        }
                    },
                },
            )
        return httpx.Response(200, json=companyfacts([]))

    client = SecEdgarClient(
        tmp_path / "cache",
        user_agent="Scanner research@example.org",
        allow_network=True,
        max_requests=3,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        now=lambda: NOW,
        sleeper=lambda _: None,
    )
    path = tmp_path / "snapshot.json"
    collect_sec_snapshot(client, path, max_candidates=1)
    coverage = load_snapshot(path)["coverage"]
    assert coverage["sampling_strategy"] == "stable_sha256_cik_v1"
    assert coverage["full_universe_size"] == 2
    assert coverage["investigated_count"] == 1
    assert coverage["coverage_ratio"] == 0.5
    assert coverage["missing_sector_rate"] == 1.0
    assert coverage["recall_unmeasurable"] is True
    assert coverage["search_scope"] == "independent_sample_not_global_candidate_search"
    assert coverage["not_covered_markets"] == ["non_SEC_US", "DE", "AT", "CH", "EU"]


def test_later_xbrl_correction_is_not_used_by_earlier_historical_fact():
    identity = AssetIdentity(asset_type="stock", name="Example", ticker="EX", cik="42")
    payload = companyfacts(
        [
            fact_row(
                value=10,
                start="2024-01-01",
                end="2024-03-31",
                filed="2024-05-01",
                accn="prior-original",
                fy=2024,
            ),
            fact_row(
                value=20,
                start="2024-01-01",
                end="2024-03-31",
                filed="2025-06-01",
                accn="prior-correction",
                fy=2024,
            ),
            fact_row(
                value=15,
                start="2025-01-01",
                end="2025-03-31",
                filed="2025-05-01",
                accn="current",
                fy=2025,
            ),
        ]
    )
    availability = {
        "prior-original": datetime(2024, 5, 1, 20, tzinfo=UTC),
        "current": datetime(2025, 5, 1, 20, tzinfo=UTC),
        "prior-correction": datetime(2025, 6, 1, 20, tzinfo=UTC),
    }
    facts = extract_sec_company_facts(
        sec_record(payload), identity, availability_by_accession=availability
    )
    current = next(row for row in facts if row.value == 15)
    assert current.comparison_value == 10
    assert current.claim == "year_over_year_increase"
    assert current.source_available_at == availability["current"]


def test_unknown_sector_is_unverifiable_while_known_different_sector_is_contradiction():
    from scanner.hebeltrader.detective.research_source import ResearchCandidateSource
    from scanner.hebeltrader.detective.schemas import DetectiveRequest
    from scanner.hebeltrader.detective.service import DetectiveService

    unknown = AssetIdentity(
        asset_type="stock",
        name="Unknown Sector",
        ticker="UNK",
        cik="1",
        country="US",
        sector=None,
        source_available_at="2024-01-01T00:00:00Z",
    )
    bank = unknown.model_copy(
        update={"name": "Known Bank", "ticker": "BNK", "cik": "2", "sector": "banking"}
    )
    source = ResearchCandidateSource(
        [unknown, bank], [], coverage={"kind": "real_archived", "candidate_count": 2}
    )
    report = DetectiveService(
        candidate_source=source,
        news_source=source,
        products=[],
        research_mode="cached_research",
    ).analyze(DetectiveRequest(teaser_text="US-Versicherer", publication_at="2025-01-01T00:00:00Z"))
    unknown_row = next(row for row in report["candidates"] if row["ticker"] == "UNK")
    bank_row = next(row for row in report["candidates"] if row["ticker"] == "BNK")
    assert "insurance" in unknown_row["unverified_clues"]["sectors"]
    assert not any(row["type"] == "sectors_mismatch" for row in unknown_row["contradictions"])
    assert any(row["type"] == "sectors_mismatch" for row in bank_row["contradictions"])
    assert (
        unknown_row["relevance_score_not_probability"] > bank_row["relevance_score_not_probability"]
    )


def test_top_three_is_selected_after_ranking_all_candidates():
    from scanner.hebeltrader.detective.research_source import ResearchCandidateSource
    from scanner.hebeltrader.detective.schemas import DetectiveRequest
    from scanner.hebeltrader.detective.service import DetectiveService

    assets = [
        AssetIdentity(
            asset_type="stock",
            name=f"Candidate {index}",
            ticker=f"C{index}",
            cik=str(index),
            country="US",
            sector="banking" if index < 5 else "insurance",
            source_available_at="2024-01-01T00:00:00Z",
        )
        for index in range(6)
    ]
    source = ResearchCandidateSource(
        assets, [], coverage={"kind": "real_archived", "candidate_count": 6}
    )
    report = DetectiveService(
        candidate_source=source,
        news_source=source,
        products=[],
        research_mode="cached_research",
    ).analyze(DetectiveRequest(teaser_text="US-Versicherer", publication_at="2025-01-01T00:00:00Z"))
    assert report["candidates"][0]["ticker"] == "C5"
    assert len(report["candidates"]) == 3


def test_candidate_response_caps_evidence_and_reports_archive_counts():
    from scanner.hebeltrader.detective.research_source import ResearchCandidateSource
    from scanner.hebeltrader.detective.schemas import DetectiveRequest
    from scanner.hebeltrader.detective.service import DetectiveService

    identity = AssetIdentity(
        asset_type="stock",
        name="Evidence Heavy",
        ticker="EVH",
        cik="42",
        country="US",
        sector="insurance",
        source_available_at="2024-01-01T00:00:00Z",
    )

    def make_event(index):
        evidence = EvidenceRecord(
            source_id=f"event-{index}",
            url=f"https://www.sec.gov/event-{index}",
            title="Filing",
            published_at=datetime(2025, 1, 1, tzinfo=UTC),
            retrieved_at=datetime(2025, 1, 1, tzinfo=UTC),
            effective_at=datetime(2025, 1, 1, tzinfo=UTC),
            source_available_at=datetime(2025, 1, 1, tzinfo=UTC),
            source_kind="regulatory",
            facts={},
            content_sha256="a" * 64,
        )
        return CompanyEvent(
            event_id=evidence.source_id,
            asset=identity,
            category="regulatory_filing",
            headline="Filing",
            published_at=evidence.published_at,
            retrieved_at=evidence.retrieved_at,
            effective_at=evidence.effective_at,
            evidence=evidence,
        )

    events = [make_event(index) for index in range(100)]
    source = ResearchCandidateSource(
        [identity], events, coverage={"kind": "real_archived", "candidate_count": 1}
    )
    report = DetectiveService(
        candidate_source=source,
        news_source=source,
        products=[],
        research_mode="cached_research",
    ).analyze(DetectiveRequest(teaser_text="US-Versicherer", publication_at="2025-06-01T00:00:00Z"))
    candidate = report["candidates"][0]
    assert len(candidate["eligible_evidence"]) <= 8
    assert candidate["evidence_summary"] == {
        "eligible_total": 100,
        "returned": 8,
        "omitted": 92,
        "response_limit": 8,
    }
    assert len(json.dumps(report)) < 30_000


def test_capped_response_keeps_evidence_that_supports_ranked_clue():
    from scanner.hebeltrader.detective.research_source import ResearchCandidateSource
    from scanner.hebeltrader.detective.schemas import DetectiveRequest
    from scanner.hebeltrader.detective.service import DetectiveService

    identity = AssetIdentity(
        asset_type="stock",
        name="Example",
        ticker="EX",
        cik="42",
        country="US",
        source_available_at="2024-01-01T00:00:00Z",
    )

    def event(index, facts):
        evidence = EvidenceRecord(
            source_id=f"event-{index}",
            url=f"https://www.sec.gov/event-{index}",
            title="Filing",
            published_at=datetime(2025, 1, 1, tzinfo=UTC),
            retrieved_at=datetime(2025, 1, 1, tzinfo=UTC),
            effective_at=datetime(2025, 1, 1, tzinfo=UTC),
            source_available_at=datetime(2025, 1, 1, tzinfo=UTC),
            source_kind="regulatory",
            facts=facts,
            content_sha256="a" * 64,
        )
        return CompanyEvent(
            event_id=evidence.source_id,
            asset=identity,
            category="regulatory_filing",
            headline="Filing",
            published_at=evidence.published_at,
            retrieved_at=evidence.retrieved_at,
            effective_at=evidence.effective_at,
            evidence=evidence,
        )

    events = [event(index, {}) for index in range(20)]
    events.append(event(99, {"fact_claims": ["net_income_increase"]}))
    source = ResearchCandidateSource(
        [identity], events, coverage={"kind": "real_archived", "candidate_count": 1}
    )
    report = DetectiveService(
        candidate_source=source,
        news_source=source,
        products=[],
        research_mode="cached_research",
    ).analyze(
        DetectiveRequest(
            teaser_text="US-Unternehmen meldet Gewinnanstieg",
            publication_at="2025-06-01T00:00:00Z",
        )
    )
    returned_ids = {row["source_id"] for row in report["candidates"][0]["eligible_evidence"]}
    assert "event-99" in returned_ids


def test_live_mode_requires_complete_bounded_request_budget(tmp_path):
    from scanner.config import Settings
    from scanner.hebeltrader.detective.factory import build_detective
    from scanner.hebeltrader.detective.schemas import DetectiveRequest

    service = build_detective(
        Settings(
            _env_file=None,
            detective_research_mode="live_research",
            detective_live_allow_network=True,
            detective_live_max_requests=20,
            detective_live_max_candidates=10,
            detective_research_snapshot=tmp_path / "snapshot.json",
            detective_research_cache_dir=tmp_path / "cache",
            sec_user_agent="Scanner research@example.org",
            detective_live_api_token="secret",
        )
    )
    report = service.analyze(DetectiveRequest(teaser_text="US-Versicherer"))
    assert report["candidate_source"]["coverage"]["error_code"] == (
        "live_request_budget_insufficient"
    )


def test_live_api_token_status_does_not_authorize_missing_or_wrong_token():
    from scanner.config import Settings
    from scanner.hebeltrader.detective.factory import live_api_access_status

    settings = Settings(
        _env_file=None,
        detective_research_mode="live_research",
        detective_live_api_token="correct horse",
    )
    assert live_api_access_status(settings, None) == "unauthorized"
    assert live_api_access_status(settings, "wrong") == "unauthorized"
    assert live_api_access_status(settings, "correct horse") == "authorized"
    assert live_api_access_status(Settings(_env_file=None), None) == "not_required"


def test_sec_collector_stops_when_wall_clock_budget_is_exhausted(tmp_path):
    from scanner.research_live import collect_sec_snapshot

    class ExpiredClient:
        remaining = 3

        def fetch(self, dataset, identifier=None):
            if dataset == "universe":
                return sec_record(
                    {
                        "fields": ["cik", "name", "ticker", "exchange"],
                        "data": [[1, "Example", "EX", "NYSE"]],
                    }
                )
            raise AssertionError("deadline must be checked before issuer requests")

    ticks = iter([0.0, 2.0])
    with pytest.raises(ValueError, match="duration limit"):
        collect_sec_snapshot(
            ExpiredClient(),
            tmp_path / "snapshot.json",
            max_candidates=1,
            max_duration_seconds=1,
            monotonic=lambda: next(ticks),
        )
