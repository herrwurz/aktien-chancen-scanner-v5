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


def test_archive_hides_case_without_rewriting_journal_and_is_idempotent(tmp_path):
    j = CaseJournal(tmp_path / "j")
    case = j.intake({"teaser_text": "obsolete test"})
    head_before = j.verify()["head_sha256"]
    j.archive(case, "obsolete operator test")
    j.archive(case, "obsolete operator test")
    assert j.cases() == []
    assert j.cases(include_archived=True)[0]["archived"] is True
    assert j.verify()["head_sha256"] != head_before
    assert len([e for e in j.events() if e["kind"] == "archive"]) == 1
    register = tmp_path / "register.md"
    j.export_register(register)
    assert "archive" in register.read_text()
    j.restore(case, "operator restored case")
    assert j.cases()[0]["archived"] is False


def test_delete_hides_archived_case_from_all_listings(tmp_path):
    j = CaseJournal(tmp_path / "j")
    case = j.intake({"teaser_text": "delete me"})
    j.archive(case, "parked")
    assert len(j.cases(include_archived=True)) == 1
    j.delete(case, "operator removed permanently")
    j.delete(case, "operator removed permanently")
    assert j.cases() == []
    assert j.cases(include_archived=True, listing="all") == []
    assert j.case(case)["deleted"] is True
    assert len([e for e in j.events() if e["kind"] == "delete"]) == 1
    with pytest.raises(ValueError, match="deleted"):
        j.restore(case, "should fail")


def test_only_resolved_case_can_be_promoted_as_prospective_reference(tmp_path):
    j = CaseJournal(tmp_path / "j", clock=lambda: NOW)
    case = j.intake(
        {
            "teaser_text": "new blind case",
            "evaluation_class": "prospective_blind",
            "previously_used_for_development": False,
        }
    )
    j.record_analysis(case, frozen(tmp_path, "blind", ["ASML", "TSM"]))
    with pytest.raises(ValueError, match="resolved"):
        j.promote_reference(case, "purchased report")
    j.resolve(
        case,
        {
            "asset_id": "ASML",
            "name": "ASML Holding",
            "source": "purchased report",
            "basis": "user",
            "error_analysis": "Compared with frozen top three",
        },
    )
    j.promote_reference(case, "operator verified purchased report")
    j.promote_reference(case, "operator verified purchased report")
    state = j.case(case)
    assert state["reference_status"] == "prospective_reference"
    assert len([e for e in j.events() if e["kind"] == "reference_promotion"]) == 1
    references = j.references()
    assert references[0]["reference_number"] == 19
    assert references[0]["case_id"] == case


def test_existing_unresolved_case_can_be_marked_prospective_before_resolution(tmp_path):
    j = CaseJournal(tmp_path / "j")
    case = j.intake({"teaser_text": "live blind teaser"})
    j.record_analysis(case, frozen(tmp_path, "live", ["ASML"]))
    j.mark_prospective(case, "operator confirms solution was not known")
    assert j.case(case)["evaluation_class"] == "prospective_blind"


def test_out_of_competition_hidden_from_listing_quality_and_blind_paths(tmp_path):
    j = CaseJournal(tmp_path / "j", clock=lambda: NOW)
    official = j.intake({"teaser_text": "official teaser"})
    j.record_analysis(official, frozen(tmp_path, "official", ["A"]))
    ooc = j.intake(
        {
            "teaser_text": "midterms ooc teaser",
            "competition_mode": "out_of_competition",
            "headline": "Außer Konkurrenz",
        }
    )
    j.record_analysis(ooc, frozen(tmp_path, "ooc", ["B", "C"]))
    assert [row["case_id"] for row in j.cases()] == [official]
    assert [row["case_id"] for row in j.cases(listing="out_of_competition")] == [ooc]
    assert {row["case_id"] for row in j.cases(listing="all")} == {official, ooc}
    quality = j.quality()
    assert [row["case_id"] for row in quality["cases"]] == [official]
    with pytest.raises(ValueError, match="out_of_competition"):
        j.mark_prospective(ooc, "must not become blind")
    j.resolve(
        ooc,
        {
            "asset_id": "B",
            "name": "OOC Co",
            "source": "purchased report",
            "basis": "user",
            "error_analysis": "ooc only",
        },
    )
    with pytest.raises(ValueError, match="out_of_competition"):
        j.promote_reference(ooc, "must not enter references")
    assert j.references() == []


def test_out_of_competition_solution_pdf_and_dataset_promotion(tmp_path):
    j = CaseJournal(tmp_path / "j", clock=lambda: NOW)
    ooc = j.intake(
        {"teaser_text": "iran ooc", "competition_mode": "out_of_competition", "headline": "Iran"}
    )
    j.record_analysis(ooc, frozen(tmp_path, "iran", ["GOLD"]))
    assert j.cases(listing="out_of_competition")[0]["case_id"] == ooc
    pdf = b"%PDF-1.4 ooc-report"
    stored = j.store_solution_pdf(
        ooc, pdf, extracted={"name": "Gold Co", "call_wkn": "ABC123", "stock_wkn": "A0AAAA"}
    )
    assert stored["pdf_sha256"] == __import__("hashlib").sha256(pdf).hexdigest()
    assert stored["listed_as_official"] is True
    assert (tmp_path / "j" / stored["relative_path"]).read_bytes() == pdf
    assert j.case(ooc)["competition_mode"] == "official"
    assert j.cases(listing="out_of_competition") == []
    assert ooc in {row["case_id"] for row in j.cases(listing="official")}
    assert j.store_solution_pdf(ooc, pdf)["pdf_sha256"] == stored["pdf_sha256"]
    assert len([e for e in j.events() if e["kind"] == "solution_pdf"]) == 1
    assert len([e for e in j.events() if e["kind"] == "listing_promotion"]) == 1
    with pytest.raises(ValueError, match="resolve"):
        j.promote_to_dataset(ooc, {"name": "Gold Co", "source": "purchased report"})
    j.resolve(
        ooc,
        {
            "asset_id": "GOLD",
            "name": "Gold Co",
            "call_wkn": "ABC123",
            "source": "purchased report",
            "basis": "user",
            "error_analysis": "confirmed from PDF",
        },
    )
    promoted = j.promote_to_dataset(
        ooc,
        {
            "name": "Gold Co",
            "ticker": "GOLD",
            "source": "purchased report",
            "call_wkn": "ABC123",
            "stock_wkn": "A0AAAA",
        },
    )
    assert promoted["export_relative_path"].endswith(f"{ooc}.json")
    export = json.loads((tmp_path / "j" / promoted["export_relative_path"]).read_text())
    assert export["kind"] == "hebeltrader_report_dataset_export"
    assert export["competition_mode"] == "official"
    assert export["actual_company"] == "Gold Co"
    assert export["derivative_wkn"] == "ABC123"
    assert (
        j.promote_to_dataset(ooc, {"name": "Gold Co", "source": "purchased report"})["pdf_sha256"]
        == stored["pdf_sha256"]
    )
    assert len([e for e in j.events() if e["kind"] == "dataset_promotion"]) == 1
    register = tmp_path / "register.md"
    j.export_register(register)
    text = register.read_text()
    assert "solution_pdf" in text and "listing_promotion" in text and "dataset_promotion" in text


def test_solution_pdf_without_listing_promotion_heals_ooc(tmp_path):
    """Rüstungsfall-style: PDF on file must leave außer Konkurrenz even without promo event."""
    j = CaseJournal(tmp_path / "j", clock=lambda: NOW)
    case = j.intake(
        {
            "teaser_text": "US-Rüstungsriese ooc",
            "competition_mode": "out_of_competition",
            "headline": "Rüstung",
        }
    )
    j.record_analysis(case, frozen(tmp_path, "defense", ["LMT", "RTX"]))
    # Simulate an older journal that stored the PDF but missed listing_promotion.
    j._append(
        case,
        "solution_pdf",
        {
            "pdf_sha256": "abc123",
            "relative_path": "solution-pdfs/x.pdf",
            "byte_length": 12,
            "extracted": {"name": "RTX"},
        },
    )
    assert j.case(case)["competition_mode"] == "official"
    assert j.cases(listing="out_of_competition") == []
    assert case in {row["case_id"] for row in j.cases(listing="official")}
    assert j.case(case)["listing_promotion"]["reason"] == "solution_pdf_uploaded"
    pdf = b"%PDF-1.4 defense-report"
    stored = j.store_solution_pdf(case, pdf, extracted={"name": "RTX"})
    assert stored["listed_as_official"] is True
    assert j.case(case)["competition_mode"] == "official"
    assert len([e for e in j.events() if e["kind"] == "listing_promotion"]) >= 1


def test_reconcile_promotes_resolves_and_deletes_ambiguous(tmp_path):
    j = CaseJournal(tmp_path / "j", clock=lambda: NOW)
    # Clear hit: PDF extract matches top tip → Erraten after reconcile.
    hit = j.intake({"teaser_text": "hit teaser with pdf"})
    j.record_analysis(hit, frozen(tmp_path, "hit", ["RTX", "LMT"]))
    j._append(
        hit,
        "solution_pdf",
        {
            "pdf_sha256": "hitpdf",
            "relative_path": "solution-pdfs/hit.pdf",
            "byte_length": 8,
            "extracted": {"name": "RTX"},
        },
    )
    # Clear miss: PDF names rank-2 → Falsch after reconcile; also stuck in OOC.
    miss = j.intake(
        {
            "teaser_text": "miss teaser ooc",
            "competition_mode": "out_of_competition",
            "headline": "Miss",
        }
    )
    j.record_analysis(miss, frozen(tmp_path, "miss", ["LMT", "RTX"]))
    j._append(
        miss,
        "solution_pdf",
        {
            "pdf_sha256": "misspdf",
            "relative_path": "solution-pdfs/miss.pdf",
            "byte_length": 8,
            "extracted": {"name": "RTX"},
        },
    )
    # Pure OOC without PDF stays außer Konkurrenz.
    ooc = j.intake(
        {
            "teaser_text": "pure ooc teaser",
            "competition_mode": "out_of_competition",
            "headline": "OOC",
        }
    )
    j.record_analysis(ooc, frozen(tmp_path, "ooc", ["X"]))
    # Ambiguous open official without PDF → delete.
    open_case = j.intake({"teaser_text": "open ambiguous teaser"})
    j.record_analysis(open_case, frozen(tmp_path, "open", ["Y"]))
    # Ambiguous PDF without extractable identity → delete.
    vague = j.intake({"teaser_text": "vague pdf teaser"})
    j.record_analysis(vague, frozen(tmp_path, "vague", ["Z"]))
    j._append(
        vague,
        "solution_pdf",
        {
            "pdf_sha256": "vaguepdf",
            "relative_path": "solution-pdfs/vague.pdf",
            "byte_length": 8,
            "extracted": {},
        },
    )

    summary = j.reconcile_operator_listing()
    assert hit in summary["resolved"]
    assert miss in summary["resolved"]
    assert miss in summary["promoted"]
    assert open_case in summary["deleted"]
    assert vague in summary["deleted"]
    assert ooc in summary["kept_ooc"]
    assert j.case(hit)["resolution"]["prediction_outcome"] == "confirmed"
    assert j.case(miss)["resolution"]["prediction_outcome"] == "refuted"
    assert j.case(miss)["competition_mode"] == "official"
    assert j.case(open_case)["deleted"] is True
    assert j.case(vague)["deleted"] is True
    assert j.case(ooc)["deleted"] is False
    active = {row["case_id"] for row in j.cases(listing="all")}
    assert active == {hit, miss, ooc}
    # Idempotent second pass.
    again = j.reconcile_operator_listing()
    assert again["deleted"] == []
    assert again["resolved"] == []
    assert set(again["clear_active"]) == {hit, miss, ooc}
