import json
from pathlib import Path

import pytest

from scanner.hebeltrader.detective.reference_cases import (
    export_inputs,
    historical_summary,
    load_references,
)

ROOT = Path(__file__).parents[2]
DATA = ROOT / "data/hebeltrader/teaser-cases.json"


def test_original_eighteen_user_cases_preserve_wrong_guesses_and_unknown_williams():
    data = load_references(DATA)
    assert len(data["cases"]) == 28
    by = {c["reference_number"]: c for c in data["cases"] if c["reference_number"] <= 18}
    assert len(by) == 18
    assert by[3]["first_prediction"] == "UnitedHealth Group"
    assert by[8]["first_prediction"] == "Zebra Technologies"
    assert by[9]["first_prediction"] == "Oracle"
    assert by[13]["first_prediction"] == "Thales"
    assert by[2]["actual_company"] is None and by[2]["actual_ticker"] is None
    assert by[2]["outcome"] == "unresolved"
    assert by[16]["publication_date"] == "2026-10-19"
    assert by[16]["resolution_date"] == "2026-10-19"
    assert by[18]["first_prediction_confidence"] == 95
    summary = historical_summary(data)
    assert (summary["correct"], summary["wrong"], summary["unresolved"]) == (10, 7, 1)
    assert summary["independent_benchmark"] is False


def test_extended_cases_do_not_change_original_historical_summary():
    data = load_references(DATA)
    summary = historical_summary(data)
    assert summary["total"] == 18
    assert summary["missing_full_teasers"] == ["HT-016"]
    extended = {c["reference_number"]: c for c in data["cases"] if c["reference_number"] > 18}
    assert extended[20]["outcome"] == "not_identified"
    assert extended[21]["outcome"] == "not_tested"
    assert extended[19]["outcome"] == "correct"


def test_scan_export_has_no_solutions_or_original_guesses(tmp_path):
    export_inputs(DATA, tmp_path / "inputs.json")
    exported = json.loads((tmp_path / "inputs.json").read_text())
    assert len(exported["cases"]) == 28
    allowed = {"case_id", "headline", "teaser_text", "publication_date", "publication_at"}
    assert all(set(case) == allowed for case in exported["cases"])
    original = next(c for c in exported["cases"] if c["case_id"] == "HT-001")
    assert "Zukäufe" in original["teaser_text"]
    assert all(
        value not in original["teaser_text"]
        for value in ["Analog Devices", "Lattice", "Empower", "Alif", "MN84GA"]
    )
    assert original["publication_at"] is None
    assert sum(bool(c["teaser_text"]) for c in exported["cases"]) == 24
    with pytest.raises(FileExistsError):
        export_inputs(DATA, tmp_path / "inputs.json")


def test_invalid_reference_resolution_cannot_silently_turn_williams_into_hit(tmp_path):
    data = json.loads(DATA.read_text())
    case = next(c for c in data["cases"] if c["reference_number"] == 2)
    case["actual_company"] = "Williams Companies"
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="unresolved"):
        load_references(path)


def test_markdown_and_current_inventory_follow_structured_reference():
    from scanner.hebeltrader.detective.history import inventory_history
    from scanner.hebeltrader.detective.reference_cases import markdown_table

    data = load_references(DATA)
    markdown = (ROOT / "docs/hebeltrader-identification-rules.md").read_text()
    assert markdown_table(data) in markdown
    inventory = inventory_history(ROOT / "docs/hebeltrader-identification-rules.md")
    assert sum(c["original_text_available"] for c in inventory["cases"]) == 17
    adi = next(c for c in inventory["cases"] if c["case_id"] == "HT-001")
    assert adi["first_prediction"] == "Lattice Semiconductor"
    assert "Zukäufe" in adi["original_text"]


def test_new_confirmations_preserve_first_rankings_and_do_not_claim_scanner_hits():
    data = load_references(DATA)
    by = {c["reference_number"]: c for c in data["cases"]}
    slb, db = by[19], by[28]
    assert slb["actual_ticker"] == "SLB"
    assert slb["first_prediction"] == "SLB"
    assert slb["resolution_history"][0]["prior_outcome"] == "unresolved"
    assert db["original_top3"] == ["Deutsche Bank", "Commerzbank", "UBS"]
    assert db["first_prediction"] == db["actual_company"] == "Deutsche Bank"
    assert db["outcome"] == "correct"
    assert db["derivative_wkn"] is None
    assert db["first_prediction_confidence"] is None
    assert not db["autonomous_scanner_success"]
    assert not slb["autonomous_scanner_success"]
    assert not db["independent_benchmark"]
    assert by[20]["outcome"] == "not_identified"
    assert sum(c["outcome"] == "correct" for c in data["cases"]) == 12
    assert sum(c["outcome"] == "wrong" for c in data["cases"]) == 7
    assert sum(c["outcome"] == "unresolved" for c in data["cases"]) == 1
    assert sum(c["outcome"] == "not_tested" for c in data["cases"]) == 7
    assert historical_summary(data)["total"] == 18
