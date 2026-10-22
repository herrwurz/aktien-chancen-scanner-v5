from decimal import Decimal

import pytest
from v21_cases import CASES, build_case

from scanner.hebeltrader.domain import RecommendationData
from scanner.hebeltrader.parser import extract_pdf, parse_fields, prose_crv


@pytest.mark.parametrize("index", range(5), ids=[x[0] for x in CASES])
def test_known_cases_have_one_real_recommendation(tmp_path, index):
    path = tmp_path / CASES[index][0]
    build_case(path, index)
    result = extract_pdf(path.read_bytes())
    assert len(result.recommendations) == 1
    rec = result.recommendations[0]
    assert rec.values["derivative_wkn"] == CASES[index][1]
    assert rec.values["entry_price"] == Decimal(CASES[index][2])
    assert rec.values["crv"] == Decimal("3.3")
    assert rec.values.get("issuer") is None
    if index == 4:
        assert rec.values["product_type"] == "Turbo Unlimited Long"
        assert rec.values["term_text"] == "open end"
        assert rec.values.get("maturity_date") is None
        assert not any(f.get("field") == "maturity_date" for f in rec.flags)


def test_open_end_label_is_explicit_not_an_invented_date():
    rec = RecommendationData()
    parse_fields(rec, [dict(text="Laufzeit Open-End", page=1, bbox=[1, 1, 100, 20])])
    assert rec.values["term_text"] == "open end"
    assert rec.values.get("maturity_date") is None


@pytest.mark.parametrize("token", ["3.3", "3,3,4", "3abc", "3.3."])
def test_prose_crv_does_not_accept_numeric_prefix(token):
    rec = RecommendationData()
    prose_crv(
        rec, {"number": 1, "regions": [[dict(text=f"(CRV) von {token}", bbox=[0, 0, 100, 20])]]}
    )
    assert rec.values.get("crv") is None


@pytest.mark.parametrize("token", ["3,3!", "3,3."])
def test_prose_crv_preserves_terminal_sentence_punctuation(token):
    rec = RecommendationData()
    prose_crv(
        rec, {"number": 1, "regions": [[dict(text=f"(CRV) von {token}", bbox=[0, 0, 100, 20])]]}
    )
    assert rec.values["crv"] == Decimal("3.3")
