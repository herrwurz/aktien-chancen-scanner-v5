"""Teaser chart buy-signal vocabulary and PIT verification specs.

Signal definitions follow common German retail TA (trading.de, finanzradar.de):
Golden/Death Cross, GD200 reclaim, breakout, MACD cross, RSI rebound, new highs.
A chart match never alone identifies a stock; it only confirms/contradicts claims.
"""

from __future__ import annotations

import re

# Registry: teaser/quote regex → PIT feature + matrix reasons (retail TA vocabulary).
SIGNAL_SPECS: tuple[dict, ...] = (
    {
        "clue": "golden_cross",
        "pattern": r"golden[\s-]*cross|goldenes?\s+kreuz",
        "feature": "golden_cross",
        "confirm_reason": "eod_golden_cross_within_20d_pit",
        "contradict_reason": "eod_no_recent_golden_cross_pit",
        "cluster": "chart:eodhd_sma50_sma200",
        "match_bonus": 8,
        "match_penalty": -4,
    },
    {
        "clue": "death_cross",
        "pattern": r"death[\s-]*cross|todeskreuz|todes[\s-]*kreuz",
        "feature": "death_cross",
        "confirm_reason": "eod_death_cross_within_20d_pit",
        "contradict_reason": "eod_no_recent_death_cross_pit",
        "cluster": "chart:eodhd_sma50_sma200",
        # Death Cross is bearish; confirming it against a bullish teaser is rare.
        "match_bonus": 0,
        "match_penalty": 0,
    },
    {
        "clue": "above_gd200",
        "pattern": (
            r"200[\s-]*tage[\s-]*linie\s+(?:\w+\s+){0,2}"
            r"(?:zurückerobert|verteidigt|überwunden)"
            r"|über\s+der\s+200[\s-]*tage[\s-]*linie"
        ),
        "feature": "above_gd200",
        "confirm_reason": "eod_price_above_sma200_pit",
        "contradict_reason": "eod_price_below_sma200_pit",
        "cluster": "chart:eodhd_sma200",
        "match_bonus": 6,
        "match_penalty": -6,
    },
    {
        "clue": "gd200_reclaim",
        "pattern": (
            r"200[\s-]*tage[\s-]*linie\s+(?:\w+\s+){0,2}"
            r"erneut\s+(?:zurückerobert|erobert|genommen|verteidigt|überwunden)"
            r"|die\s+200[\s-]*tage[\s-]*linie\s+erneut\s+"
            r"(?:erobert|genommen|verteidigt|überwunden)"
        ),
        "feature": "gd200_reclaim",
        "confirm_reason": "eod_sma200_reclaim_within_20d_pit",
        "contradict_reason": "eod_no_recent_sma200_reclaim_pit",
        "cluster": "chart:eodhd_sma200",
        "match_bonus": 6,
        "match_penalty": -4,
    },
    {
        "clue": "breakout",
        "pattern": (
            r"ausbruch(?:salarm)?|befreiungsschlag|rallye|rally|kaufsignal|"
            r"charttechnische[rn]?\s+(?:ausbruch|befreiungsschlag)|entscheidenden\s+moment"
        ),
        "feature": "breakout",
        "confirm_reason": "eod_breakout_above_60d_high_pit",
        "contradict_reason": "eod_no_breakout_vs_60d_high_pit",
        "cluster": "chart:eodhd_breakout_60d",
        "match_bonus": 3,
        "match_penalty": -2,
    },
    {
        "clue": "new_high",
        "pattern": (
            r"rekordhoch|allzeithoch|jahreshoch|"
            r"neues\s+(?:rekord)?hoch|auf\s+ein\s+neues\s+rekordhoch"
        ),
        "feature": "new_52w_high",
        "confirm_reason": "eod_at_52w_high_pit",
        "contradict_reason": "eod_not_at_52w_high_pit",
        "cluster": "chart:eodhd_52w_high",
        "match_bonus": 4,
        "match_penalty": -3,
    },
    {
        "clue": "macd_bullish_cross",
        "pattern": (
            r"\bmacd\b.{0,48}(?:kaufsignal|kreuz|überkreuz|bullisch|positiv)"
            r"|(?:kaufsignal|kreuz|überkreuz).{0,48}\bmacd\b"
        ),
        "feature": "macd_bullish_cross",
        "confirm_reason": "eod_macd_bullish_cross_within_20d_pit",
        "contradict_reason": "eod_no_recent_macd_bullish_cross_pit",
        "cluster": "chart:eodhd_macd_12_26_9",
        "match_bonus": 5,
        "match_penalty": -3,
    },
    {
        "clue": "rsi_oversold_rebound",
        "pattern": (
            r"\brsi\b.{0,40}(?:überverkauft|oversold|unter\s+30|aus\s+dem\s+überverkauft)"
            r"|überverkauft(?:em|en)?\s+(?:bereich|niveau|zone)"
        ),
        "feature": "rsi_oversold_rebound",
        "confirm_reason": "eod_rsi_oversold_rebound_pit",
        "contradict_reason": "eod_no_rsi_oversold_rebound_pit",
        "cluster": "chart:eodhd_rsi14",
        "match_bonus": 4,
        "match_penalty": -2,
    },
    {
        "clue": "correction",
        "pattern": r"korrektur|rücksetzer|konsolidierung",
        "feature": "in_correction",
        "confirm_reason": "eod_pullback_from_52w_high_pit",
        "contradict_reason": "eod_no_material_pullback_pit",
        "cluster": "chart:eodhd_52w_drawdown",
        "match_bonus": 2,
        "match_penalty": 0,
    },
    {
        "clue": "steady_uptrend",
        "pattern": r"seit\s+jahren\s+(?:\w+\s+)?(?:kontinuierlich\s+)?nach\s+oben",
        "feature": "steady_uptrend",
        "confirm_reason": "eod_multi_year_uptrend_proxy_pit",
        "contradict_reason": "eod_uptrend_proxy_absent_pit",
        "cluster": "chart:eodhd_trend",
        "match_bonus": 4,
        "match_penalty": -3,
    },
)


def _compiled():
    return tuple({**spec, "regex": re.compile(spec["pattern"], re.I)} for spec in SIGNAL_SPECS)


SIGNAL_SPECS_COMPILED = _compiled()


def teaser_chart_clues(text: str) -> list[str]:
    clean = text or ""
    return [spec["clue"] for spec in SIGNAL_SPECS_COMPILED if spec["regex"].search(clean)]


def signals_in_quote(quote: str) -> list[dict]:
    return [spec for spec in SIGNAL_SPECS_COMPILED if spec["regex"].search(quote or "")]


def normalize_ticker(ticker: str | None) -> str | None:
    """Strip venue prefixes like ``NYSE NEE`` / ``NASDAQ:AAPL`` → bare symbol."""
    if not ticker:
        return None
    value = str(ticker).strip()
    value = re.sub(
        r"^(NYSE|NASDAQ|AMEX|XETRA|LSE|EPA|FRA|ETR|TYO|HKG)\s*[:\s]+",
        "",
        value,
        flags=re.I,
    )
    value = value.strip()
    return value or None
