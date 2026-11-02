"""Technical buy-signal detection and PIT matrix verification beyond Golden Cross."""

from scanner.hebeltrader.detective.chart_check import trend_features
from scanner.hebeltrader.detective.chart_signals import (
    normalize_ticker,
    signals_in_quote,
    teaser_chart_clues,
)
from scanner.hebeltrader.detective.investigation import _apply_chart_signal_matrix
from scanner.hebeltrader.detective.market_screen import match_score


def test_teaser_detects_common_german_buy_signals():
    text = (
        "Nach der Korrektur hat die Aktie die 200-Tage-Linie erneut verteidigt. "
        "Charttechnisch hat sich zudem ein kraftvolles Golden Cross gebildet. "
        "MACD liefert ein Kaufsignal, der RSI kommt aus dem überverkauften Bereich, "
        "und der Ausbruch auf ein neues Rekordhoch steht bevor."
    )
    clues = set(teaser_chart_clues(text))
    assert "golden_cross" in clues
    assert "above_gd200" in clues or "gd200_reclaim" in clues
    assert "macd_bullish_cross" in clues
    assert "rsi_oversold_rebound" in clues
    assert "breakout" in clues or "new_high" in clues


def test_normalize_ticker_strips_venue_prefix():
    assert normalize_ticker("NYSE NEE") == "NEE"
    assert normalize_ticker("NASDAQ:AAPL") == "AAPL"
    assert normalize_ticker("IBE.MC") == "IBE.MC"


def test_matrix_contradicts_breakout_and_confirms_gd200():
    ranked = [
        {
            "chart": {
                "status": "ok",
                "breakout": False,
                "above_gd200": True,
                "gd200_reclaim": True,
                "golden_cross": False,
            },
            "evidence_matrix": [
                {
                    "clue_id": "ai:bo",
                    "status": "unknown",
                    "quote": "Gelingt der charttechnische Ausbruch, startet die Rallye.",
                },
                {
                    "clue_id": "ai:gd",
                    "status": "unknown",
                    "quote": (
                        "Nach der Korrektur hat die Aktie die 200-Tage-Linie erneut verteidigt."
                    ),
                },
            ],
            "unknown_clues": ["ai:bo", "ai:gd"],
        }
    ]
    _apply_chart_signal_matrix(ranked)
    by_id = {c["clue_id"]: c for c in ranked[0]["evidence_matrix"]}
    assert by_id["ai:bo"]["status"] == "contradicted"
    assert by_id["ai:gd"]["status"] == "confirmed"
    assert ranked[0]["unknown_clues"] == []


def test_signals_in_quote_maps_macd_and_rsi():
    specs = signals_in_quote("Der MACD kreuzt bullisch, RSI überverkauft verlassen.")
    names = {s["clue"] for s in specs}
    assert "macd_bullish_cross" in names
    assert "rsi_oversold_rebound" in names


def test_match_score_penalizes_missing_claimed_breakout():
    features = {
        "above_gd50": True,
        "above_gd200": True,
        "gd200_rising": False,
        "return_1y_pct": 0,
        "near_high_pct": -1,
        "breakout": False,
        "golden_cross": False,
        "in_correction": False,
        "steady_uptrend": False,
        "new_52w_high": False,
        "macd_bullish_cross": False,
        "rsi_oversold_rebound": False,
        "gd200_reclaim": False,
        "death_cross": False,
    }
    with_claim = match_score(features, ["breakout"])
    without = match_score(features, [])
    assert with_claim < without


def test_macd_and_rsi_features_present_on_uptrend():
    closes = [100 + i * 0.4 for i in range(300)]
    features = trend_features(closes)
    assert features is not None
    assert "macd_bullish_cross" in features
    assert "rsi_14" in features
    assert "death_cross" in features
    assert features["death_cross"] is False
