from decimal import Decimal

import pytest

from scanner.hebeltrader.calculations import calculate_crv
from scanner.hebeltrader.domain import RecommendationData
from scanner.hebeltrader.parser import parse_fields


def recommendation(price="2,00 EUR", target="4,00 EUR", stop="1,00 EUR"):
    r = RecommendationData()
    lines = [
        dict(text=t, page=1, bbox=[390, i * 20, 550, i * 20 + 12])
        for i, t in enumerate(
            ["WKN AB1C23", f"Akt. Kurs {price}", f"Ziel 1 {target}", f"Stopp 1 {stop}"]
        )
    ]
    parse_fields(r, lines)
    return r


def test_calculated_crv_never_overwrites_original():
    r = recommendation()
    r.values["crv"] = Decimal("9.9")
    calculate_crv(r)
    item = r.evidence["_calculated_crv"][0]
    assert item["kind"] == "calculated"
    assert Decimal(item["value"]) == 2
    assert item["target"] == "derivative_target1"
    assert item["inputs"]["entry_price"] == "2.00"
    assert r.values["crv"] == Decimal("9.9")
    assert item["source_evidence"]["derivative_stop1"][0]["page"] == 1


@pytest.mark.parametrize(
    ("price", "target", "stop"),
    [
        ("2,00 EUR", "4,00 USD", "1,00 EUR"),
        ("2,00", "4,00 EUR", "1,00 EUR"),
        ("2,00 EUR", "4,00 EUR", "2,00 EUR"),
        ("2,00 EUR", "1,00 EUR", "1,00 EUR"),
        ("0,00 EUR", "4,00 EUR", "0,00 EUR"),
    ],
)
def test_ambiguous_or_invalid_risk_never_computes(price, target, stop):
    r = recommendation(price, target, stop)
    calculate_crv(r)
    assert not r.evidence.get("_calculated_crv")
    assert any(f["code"] == "crv_not_computable" for f in r.flags)


def test_conflicting_quotes_do_not_compute():
    r = recommendation()
    parse_fields(r, [dict(text="Akt. Kurs 3,00 EUR", page=1, bbox=[390, 20, 550, 32])])
    calculate_crv(r)
    assert not r.evidence.get("_calculated_crv")
