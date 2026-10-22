from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from scanner.hebeltrader.parser import extract_pdf

FIXTURES = Path(__file__).parents[1] / "fixtures" / "hebeltrader"


def read(name):
    return extract_pdf((FIXTURES / name).read_bytes())


def test_separate_derivative_and_stock_with_evidence():
    result = read("complete.pdf")
    assert result.publication_date == date(2025, 2, 14)
    assert (result.issue_number, result.issue_year) == (25, 2025)
    assert len(result.recommendations) == 1
    r = result.recommendations[0]
    assert r.values["stock_name"] == "Muster AG"
    assert r.values["derivative_wkn"] == "AB1C23"
    assert r.values["stock_wkn"] == "123456"
    assert r.values["entry_price"] == Decimal("1.25")
    assert r.values["stock_price"] == Decimal("100.50")
    assert r.values["strike"] == Decimal("1250.50")
    assert r.values["omega"] == Decimal("4.2")
    assert r.values["crv"] == Decimal("3.5")
    assert r.values["maturity_date"] == date(2025, 12, 19)
    assert r.values["stock_target1"] == 120
    assert r.values["derivative_target1"] == Decimal("2.50")
    assert r.values["stock_stop1"] == 90
    assert r.values["issuer"] == "Muster Bank"
    assert r.values["entry_kind"] == "indication"
    assert r.evidence["stock_price"][0]["page"] == 2
    assert r.evidence["entry_price"][0]["page"] == 1
    assert r.evidence["entry_price"][0]["bbox"]
    assert "1,25" in r.evidence["entry_price"][0]["raw"]
    assert result.pages[0]["text"]


def test_ruled_table_is_extracted():
    result = read("table.pdf")
    assert result.pages[0]["tables"]
    assert result.recommendations[0].values["entry_price"] == Decimal("2.50")


def test_missing_and_conflicting_values_are_not_invented():
    result = read("incomplete.pdf")
    r = result.recommendations[0]
    assert r.values.get("issuer") is None
    assert r.values.get("entry_price") is None
    assert r.values.get("strike") is None
    assert r.values.get("derivative_target1") is None
    assert {"missing_field", "invalid_value", "conflicting_values"} <= {f["code"] for f in r.flags}
    assert len(r.evidence["derivative_target1"]) == 2


def test_multiple_recommendations_do_not_mix_values():
    result = read("multiple.pdf")
    assert len(result.recommendations) == 2
    assert [r.values["stock_name"] for r in result.recommendations] == ["Muster AG", "Zweite AG"]
    assert [r.values["stock_wkn"] for r in result.recommendations] == ["123456", "654321"]


def test_conflicting_metadata_requires_review():
    result = read("metadata_conflict.pdf")
    assert result.publication_date is None
    assert any(f["code"] == "metadata_conflict" for f in result.flags)


def test_no_date_is_not_inferred():
    result = read("no_date.pdf")
    assert result.publication_date is None
    assert result.issue_number is None


def test_image_only_pdf_is_flagged_for_ocr():
    result = read("scan.pdf")
    assert not result.recommendations
    assert any(f["code"] == "ocr_required" for f in result.flags)


def test_broken_pdf_raises_sanitized_extraction_error():
    with pytest.raises(ValueError, match="PDF"):
        read("broken.pdf")
