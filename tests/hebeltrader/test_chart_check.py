import httpx

from scanner.hebeltrader.detective.chart_check import chart_score, check, trend_features
from scanner.hebeltrader.detective.structure_screen import ticker_for


def test_uptrend_with_breakout_scores_high():
    closes = [100 + i * 0.3 for i in range(300)]
    features = trend_features(closes)
    assert features["above_gd200"] and features["gd200_rising"] and features["breakout"]
    assert chart_score(features) == 10


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
