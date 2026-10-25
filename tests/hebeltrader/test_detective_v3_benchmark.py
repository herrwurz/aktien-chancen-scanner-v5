import inspect
import json
from pathlib import Path

import pytest

from scanner.hebeltrader.detective.benchmark_evaluate import evaluate_rankings
from scanner.hebeltrader.detective.benchmark_scan import scan_manifest


class StubService:
    def analyze(self, request):
        ranked = {
            "case-001": ["cik:0000000001", "cik:0000000002"],
            "case-002": [],
        }
        case_id = "case-001" if "Pharma" in request.teaser_text else "case-002"
        hit = bool(ranked[case_id])
        return {
            "schema_version": 3,
            "identification": {
                "status": "likely_candidate" if hit else "unresolved",
                "reason": "frozen_evidence_thresholds_met" if hit else "retrieval_missed",
                "failure_code": None if hit else "retrieval_missed",
            },
            "candidates": [
                {"asset_id": asset_id, "evidence_score": 100 - index}
                for index, asset_id in enumerate(ranked[case_id])
            ],
            "candidate_source": {
                "coverage": {
                    "visible_universe_size": 100,
                    "matched_before_limit": 2 if hit else 0,
                    "channel_limit": 50,
                    "channel_counts": {"sector": 2} if hit else {},
                    "channel_matched_before_limit": {"sector": 2} if hit else {},
                    "stage_a_asset_ids": ranked[case_id],
                }
            },
        }


def write_json(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def sealed_rankings(corpus_kind, cases):
    stable = json.dumps(cases, sort_keys=True, separators=(",", ":")).encode()
    return {
        "schema_version": 3,
        "corpus_kind": corpus_kind,
        "ranking_payload_sha256": __import__("hashlib").sha256(stable).hexdigest(),
        "cases": cases,
    }


def test_scanner_contract_has_no_solution_input_and_emits_stable_rankings(tmp_path):
    assert "solution" not in inspect.signature(scan_manifest).parameters
    manifest = write_json(
        tmp_path / "manifest.json",
        {
            "schema_version": 3,
            "corpus_kind": "synthetic_functional",
            "cases": [
                {
                    "case_id": "case-001",
                    "teaser_text": "US-Pharma mit Prognoseanhebung",
                    "publication_at": "2025-01-01T12:00:00Z",
                },
                {
                    "case_id": "case-002",
                    "teaser_text": "Nicht ausreichend eingeschränkt",
                    "publication_at": "2025-01-01T12:00:00Z",
                },
            ],
        },
    )

    first = scan_manifest(manifest, StubService())
    second = scan_manifest(manifest, StubService())

    assert first["ranking_payload_sha256"] == second["ranking_payload_sha256"]
    assert first["runtime_ms"] >= 0
    assert first["request_count"] == 0
    assert first["cost_eur"] == 0
    assert first["cases"][0]["ranked_asset_ids"] == ["cik:0000000001", "cik:0000000002"]
    assert first["cases"][0]["channel_limit"] == 50
    assert first["cases"][1]["failure_code"] == "retrieval_missed"
    assert "target" not in json.dumps(first)


def test_evaluator_reports_metrics_and_detects_solution_leakage(tmp_path):
    cases = [
        {
            "case_id": "case-001",
            "teaser_sha256": __import__("hashlib").sha256(b"Unbekannter Pharmakonzern").hexdigest(),
            "input_text": "Unbekannter Pharmakonzern",
            "ranked_asset_ids": ["cik:1", "cik:2"],
            "status": "likely_candidate",
        },
        {
            "case_id": "case-002",
            "teaser_sha256": __import__("hashlib").sha256(b"Zu wenig Hinweise").hexdigest(),
            "input_text": "Zu wenig Hinweise",
            "ranked_asset_ids": [],
            "status": "unresolved",
        },
    ]
    rankings = write_json(tmp_path / "rankings.json", sealed_rankings("real_original", cases))
    labels = write_json(
        tmp_path / "labels.json",
        {
            "cases": {
                "case-001": {
                    "asset_id": "cik:1",
                    "forbidden_identifiers": ["ALPHA"],
                    "solution_source": "https://example.test/1",
                    "reviewer": "fixture-reviewer",
                    "confirmed_at": "2025-01-02T00:00:00Z",
                    "original_sha256": "1" * 64,
                },
                "case-002": {
                    "asset_id": "cik:9",
                    "forbidden_identifiers": ["BETA"],
                    "solution_source": "https://example.test/2",
                    "reviewer": "fixture-reviewer",
                    "confirmed_at": "2025-01-02T00:00:00Z",
                    "original_sha256": "2" * 64,
                },
            }
        },
    )

    report = evaluate_rankings(rankings, labels)

    assert report["metrics"]["top_1_rate"] == 0.5
    assert report["metrics"]["top_3_rate"] == 0.5
    assert report["metrics"]["abstention_count"] == 1
    assert report["metrics"]["outcome_counts"]["hit_top3"] == 1
    assert report["case_outcomes"][0]["outcome"] == "hit_top3"
    assert report["real_benchmark_status"] == "insufficient_real_benchmark_coverage"
    assert report["leakage_violations"] == []


def test_evaluator_rejects_solution_identifier_in_input(tmp_path):
    teaser = "Gesucht ist ALPHA"
    cases = [
        {
            "case_id": "random-7f4a",
            "teaser_sha256": __import__("hashlib").sha256(teaser.encode()).hexdigest(),
            "input_text": teaser,
            "ranked_asset_ids": [],
            "status": "unresolved",
        }
    ]
    rankings = write_json(
        tmp_path / "rankings.json", sealed_rankings("synthetic_functional", cases)
    )
    labels = write_json(
        tmp_path / "labels.json",
        {"cases": {"random-7f4a": {"asset_id": "cik:1", "forbidden_identifiers": ["ALPHA"]}}},
    )
    with pytest.raises(ValueError, match="solution leakage"):
        evaluate_rankings(rankings, labels)


def test_fixture_keeps_ten_functional_inputs_separate_from_labels():
    inputs = json.loads(Path("tests/fixtures/detective-v3/inputs/manifest.json").read_text())
    labels = json.loads(Path("tests/fixtures/detective-v3/solutions/labels.json").read_text())
    assert len(inputs["cases"]) >= 10
    assert set(labels["cases"]) == {case["case_id"] for case in inputs["cases"]}
    assert "asset_id" not in json.dumps(inputs)


def test_ten_case_fixture_runs_end_to_end_against_separate_index(tmp_path):
    from scanner.hebeltrader.detective.index_source import IndexCandidateSource
    from scanner.hebeltrader.detective.service import DetectiveService
    from scanner.news import NewsItem
    from scanner.research import AssetIdentity
    from scanner.research_index.builder import build_index
    from scanner.research_index.repository import ResearchIndex

    root = Path("tests/fixtures/detective-v3")
    universe = json.loads((root / "inputs/universe.json").read_text())
    index_path = tmp_path / "index.db"
    build_index(
        index_path,
        assets=[AssetIdentity.model_validate(row) for row in universe["assets"]],
        events=[],
        facts=[],
        news=[NewsItem.model_validate(row) for row in universe["news"]],
    )
    source = IndexCandidateSource(ResearchIndex(index_path))
    service = DetectiveService(
        candidate_source=source,
        news_source=source,
        products=[],
        research_mode="indexed_research",
    )
    rankings_payload = scan_manifest(root / "inputs/manifest.json", service)
    rankings = write_json(tmp_path / "rankings.json", rankings_payload)
    report = evaluate_rankings(rankings, root / "solutions/labels.json")

    assert report["metrics"]["case_count"] == 10
    assert report["metrics"]["top_3_count"] >= 6
    assert report["metrics"]["abstention_count"] >= 2
    assert report["real_benchmark_status"] == "insufficient_real_benchmark_coverage"
