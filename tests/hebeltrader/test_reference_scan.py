import json
from pathlib import Path

import pytest

from scanner.hebeltrader.detective.reference_cases import export_inputs
from scanner.hebeltrader.detective.reference_evaluate import evaluate
from scanner.hebeltrader.detective.reference_scan import run_scan

REFERENCES = Path(__file__).parents[2] / "data/hebeltrader/teaser-cases.json"


def test_scan_all_references_without_reading_solutions_then_evaluate(tmp_path, monkeypatch):
    inputs = tmp_path / "inputs.json"
    export_inputs(REFERENCES, inputs)
    read = Path.read_text

    def guarded(path, *args, **kwargs):
        assert path.name not in ("teaser-cases.json", "hebeltrader-identification-rules.md")
        assert "solutions" not in path.parts
        return read(path, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "read_text", guarded)
        frozen = run_scan(inputs, tmp_path / "out")
    assert len(frozen["report"]["cases"]) == 27
    assert all(c["identification"]["status"] == "not_identified" for c in frozen["report"]["cases"])
    assert all(
        set(candidate) <= {"name", "sector", "layer", "structure", "ticker", "aliases"}
        for case in frozen["report"]["cases"]
        for candidate in case["offline_hypotheses"]
    )
    assert all(not case["candidates"] for case in frozen["report"]["cases"])
    result = evaluate(tmp_path / "out/rankings.json", REFERENCES)
    assert result["historical_conversation"]["wrong"] == 7
    assert result["regression"]["cases"] == 27
    assert result["regression"]["graded_cases"] == 25
    assert result["regression"]["abstentions"] == 27
    assert result["independent_real_blind_tests"] == 0
    assert result["regression"]["top1_rate"] is None
    assert result["regression"]["top3_rate"] is None
    assert result["missing_full_text_count"] == 4
    assert result["historical_conversation"]["total"] == 18
    assert result["offline_hypothesis_coverage"]["graded_cases"] == 25
    assert result["offline_hypothesis_coverage"]["solution_in_first_suggestion"] == 2
    assert result["offline_hypothesis_coverage"]["solution_in_top3_suggestions"] == 4
    assert result["offline_hypothesis_coverage"]["solution_in_top8_suggestions"] == 6
    assert result["cases"][0]["offline_hypothesis_rank"] == 1
    assert result["market_hypothesis_coverage"]["snapshots_not_provided"] == 27
    assert result["market_hypothesis_coverage"]["suggestion_cases"] == 0
    assert result["cases"][0]["market_hypothesis_rank"] is None


def test_scan_rejects_solution_fields_even_in_export(tmp_path):
    inputs = tmp_path / "inputs.json"
    export_inputs(REFERENCES, inputs)
    data = json.loads(inputs.read_text())
    data["cases"][0]["actual_company"] = "Costco"
    inputs.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="forbidden"):
        run_scan(inputs, tmp_path / "out")
