"""Known title excerpts are development regressions, never independent blind evidence."""

import json
from pathlib import Path

from scanner.hebeltrader.detective.investigation import InvestigationRequest, Investigator

FIXTURES = Path(__file__).parents[1] / "fixtures" / "teaser-v31"


def test_known_excerpts_do_not_force_old_solutions_without_original_evidence(tmp_path, monkeypatch):
    inputs = json.loads((FIXTURES / "inputs" / "known-title-excerpts.json").read_text())
    read = Path.read_text

    def guard(path, *args, **kwargs):
        assert path.name != "hebeltrader-identification-rules.md"
        assert "solutions" not in path.parts, "Solutions entered ranking context"
        return read(path, *args, **kwargs)

    reports = []
    with monkeypatch.context() as patch:
        patch.setattr(Path, "read_text", guard)
        for case in inputs["cases"]:
            reports.append(
                Investigator(tmp_path).analyze(
                    InvestigationRequest(
                        teaser_text=case["teaser_text"],
                        headline=case["headline"],
                        evaluation_class="development_regression",
                    ),
                    documents=[],
                    case_id=case["case_id"],
                )
            )
    # Labels are opened only after all rankings were frozen.
    labels = json.loads((FIXTURES / "solutions" / "known-history.json").read_text())
    assert len(labels["cases"]) == 3
    assert all(report["identification"]["status"] == "not_identified" for report in reports)
    assert all(not report["candidates"] for report in reports)
    assert labels["cases"][2]["blocked_reason"] == "Original teaser absent"
