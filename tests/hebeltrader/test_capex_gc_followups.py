"""Follow-ups from HT 203/26 resolution: capex plan quality + GC exclusivity."""

from scanner.hebeltrader.detective.chart_check import (
    _death_cross,
    _golden_cross,
    trend_features,
)
from scanner.hebeltrader.detective.utility_fingerprint import (
    extract_utility_fingerprint,
    fingerprint_from_documents,
)


def test_prefers_multi_year_capital_plan_over_proxy_table_noise():
    noisy = (
        "Volume of Transmission Capital Investment $2.507 billion 200.0% 0.040 "
        "in the proxy statement table."
    )
    plan = (
        "AEP is announcing an expanded $100 billion five-year capital plan through 2031 "
        "to serve data center load under take-or-pay agreements."
    )
    assert extract_utility_fingerprint(noisy).capex_billions is None
    fp = extract_utility_fingerprint(plan)
    assert fp.capex_billions == 100.0


def test_fingerprint_merge_keeps_large_plan_not_tiny_primary_table():
    docs = [
        {
            "source_kind": "regulatory",
            "title": "DEF 14A",
            "text": (
                "Volume of Transmission Capital Investment $2.507 billion 200.0% "
                "plus offtake with hyperscale data center customers."
            ),
        },
        {
            "source_kind": "issuer",
            "title": "IR",
            "text": (
                "We signed electric service agreements with data center customers and "
                "raised the five-year capital plan to $78 billion."
            ),
        },
        {
            "source_kind": "news",
            "title": "Wire",
            "text": "Company unveils $100 billion five-year capital plan for the grid.",
        },
    ]
    fp = fingerprint_from_documents(docs)
    assert fp.has_offtake and fp.has_data_center_link
    assert fp.capex_billions == 100.0


def test_latest_cross_makes_golden_and_death_exclusive():
    # Soft decline (EMA death risk) then sharp rally (EMA golden) within lookback.
    closes = (
        [100.0] * 180
        + [100.0 - i * 0.35 for i in range(1, 41)]
        + [86.0 + i * 2.2 for i in range(1, 36)]
    )
    assert not (_golden_cross(closes) and _death_cross(closes))
    features = trend_features(closes)
    assert features is not None
    assert features["golden_cross"] is True
    assert features["death_cross"] is False
    assert features["gd50_ema"] is not None and features["gd200_ema"] is not None
    # EMA GD sits nearer a Wittmer-style ~125 GD50 table than the SMA on this path
    # when price has rebounded hard (EMA50 tracks price faster than SMA50).
    assert features["gd50_ema"] > features["gd50"]


def test_five_year_capex_phrase_variants():
    samples = [
        "five-year, $72 billion capital plan",
        "raised its capital plan to $78 billion",
        "a $100 billion 5-year capital plan",
    ]
    amounts = [extract_utility_fingerprint(s).capex_billions for s in samples]
    assert amounts == [72.0, 78.0, 100.0]
