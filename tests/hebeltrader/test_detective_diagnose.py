import json
from pathlib import Path

from scanner.hebeltrader.detective.diagnose import (
    diagnose_manifest,
    main,
    render_markdown,
    summarize_result,
)
from tests.hebeltrader.test_detective_hypothesis_benchmark import _service

ROOT = Path("tests/fixtures/detective-hypothesis")


def test_diagnose_mini_benchmark_writes_artifacts(tmp_path):
    labels = json.loads((ROOT / "mini_benchmark/labels.json").read_text(encoding="utf-8"))["cases"]
    report = diagnose_manifest(ROOT / "mini_benchmark/manifest.json", _service(), labels=labels)
    assert report["case_count"] == 8
    assert "outcome_counts" in report
    assert any(row.get("top3") is not None for row in report["cases"])
    markdown = render_markdown(report)
    assert "Detektiv-Teaser-Diagnose" in markdown
    prefix = tmp_path / "diag"
    code = main(
        [
            "--inputs",
            str(ROOT / "mini_benchmark/manifest.json"),
            "--labels",
            str(ROOT / "mini_benchmark/labels.json"),
            "--output-prefix",
            str(prefix),
            "--service",
            "hypothesis_fixture",
        ]
    )
    assert code == 0
    assert Path(f"{prefix}.json").is_file()
    assert Path(f"{prefix}.md").is_file()
    assert Path(f"{prefix}.csv").is_file()


def test_summarize_marks_false_top3_when_abstention_expected():
    result = {
        "analysis_mode": "hypothesis",
        "identification": {
            "status": "hypothesis_top3",
            "reason": "top_hypothesis_candidates_require_manual_review",
            "selected_asset_id": "isin:DE0005552004",
            "failure_code": None,
            "requires_manual_review": True,
        },
        "candidates": [
            {
                "asset_id": "isin:DE0005552004",
                "name": "Demo",
                "evidence_score": 1,
                "evidence_strength": "hypothesis_only",
                "hypothesis_reasons": ["sector_match"],
                "supporting_clues": [],
                "contradictions": [],
                "unknown_clue_ids": ["c1"],
                "hard_contradictions": False,
            }
        ],
        "extracted_clues": [{"category": "sector", "value": "logistics"}],
        "search_queries": [],
        "candidate_source": {"coverage": {}},
        "review_hints": [],
    }
    row = summarize_result(
        "promo",
        "Einmalige Chance mit 1.717 Prozent Rendite.",
        result,
        {
            "asset_id": "fixture-unresolved-ok",
            "acceptable_asset_ids": [],
            "expected_in_universe": False,
        },
    )
    assert row["label"]["outcome"] == "false_top3"
