import hashlib
import json
from datetime import UTC, datetime

NOW = datetime(2026, 10, 24, tzinfo=UTC)


def test_evaluation_reports_recall_ranking_abstention_and_real_fixture_split():
    from scanner.research_evaluation import evaluate_cases

    cases = [
        {
            "case_id": "real-1",
            "kind": "real_archived",
            "target": "cik:1",
            "ranked": ["cik:2", "cik:1"],
            "status": "ok",
        },
        {
            "case_id": "synthetic-1",
            "kind": "synthetic",
            "target": "cik:9",
            "ranked": ["cik:9"],
            "status": "ok",
        },
        {
            "case_id": "abstain",
            "kind": "synthetic",
            "target": None,
            "ranked": [],
            "status": "unresolved",
        },
        {
            "case_id": "missing",
            "kind": "real_archived",
            "target": "cik:7",
            "ranked": [],
            "status": "unresolved",
        },
    ]
    report = evaluate_cases(cases)
    assert report["all"]["recall_at_10"] == 2 / 3
    assert report["all"]["recall_at_50"] == 2 / 3
    assert report["all"]["top_1"] == 1 / 3
    assert report["all"]["top_3"] == 2 / 3
    assert report["all"]["abstention_accuracy"] == 1.0
    assert report["real_archived"]["case_count"] == 2
    assert report["synthetic"]["case_count"] == 2


def test_evaluation_flags_lookahead_and_missing_target_without_inventing_denominator():
    from scanner.research_evaluation import evaluate_cases

    cases = [
        {
            "case_id": "late",
            "kind": "real_archived",
            "target": "cik:1",
            "ranked": ["cik:1"],
            "status": "ok",
            "as_of": "2025-01-01T00:00:00Z",
            "evidence_available_at": ["2025-01-02T00:00:00Z"],
        },
        {
            "case_id": "unlabelled",
            "kind": "real_archived",
            "target": None,
            "ranked": ["cik:2"],
            "status": "ok",
        },
    ]
    report = evaluate_cases(cases)
    assert report["all"]["labelled_case_count"] == 1
    assert report["all"]["lookahead_violations"] == ["late"]
    assert report["all"]["abstention_accuracy"] == 0.0


def test_evaluation_reports_latency_cost_and_request_budget_without_inventing_values():
    from scanner.research_evaluation import evaluate_cases

    cases = [
        {
            "case_id": "measured",
            "kind": "real_archived",
            "target": "cik:1",
            "ranked": ["cik:1"],
            "status": "ok",
            "latency_ms": 125.5,
            "cost_eur": 0.0,
            "request_count": 1,
        },
        {
            "case_id": "unmeasured",
            "kind": "synthetic",
            "target": "cik:2",
            "ranked": [],
            "status": "unresolved",
        },
    ]
    report = evaluate_cases(cases)["all"]
    assert report["measured_latency_case_count"] == 1
    assert report["max_latency_ms"] == 125.5
    assert report["total_cost_eur"] == 0.0
    assert report["total_request_count"] == 1


def test_archived_sec_and_news_build_a_reproducible_real_report(tmp_path):
    from scanner.news import NewsBatch
    from scanner.research_v24_report import build_report

    raw = json.dumps(
        {
            "fields": ["cik", "name", "ticker", "exchange"],
            "data": [[320193, "Apple Inc.", "AAPL", "Nasdaq"], [42, "Other", "OTH", "NYSE"]],
        }
    ).encode()
    cache = tmp_path / "sec-cache"
    (cache / "raw").mkdir(parents=True)
    raw_sha = hashlib.sha256(raw).hexdigest()
    (cache / "raw" / f"{raw_sha}.json").write_bytes(raw)
    manifest = {
        "raw_sha256": raw_sha,
        "raw_file": f"raw/{raw_sha}.json",
        "source_reference": "https://www.sec.gov/files/company_tickers_exchange.json",
        "retrieved_at": NOW.isoformat(),
    }
    request_path = cache / "requests" / "universe.json"
    request_path.parent.mkdir()
    request_path.write_text(json.dumps(manifest))
    batch = NewsBatch.model_validate(
        {
            "provider": "ISSUER_FEED",
            "status": "ok",
            "items": [
                {
                    "source_id": "issuer:apple",
                    "source_type": "PRIMARY",
                    "url": "https://www.apple.com/newsroom/example",
                    "title": "Apple unveils a new product",
                    "published_at": NOW.isoformat(),
                    "first_seen_at": NOW.isoformat(),
                    "retrieved_at": NOW.isoformat(),
                    "source_available_at": NOW.isoformat(),
                    "company_identifiers": {"cik": ["320193"]},
                    "event_type": "issuer_announcement",
                    "event_confidence": "source_claim",
                    "evidence_status": "issuer_publication",
                    "license_status": "permitted_metadata",
                    "content_hash": "a" * 64,
                    "origin_id": "apple:1",
                }
            ],
            "retrieved_at": NOW.isoformat(),
        }
    )
    batch_path = tmp_path / "news.json"
    batch_path.write_text(batch.model_dump_json())
    report = build_report(
        request_path,
        batch_path,
        tmp_path / "index.db",
        query="Apple unveils product",
        as_of=NOW,
    )
    assert report["real_data"]["sec_issuers"] == 2
    assert report["real_data"]["news_items"] == 1
    assert report["candidate_result"]["candidates"][0]["identity"]["ticker"] == "AAPL"
    assert report["claims"]["investment_signal"] is False
