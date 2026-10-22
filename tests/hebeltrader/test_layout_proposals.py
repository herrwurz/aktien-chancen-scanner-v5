import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scanner.hebeltrader.layout_proposals import suggest_stock_repairs

CASES = json.loads(
    (Path(__file__).parents[1] / "fixtures/hebeltrader/v14-audit-five.json").read_text()
)["cases"]


def bound(case):
    data = json.dumps(case, sort_keys=True).encode()
    sha = hashlib.sha256(data).hexdigest()
    doc = SimpleNamespace(sha256=sha, original_pdf=data, pages=case["pages"])
    rec = SimpleNamespace(
        document_sha=sha, ordinal=1, stock_name=case["stock_name"], flags=case["flags"]
    )
    for field, value in case["original_values"].items():
        setattr(rec, field, value)
    return doc, rec


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["source_sha"][:8])
def test_real_five_audit_cases_produce_only_cited_pending_repairs(case):
    doc, rec = bound(case)
    before = dict(vars(rec))
    result = suggest_stock_repairs(doc, rec)
    assert result["status"] == "supported_proposal"
    assert {p["field"] for p in result["proposals"]} == set(case["missing"])
    assert vars(rec) == before
    for proposal in result["proposals"]:
        assert proposal["requires_manual_review"] is True
        assert proposal["evidence"][0]["page"] == 3
        assert proposal["document_sha"] == doc.sha256
        assert proposal["ordinal"] == 1
    expected = {
        "0423a87f": ("stock_wkn", "ENAG99"),
        "52e053b7": ("stock_target2", "91.20"),
        "5cf16313": ("stock_wkn", "851921"),
        "ca53f7e4": ("stock_wkn", "893579"),
        "e73f23ac": ("stock_wkn", "A1JWVX"),
    }
    field, value = expected[case["source_sha"][:8]]
    assert next(p["value"] for p in result["proposals"] if p["field"] == field) == value


def test_unknown_alias_or_mixed_instruments_withholds_repairs():
    case = next(c for c in CASES if c["source_sha"].startswith("5cf16313"))
    doc, rec = bound(case)
    doc.pages = doc.pages[:1]
    assert suggest_stock_repairs(doc, rec)["proposals"] == []
    doc, rec = bound(case)
    doc.pages = [dict(doc.pages[0], regions=[doc.pages[0]["regions"][0] * 2]), doc.pages[1]]
    assert suggest_stock_repairs(doc, rec)["proposals"] == []


def test_original_hash_mismatch_rejects_proposals():
    doc, rec = bound(CASES[0])
    doc.original_pdf = b"changed"
    assert suggest_stock_repairs(doc, rec)["proposals"] == []


def test_derivative_heading_or_duplicate_wkn_never_yields_stock_repairs():
    import copy

    case = copy.deepcopy(CASES[0])
    region = case["pages"][0]["regions"][0]
    region[0]["text"] = "Optionsschein Call"
    doc, rec = bound(case)
    assert suggest_stock_repairs(doc, rec)["proposals"] == []


def test_no_missing_target_is_estimated():
    import copy

    case = copy.deepcopy(next(c for c in CASES if c["source_sha"].startswith("52e053b7")))
    region = case["pages"][0]["regions"][0]
    case["pages"][0]["regions"][0] = [r for r in region if not r["text"].startswith("Kursziel 2")]
    doc, rec = bound(case)
    assert not any(
        p["field"] == "stock_target2" for p in suggest_stock_repairs(doc, rec)["proposals"]
    )


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["source_sha"][:8])
def test_five_problem_pdf_rule_columns_remain_cited(case):
    from scanner.hebeltrader.rule_assistant import suggest_layout_rule_hints

    doc, rec = bound(case)
    hints = suggest_layout_rule_hints(doc, rec)
    assert {"partial_fraction", "after_target1"} <= {h["kind"] for h in hints}
    assert all(h["evidence"][0]["page"] == 3 for h in hints)
    assert all(h["requires_manual_review"] for h in hints)


def test_missing_recommendation_name_does_not_adopt_an_alias_from_the_document():
    case = next(c for c in CASES if c["source_sha"].startswith("5cf16313"))
    doc, rec = bound(case)
    rec.stock_name = None
    assert suggest_stock_repairs(doc, rec)["proposals"] == []
