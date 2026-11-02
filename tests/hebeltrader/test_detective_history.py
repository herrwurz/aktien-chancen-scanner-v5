import json
from pathlib import Path

import pytest

from scanner.hebeltrader.detective.history import (
    evaluate_frozen,
    freeze_analysis,
    inventory_history,
)


def test_history_complete_and_honest():
    inventory = inventory_history(
        Path(__file__).parents[2] / "docs/hebeltrader-identification-rules.md"
    )
    assert len(inventory["cases"]) == 17
    cases = {c["case_id"]: c for c in inventory["cases"]}
    assert "HT-016" not in cases
    assert "Analog Devices" in cases["HT-001"]["reported_identity"]
    assert "Lattice" in cases["HT-001"]["notes"]
    assert "Salesforce" in cases["HT-004"]["reported_identity"]
    assert "Zoom" in cases["HT-004"]["notes"]
    assert "Goldman Sachs" in cases["HT-017"]["notes"]
    assert "Johnson & Johnson" in cases["HT-018"]["reported_identity"]
    assert "Turnaround-Alarm im Versicherungssektor" in cases["HT-002"]["original_text"]
    assert cases["HT-017"]["publication_date"] == "2026-10-19"
    assert cases["HT-001"]["publication_date"] == "2026-10-28"
    assert all(c["historical_top3"] is None for c in cases.values())
    assert all(c["evaluation_class"] == "development_regression" for c in cases.values())


def report():
    return {
        "cases": [
            {
                "case_id": "HT-001",
                "identification": {"status": "identified"},
                "candidates": [{"asset_id": "LSCC"}, {"asset_id": "ADI"}],
                "countercandidate_count": 5,
                "source_quality": {"primary": 2},
                "analysis_seconds": 1.2,
            },
            {
                "case_id": "HT-OPEN",
                "identification": {"status": "identified"},
                "candidates": [{"asset_id": "WMB"}],
            },
            {"case_id": "new", "identification": {"status": "not_identified"}, "candidates": []},
        ]
    }


def test_freeze_and_blind_evaluation(tmp_path):
    frozen = tmp_path / "frozen.json"
    result = freeze_analysis(report(), frozen)
    assert result["sha256"]
    with pytest.raises(FileExistsError):
        freeze_analysis(report(), frozen)
    labels = tmp_path / "labels.json"
    labels.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "case_id": "HT-001",
                        "asset_id": "ADI",
                        "evaluation_class": "development_regression",
                    },
                    {"case_id": "HT-OPEN", "status": "unresolved", "asset_id": "WMB"},
                    {"case_id": "new", "asset_id": "CRM", "evaluation_class": "independent"},
                ]
            }
        )
    )
    evaluated = evaluate_frozen(frozen, labels)
    assert evaluated["cases"][0]["correct_rank"] == 2
    assert evaluated["cases"][0]["original_top3"] == report()["cases"][0]["candidates"]
    assert evaluated["cases"][1]["correct_rank"] is None
    assert evaluated["summary"]["abstentions"] == 1
    assert evaluated["summary"]["top3_hits"] == 1
    assert evaluated["independent"]["total"] == 0
    assert evaluated["independent"]["top3_hits"] == 0
    envelope = json.loads(frozen.read_text())
    envelope["report"]["cases"][0]["candidates"].reverse()
    frozen.chmod(0o600)
    frozen.write_text(json.dumps(envelope))
    with pytest.raises(ValueError, match="SHA"):
        evaluate_frozen(frozen, labels)


def test_unfrozen_rejected(tmp_path):
    path = tmp_path / "raw.json"
    path.write_text(json.dumps(report()))
    with pytest.raises(ValueError, match="frozen"):
        evaluate_frozen(path, tmp_path / "absent-labels.json")


def test_independent_label_without_post_freeze_provenance_is_not_an_independent_rate(tmp_path):
    frozen = tmp_path / "ranking.json"
    freeze_analysis(
        {
            "case_id": "fresh",
            "teaser_sha256": "a" * 64,
            "identification": {"status": "identified"},
            "candidates": [{"asset_id": "X"}],
        },
        frozen,
    )
    labels = tmp_path / "labels.json"
    labels.write_text(
        json.dumps(
            {"cases": [{"case_id": "fresh", "asset_id": "X", "evaluation_class": "independent"}]}
        )
    )
    result = evaluate_frozen(frozen, labels)
    assert result["independent"]["graded"] == 0
    assert result["cases"][0]["evaluation_class"] == "independent_unverified"
