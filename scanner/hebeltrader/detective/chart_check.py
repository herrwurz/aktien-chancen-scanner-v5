"""Deterministic chart-clue check (uptrend, GD50/GD200, breakout) from daily closes."""

import os
from datetime import UTC, date, datetime, timedelta

import httpx

EOD_URL = "https://eodhd.com/api/eod/{symbol}"


def _sma(values, n):
    return sum(values[-n:]) / n if len(values) >= n else None


def trend_features(closes):
    """Return trend facts for oldest-to-newest closes, or None if history is too short."""
    closes = [float(c) for c in closes if c]
    if len(closes) < 200:
        return None
    last, gd50, gd200 = closes[-1], _sma(closes, 50), _sma(closes, 200)
    prior_gd200 = sum(closes[-220:-20]) / 200 if len(closes) >= 220 else None
    year = closes[-252:]
    recent = closes[-60:]
    return {
        "last": round(last, 2),
        "gd50": round(gd50, 2),
        "gd200": round(gd200, 2),
        "above_gd50": last > gd50,
        "above_gd200": last > gd200,
        "gd200_rising": prior_gd200 is not None and gd200 > prior_gd200,
        "return_1y_pct": round((last / year[0] - 1) * 100, 1),
        "near_high_pct": round((last / max(year) - 1) * 100, 1),
        # Breakout: close above the prior 60-day consolidation high, excluding the last 5 days.
        "breakout": last >= max(recent[:-5]) if len(recent) > 5 else False,
    }


def chart_score(features):
    """Small bounded bonus for 'long-term uptrend' and 'breakout' teaser wording."""
    if not features:
        return 0
    score = 0
    score += 4 if features["above_gd200"] and features["gd200_rising"] else 0
    score += 2 if features["above_gd50"] else 0
    score += 2 if features["return_1y_pct"] > 15 else 0
    score += 2 if features["breakout"] else 0
    return score


def fetch_closes(ticker, *, token=None, client=None, today=None, exchange="US"):
    token = token or os.environ.get("EODHD_API_TOKEN")
    if not token or not ticker:
        return None
    today = today or date.today()
    symbol = ticker if "." in ticker else f"{ticker}.{exchange}"
    params = {
        "api_token": token,
        "fmt": "json",
        "from": (today - timedelta(days=420)).isoformat(),
        "to": today.isoformat(),
    }
    try:
        response = (client or httpx).get(EOD_URL.format(symbol=symbol), params=params, timeout=10)
        response.raise_for_status()
        rows = response.json()
    except (httpx.HTTPError, ValueError):
        return None
    return [r.get("adjusted_close") or r.get("close") for r in rows if isinstance(r, dict)]


def check(ticker, **options):
    closes = fetch_closes(ticker, **options)
    if closes is None:
        return {"status": "unavailable"}
    features = trend_features(closes)
    if features is None:
        return {"status": "insufficient_history"}
    return {"status": "ok", "retrieved_at": datetime.now(UTC).isoformat(), **features}
