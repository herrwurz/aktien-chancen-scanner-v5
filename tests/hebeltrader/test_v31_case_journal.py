import json
from datetime import UTC, datetime

import pytest

from scanner.hebeltrader.detective.case_journal import CaseJournal
from scanner.hebeltrader.detective.history import freeze_analysis

NOW = datetime(2026, 10, 28, 15, tzinfo=UTC)


def frozen(tmp_path, tag, candidates):
    p = tmp_path / f"{tag}.json"
    freeze_analysis(
        {
            "run_id": tag,
            "case_id": tag,
            "teaser_sha256": "input",
            "identification": {"status": "identified" if candidates else "not_identified"},
            "candidates": [{"asset_id": x, "identity": {"name": x}} for x in candidates],
            "countercandidate_count": 5,
            "analysis_seconds": 2,
            "source_quality": {"primary_documents": 2, "documents": 3},
        },
        p,
    )
    return p


def test_dedup_first_ranking_resolution_correction_and_register_append(tmp_path):
    journal = CaseJournal(tmp_path / "journal", clock=lambda: NOW)
    case = journal.intake(
        {
            "teaser_text": "Unknown  company",
            "headline": "Teaser",
            "author": "Author",
            "issue": "1/26",
        }
    )
    assert journal.intake({"teaser_text": "Unknown company", "headline": "Teaser"}) == case
    assert journal.case(case)["status"] == "neu"
    journal.begin(case)
    assert journal.case(case)["status"] == "in_analyse"
    first = frozen(tmp_path, "first", ["wrong", "right", "third"])
    journal.record_analysis(case, first)
    journal.record_analysis(case, frozen(tmp_path, "second", ["right", "wrong", "third"]))
    resolution = {
        "asset_id": "right",
        "name": "Right Corporation",
        "call_wkn": "ABC123",
        "source": "https://issuer.example/product",
        "basis": "user",
        "error_analysis": "Wrong generic clue",
        "algorithm_change": "Use specific events",
    }
    journal.resolve(case, resolution)
    result = journal.case(case)
    assert result["status"] == "widerlegt"
    assert result["first_prediction"]["candidates"][0]["asset_id"] == "wrong"
    assert result["resolution"]["correct_rank"] == 2
    assert result["resolution"]["product_verification"] == "not_verified"
    journal.resolve(
        case, dict(resolution, asset_id="wrong", error_analysis="Correction of previous resolution")
    )
    assert journal.case(case)["status"] == "bestaetigt"
    assert len([e for e in journal.events() if e["kind"] == "resolution"]) == 2
    register = tmp_path / "rules.md"
    register.write_text("Existing 18 cases\n")
    journal.export_register(register)
    before = register.read_bytes()
    journal.export_register(register)
    assert register.read_bytes() == before
    assert before.startswith(b"Existing 18 cases\n")
    assert b"wrong" in before and b"ABC123" in before
    assert journal.verify()["valid"] is True


def test_same_source_issue_dedup_but_new_issue_is_new_case(tmp_path):
    j = CaseJournal(tmp_path)
    a = {
        "teaser_url": "https://publisher.example/teaser?utm_source=a",
        "issue": "1/26",
        "teaser_text": "One",
    }
    case = j.intake(a)
    assert j.intake(dict(a, teaser_text="Corrected text")) == case
    assert j.intake(dict(a, issue="2/26", teaser_text="Different teaser")) != case


def test_tampered_journal_and_missing_resolution_provenance_rejected(tmp_path):
    j = CaseJournal(tmp_path)
    case = j.intake({"teaser_text": "Unknown"})
    with pytest.raises(ValueError):
        j.resolve(case, {"asset_id": "A"})
    path = tmp_path / "cases.jsonl"
    rows = path.read_text().splitlines()
    r = json.loads(rows[0])
    r["kind"] = "resolution"
    rows[0] = json.dumps(r)
    path.write_text("\n".join(rows) + "\n")
    with pytest.raises(ValueError, match="integrity"):
        j.events()


def test_quality_never_promotes_known_development_cases_to_blind_rates(tmp_path):
    j = CaseJournal(tmp_path / "j", clock=lambda: NOW)
    case = j.intake({"teaser_text": "Historic title", "evaluation_class": "development_regression"})
    j.record_analysis(case, frozen(tmp_path, "historic", ["wrong", "right"]))
    j.resolve(
        case,
        {
            "asset_id": "right",
            "name": "Right",
            "source": "operator supplied resolution",
            "basis": "user",
            "error_analysis": "Generic clue",
        },
    )
    quality = j.quality()
    assert quality["independent"]["total"] == 0
    assert quality["independent"]["top1_rate"] is None
    assert quality["development_regression"]["top3_hits"] == 1
    assert quality["development_regression"]["top1_hits"] == 0
    assert quality["development_regression"]["false_identifications"] == 1
    assert quality["development_regression"]["average_research_seconds"] == 2


def test_independent_cohort_keeps_unresolved_denominator_and_separate_top3(tmp_path):
    j = CaseJournal(tmp_path / "j", clock=lambda: datetime.now(UTC))
    cases = []
    for i in range(2):
        case = j.intake(
            {
                "teaser_text": f"New original {i}",
                "evaluation_class": "prospective_blind",
                "previously_used_for_development": False,
            }
        )
        j.record_analysis(case, frozen(tmp_path, f"new{i}", ["wrong", "right"]))
        cases.append(case)
    j.resolve(
        cases[0],
        {
            "asset_id": "right",
            "name": "Right",
            "source": "Operator archived primary resolution",
            "basis": "primary_source",
            "error_analysis": "Specific clue missed",
            "confirmed_at": datetime.now(UTC).isoformat(),
            "original_sha256": "input",
        },
    )
    q = j.quality()["independent"]
    assert q["total"] == 2
    assert q["resolved_denominator"] == 1
    assert q["unresolved_fraction"] == 0.5
    assert q["top1_rate"] == 0
    assert q["top3_rate"] == 1


def test_alternate_source_alias_survives_later_text_revision(tmp_path):
    j = CaseJournal(tmp_path)
    original = {"teaser_text": "One", "teaser_url": "https://publisher.example/a", "issue": "1/26"}
    case = j.intake(original)
    alias = dict(original, teaser_url="https://publisher.example/b")
    assert j.intake(alias) == case
    assert j.intake(dict(alias, teaser_text="Corrected original")) == case
    assert len(j.cases()) == 1


def test_preexisting_frozen_ranking_cannot_be_registered_as_new_blind_case(tmp_path):
    from datetime import timedelta

    path = frozen(tmp_path, "already_known", ["right"])
    j = CaseJournal(tmp_path / "j", clock=lambda: datetime.now(UTC) + timedelta(minutes=1))
    case = j.intake(
        {
            "teaser_text": "Already analyzed",
            "evaluation_class": "prospective_blind",
            "previously_used_for_development": False,
        }
    )
    j.record_analysis(case, path)
    assert j.quality()["independent"]["total"] == 0


def test_later_solution_can_resolve_empty_first_prediction_without_claiming_hit(tmp_path):
    j = CaseJournal(tmp_path / "j")
    case = j.intake({"teaser_text": "Unknown without enough clues"})
    j.record_analysis(case, frozen(tmp_path, "empty", []))
    result = j.resolve(
        case,
        {
            "asset_id": "right",
            "name": "Right",
            "source": "User resolution",
            "basis": "user",
            "error_analysis": "No candidate possible",
        },
    )
    assert result["case_status"] == "bestaetigt"
    assert result["prediction_outcome"] == "not_identified"
    assert result["correct_rank"] is None
    assert j.quality()["all"]["top1_hits"] == 0
