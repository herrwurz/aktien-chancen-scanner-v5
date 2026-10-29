import json
from pathlib import Path

import pytest

from scanner.hebeltrader.detective.reference_cases import export_inputs
from scanner.hebeltrader.detective.reference_evaluate import evaluate
from scanner.hebeltrader.detective.reference_scan import run_scan

REFERENCES = Path(__file__).parents[2] / "data/hebeltrader/teaser-cases.json"


def test_scan_all_eighteen_without_reading_solutions_then_evaluate(tmp_path, monkeypatch):
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
    assert len(frozen["report"]["cases"]) == 18
    assert all(c["identification"]["status"] == "not_identified" for c in frozen["report"]["cases"])
    result = evaluate(tmp_path / "out/rankings.json", REFERENCES)
    assert result["historical_conversation"]["wrong"] == 7
    assert result["regression"]["cases"] == 18
    assert result["regression"]["abstentions"] == 18
    assert result["independent_real_blind_tests"] == 0
    assert result["regression"]["top1_rate"] is None
    assert result["regression"]["top3_rate"] is None
    assert result["missing_full_text_count"] == 17


def test_scan_rejects_solution_fields_even_in_export(tmp_path):
    inputs = tmp_path / "inputs.json"
    export_inputs(REFERENCES, inputs)
    data = json.loads(inputs.read_text())
    data["cases"][0]["actual_company"] = "Costco"
    inputs.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="forbidden"):
        run_scan(inputs, tmp_path / "out")
