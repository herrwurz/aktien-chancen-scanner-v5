import httpx

from scanner.hebeltrader.detective.chart_check import chart_score, check, trend_features
from scanner.hebeltrader.detective.structure_screen import ticker_for


def test_uptrend_with_breakout_scores_high():
    closes = [100 + i * 0.3 for i in range(300)]
    features = trend_features(closes)
    assert features["above_gd200"] and features["gd200_rising"] and features["breakout"]
    assert chart_score(features) == 17


def test_downtrend_scores_zero_and_short_history_is_none():
    assert chart_score(trend_features([300 - i * 0.5 for i in range(300)])) == 0
    assert trend_features([1.0] * 50) is None
    assert chart_score(None) == 0


def test_check_without_token_is_unavailable(monkeypatch):
    monkeypatch.delenv("EODHD_API_TOKEN", raising=False)
    assert check("SNPS") == {"status": "unavailable"}


def test_check_uses_provider_rows():
    rows = [{"close": 100 + i * 0.3} for i in range(300)]
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=rows)))
    result = check("SNPS", token="t", client=client)
    assert result["status"] == "ok" and result["breakout"]


def test_ticker_lookup():
    assert ticker_for("Synopsys") == "SNPS"
    assert ticker_for("Unbekannt AG") is None


def _features(**values):
    base = {
        "above_gd50": False,
        "above_gd200": False,
        "gd200_rising": False,
        "return_1y_pct": 0,
        "near_high_pct": -5,
        "breakout": False,
    }
    return base | values


def test_price_above_both_averages_outranks_single_average_and_drawdown():
    both = chart_score(_features(above_gd50=True, above_gd200=True))
    only200 = chart_score(_features(above_gd200=True, gd200_rising=True, return_1y_pct=40))
    crashed = chart_score(_features(above_gd200=True, near_high_pct=-48))
    assert both > only200 > crashed


def test_ticker_lookup_handles_legal_forms_and_aliases():
    assert ticker_for("NVIDIA Corporation") == "NVDA"
    assert ticker_for("Applied Materials Inc.") == "AMAT"
    assert ticker_for("Taiwan Semiconductor Manufacturing Company Ltd.") == "TSM"


def test_name_match_uses_whole_words():
    assert ticker_for("Intuit Inc.") != ticker_for("Intuitive Surgical Inc.")
    assert ticker_for("Armstrong World Industries") is None
    assert ticker_for("Sapient") is None
