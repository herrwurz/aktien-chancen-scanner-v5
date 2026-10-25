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
        return {
            "schema_version": 3,
            "identification": {"status": "likely_candidate" if ranked[case_id] else "unresolved"},
            "candidates": [
                {"asset_id": asset_id, "evidence_score": 100 - index}
                for index, asset_id in enumerate(ranked[case_id])
            ],
            "candidate_source": {"coverage": {"visible_universe_size": 100}},
        }


def write_json(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


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
    assert "target" not in json.dumps(first)


def test_evaluator_reports_metrics_and_detects_solution_leakage(tmp_path):
    rankings = write_json(
        tmp_path / "rankings.json",
        {
            "schema_version": 3,
            "corpus_kind": "real_original",
            "cases": [
                {
                    "case_id": "case-001",
                    "teaser_sha256": "a" * 64,
                    "input_text": "Unbekannter Pharmakonzern",
                    "ranked_asset_ids": ["cik:1", "cik:2"],
                    "status": "likely_candidate",
                },
                {
                    "case_id": "case-002",
                    "teaser_sha256": "b" * 64,
                    "input_text": "Zu wenig Hinweise",
                    "ranked_asset_ids": [],
                    "status": "unresolved",
                },
            ],
        },
    )
    labels = write_json(
        tmp_path / "labels.json",
        {
            "cases": {
                "case-001": {"asset_id": "cik:1", "forbidden_identifiers": ["ALPHA"]},
                "case-002": {"asset_id": "cik:9", "forbidden_identifiers": ["BETA"]},
            }
        },
    )

    report = evaluate_rankings(rankings, labels)

    assert report["metrics"]["top_1_rate"] == 0.5
    assert report["metrics"]["top_3_rate"] == 0.5
    assert report["metrics"]["abstention_count"] == 1
    assert report["real_benchmark_status"] == "insufficient_real_benchmark_coverage"
    assert report["leakage_violations"] == []


def test_evaluator_rejects_solution_identifier_in_input(tmp_path):
    rankings = write_json(
        tmp_path / "rankings.json",
        {
            "schema_version": 3,
            "corpus_kind": "synthetic_functional",
            "cases": [
                {
                    "case_id": "random-7f4a",
                    "input_text": "Gesucht ist ALPHA",
                    "ranked_asset_ids": [],
                    "status": "unresolved",
                }
            ],
        },
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
