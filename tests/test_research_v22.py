import json
from datetime import UTC, datetime

import httpx

from scanner.hebeltrader.detective.research_source import ResearchCandidateSource
from scanner.hebeltrader.detective.schemas import DetectiveRequest
from scanner.hebeltrader.detective.service import DetectiveService
from scanner.research import AssetIdentity, CompanyEvent, EvidenceRecord, ProviderStatus
from scanner.research_service import ResearchService, audit_identity_conflicts

CLOCK = datetime(2026, 10, 23, 12, tzinfo=UTC)


def event(asset, *, event_id, category, published_at, sector):
    evidence = EvidenceRecord(
        source_id=event_id,
        url=f"https://evidence.example/{event_id}",
        title=event_id,
        published_at=published_at,
        retrieved_at=published_at,
        effective_at=published_at,
        source_kind="news",
        facts={},
        content_sha256="a" * 64,
    )
    asset = asset.model_copy(update={"sector": sector})
    return CompanyEvent(
        event_id=event_id,
        asset=asset,
        category=category,
        headline=event_id,
        published_at=published_at,
        retrieved_at=published_at,
        effective_at=published_at,
        evidence=evidence,
    )


def broad_snapshot():
    sectors = [
        "insurance",
        "pharma",
        "energy",
        "sportswear",
        "laboratory",
        "gold_mining",
        "power_grid",
        "agriculture_machinery",
    ]
    assets = [
        AssetIdentity(
            asset_type="stock",
            name=f"Company {index}",
            ticker=f"C{index}",
            isin=f"DE00000000{index:02d}",
            country="EU" if index < 5 else "US",
            sector=sector,
            source_id="broad-offline-snapshot",
            quality_status="candidate",
        )
        for index, sector in enumerate(sectors)
    ]
    events = [
        event(
            asset,
            event_id=f"event-{index}",
            category="guidance_raise" if index in {0, 3} else "regulatory_filing",
            published_at=datetime(2025, 5, index + 1, tzinfo=UTC),
            sector=asset.sector,
        )
        for index, asset in enumerate(assets)
    ]
    return assets, events


def test_a_blind_teaser_searches_broad_snapshot_and_returns_evidence():
    assets, events = broad_snapshot()
    source = ResearchCandidateSource(
        assets,
        events,
        coverage={"status": "offline_snapshot", "candidate_count": len(assets)},
    )
    report = DetectiveService(candidate_source=source, news_source=source, products=[]).analyze(
        DetectiveRequest(
            teaser_text=(
                "Ein europäischer Versicherer überrascht mit steigenden Gewinnen und einer "
                "angehobenen Jahresprognose."
            ),
            publication_at="2025-08-01T08:00:00Z",
        )
    )
    assert report["identification"]["status"] == "resolved_candidate"
    assert report["candidates"][0]["ticker"] == "C0"
    assert report["candidates"][0]["eligible_evidence"][0]["source_id"] == "event-0"
    assert report["automatic_confirmation"] is False


def test_b_later_news_is_excluded_from_historical_analysis():
    assets, events = broad_snapshot()
    events[0] = event(
        assets[0],
        event_id="future-guidance",
        category="guidance_raise",
        published_at=datetime(2025, 9, 1, tzinfo=UTC),
        sector="insurance",
    )
    source = ResearchCandidateSource(assets, events, coverage={"status": "snapshot"})
    report = DetectiveService(candidate_source=source, news_source=source, products=[]).analyze(
        DetectiveRequest(
            teaser_text="Company 0: Europäischer Versicherer mit angehobener Jahresprognose",
            publication_at="2025-08-01T08:00:00Z",
        )
    )
    candidate = next(row for row in report["candidates"] if row["ticker"] == "C0")
    assert candidate["eligible_evidence"] == []
    assert candidate["excluded_future_or_unavailable_source_ids"] == ["future-guidance"]
    assert report["identification"]["status"] == "unresolved"


def test_c_missing_market_coverage_abstains():
    source = ResearchCandidateSource(
        [], [], coverage={"status": "unavailable", "reason": "market_not_covered"}
    )
    report = DetectiveService(candidate_source=source, news_source=source, products=[]).analyze(
        DetectiveRequest(teaser_text="Japanischer Halbleiterausrüster", publication_at=CLOCK)
    )
    assert report["candidates"] == []
    assert report["identification"]["reason"] == "insufficient_evidence"


def test_d_duplicate_and_conflicting_identities_are_not_merged():
    base = AssetIdentity(
        asset_type="stock", name="Alpha", ticker="AAA", isin="US0000000001", exchange="NYSE"
    )
    duplicate = base.model_copy()
    conflict = base.model_copy(update={"name": "Different Company", "cik": "123"})
    audit = audit_identity_conflicts([base, duplicate, conflict])
    assert audit["conflicts"]
    assert audit["merge_performed"] is False


class StaticUniverse:
    def __init__(self, assets):
        self.assets = assets

    def load_universe(self):
        return self.assets, ProviderStatus(
            provider="fixture",
            status="offline_fixture",
            retrieved_at=CLOCK,
            record_count=len(self.assets),
        )


class StaticEvents:
    def __init__(self, events):
        self._events = events

    def load_events(self, identity):
        return self._events, ProviderStatus(
            provider="fixture",
            status="offline_fixture",
            retrieved_at=CLOCK,
            record_count=len(self._events),
        )


def test_e_events_are_shared_without_mixing_strategy_decisions():
    assets, events = broad_snapshot()
    report = ResearchService(
        universe_provider=StaticUniverse(assets), event_provider=StaticEvents(events)
    ).events(assets[0])
    assert report["strategy_consumers"] == [
        "HEBELTRADER_DETECTIVE",
        "short_term_trading",
        "medium_term_investing",
    ]
    assert report["strategy_decision"] is None


def test_f_sec_provider_failure_is_explicit(tmp_path):
    from scanner.research_providers.sec_edgar import SecEdgarClient, SecUniverseProvider

    client = SecEdgarClient(tmp_path, allow_network=False, now=lambda: CLOCK)
    assets, status = SecUniverseProvider(client).load_universe()
    assert assets == []
    assert status.status == "unavailable"
    assert "cache miss" in status.error_code


def test_sec_live_schema_adapter_caches_deduplicates_and_normalizes(tmp_path):
    from scanner.research_providers.sec_edgar import SecEdgarClient, SecUniverseProvider

    calls = []

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(
            200,
            json={
                "fields": ["cik", "name", "ticker", "exchange"],
                "data": [[320193, "Apple Inc.", "AAPL", "Nasdaq"]],
            },
        )

    client = SecEdgarClient(
        tmp_path,
        user_agent="Scanner research@example.org",
        allow_network=True,
        max_requests=1,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        now=lambda: CLOCK,
        sleeper=lambda _: None,
    )
    first, first_status = SecUniverseProvider(client).load_universe()
    second, second_status = SecUniverseProvider(client).load_universe()
    assert first[0].ticker == second[0].ticker == "AAPL"
    assert first[0].cik == "320193"
    assert first_status.cache_hit is False
    assert second_status.cache_hit is True
    assert len(calls) == 1


def test_sec_submission_event_categories_and_point_in_time_fields():
    from scanner.research_providers.sec_edgar import normalize_submission_events

    identity = AssetIdentity(asset_type="stock", name="Example", ticker="EX", cik="42")
    payload = {
        "filings": {
            "recent": {
                "accessionNumber": ["0000000042-25-000001", "0000000042-25-000002"],
                "filingDate": ["2025-05-01", "2025-05-02"],
                "acceptanceDateTime": ["2025-05-01T16:30:00Z", "2025-05-02T17:00:00Z"],
                "form": ["8-K", "8-K"],
                "items": ["2.02", "5.02"],
            }
        }
    }
    events = normalize_submission_events(
        {"payload": payload, "retrieved_at": CLOCK.isoformat(), "raw_sha256": "b" * 64},
        identity,
    )
    assert [row.category for row in events] == ["regulatory_filing", "management_change"]
    assert events[0].facts["document_type"] == "8-K"
    assert events[0].published_at < events[0].retrieved_at
    assert events[0].evidence.available_at(datetime(2025, 5, 1, 17, tzinfo=UTC))
    assert not events[1].evidence.available_at(datetime(2025, 5, 1, 17, tzinfo=UTC))
    assert events[0].evidence.url.startswith("https://www.sec.gov/Archives/")


def test_sec_cli_dry_run_is_read_only_and_machine_readable(tmp_path):
    from scanner.research_cli import run

    output = tmp_path / "report.json"
    status = run(
        [
            "--cache-dir",
            str(tmp_path / "cache"),
            "--output",
            str(output),
            "--dry-run",
            "sec-universe",
        ]
    )
    report = json.loads(output.read_text())
    assert status == 0
    assert report["provider_status"]["status"] == "dry_run"
    assert report["assets"] == []
    assert report["strategy_decision"] is None
