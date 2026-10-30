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
    """Bounded score for 'uptrend' and 'decisive chart moment' (price above GD50 and GD200).

    Hebeltrader entries require a confirmed uptrend: price above both averages scores most.
    A deep drawdown from the 1-year high contradicts a 'years of steady gains' claim.
    """
    if not features:
        return 0
    if features["above_gd50"] and features["above_gd200"]:
        score = 12
    elif features["above_gd200"]:
        score = 4
    else:
        score = 0
    score += 2 if features["gd200_rising"] else 0
    score += 1 if features["return_1y_pct"] > 15 else 0
    score += 2 if features["breakout"] else 0
    score -= 4 if features["near_high_pct"] < -25 else 0
    return max(0, score)


def fetch_eod_bars(
    ticker,
    *,
    token=None,
    client=None,
    from_date=None,
    to_date=None,
    exchange="US",
):
    """Return oldest-to-newest ``{date, close}`` bars, or None on auth/network failure."""
    token = token or os.environ.get("EODHD_API_TOKEN")
    if not token or not ticker:
        return None
    to_date = to_date or date.today()
    from_date = from_date or (to_date - timedelta(days=420))
    symbol = ticker if "." in ticker else f"{ticker}.{exchange}"
    params = {
        "api_token": token,
        "fmt": "json",
        "from": from_date.isoformat(),
        "to": to_date.isoformat(),
    }
    try:
        response = (client or httpx).get(EOD_URL.format(symbol=symbol), params=params, timeout=10)
        response.raise_for_status()
        rows = response.json()
    except (httpx.HTTPError, ValueError):
        return None
    bars = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict) or not row.get("date"):
            continue
        close = row.get("adjusted_close")
        if close is None:
            close = row.get("close")
        if close is None:
            continue
        bars.append({"date": row["date"][:10], "close": float(close)})
    bars.sort(key=lambda item: item["date"])
    return bars


def closes_through(bars, as_of):
    """Closes with bar date ≤ ``as_of`` (ISO date or ``date``)."""
    if bars is None:
        return None
    cutoff = as_of.isoformat() if isinstance(as_of, date) else str(as_of)[:10]
    return [bar["close"] for bar in bars if bar["date"] <= cutoff]


def fetch_closes(ticker, *, token=None, client=None, today=None, exchange="US"):
    today = today or date.today()
    bars = fetch_eod_bars(
        ticker,
        token=token,
        client=client,
        from_date=today - timedelta(days=420),
        to_date=today,
        exchange=exchange,
    )
    if bars is None:
        return None
    return closes_through(bars, today)


def check(ticker, **options):
    closes = fetch_closes(ticker, **options)
    if closes is None:
        return {"status": "unavailable"}
    features = trend_features(closes)
    if features is None:
        return {"status": "insufficient_history"}
    return {"status": "ok", "retrieved_at": datetime.now(UTC).isoformat(), **features}
