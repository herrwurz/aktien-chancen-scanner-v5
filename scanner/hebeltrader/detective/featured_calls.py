"""Blocklist of recently featured HEBELTRADER underlyings (exclusion only).

Past published picks are never used as solutions or ranking targets. They only remove
hypothesis candidates when a prior call is assumed still open.
"""

from __future__ import annotations

import json
import re
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

FEATURED_CALLS = Path(__file__).resolve().parent / "featured_calls.json"
DEFAULT_LOOKBACK_DAYS = 180


def _company_key(value):
    value = (value or "").casefold()
    value = re.sub(
        r"\b(?:incorporated|inc|corporation|corp|limited|ltd|plc|ag|se|sa|nv|spa|group|co)\b",
        " ",
        value,
    )
    return re.sub(r"[^a-z0-9]", "", value)


@lru_cache(maxsize=1)
def load_featured_calls(path=None):
    file = Path(path) if path is not None else FEATURED_CALLS
    payload = json.loads(file.read_text(encoding="utf-8"))
    if payload.get("kind") != "hebeltrader_featured_calls_blocklist":
        raise ValueError("featured_calls file has unexpected kind")
    return payload


def blocked_features(as_of, *, lookback_days=None, featured=None):
    """Return exclusion sets for hypotheses as of a teaser publication date.

    Only features strictly before ``as_of`` and within the lookback window are blocked.
    Same-day / future features are ignored (no self-exclusion of the unresolved case).
    """
    if not as_of:
        return {
            "tickers": set(),
            "names": set(),
            "entries": [],
            "lookback_days": lookback_days,
            "status": "no_publication_date",
        }
    as_of_date = date.fromisoformat(str(as_of)[:10])
    payload = featured if featured is not None else load_featured_calls()
    if lookback_days is None:
        window = int(payload.get("default_lookback_days", DEFAULT_LOOKBACK_DAYS))
    else:
        window = int(lookback_days)
    earliest = as_of_date - timedelta(days=window)
    tickers, names, entries = set(), set(), []
    for call in payload.get("calls") or []:
        featured_raw = call.get("featured_date")
        if not featured_raw:
            continue
        featured_date = date.fromisoformat(str(featured_raw)[:10])
        if not (earliest <= featured_date < as_of_date):
            continue
        ticker = call.get("ticker")
        company = call.get("company")
        if ticker:
            tickers.add(str(ticker))
        if company:
            names.add(_company_key(company))
        entries.append(
            {
                "company": company,
                "ticker": ticker,
                "featured_date": featured_date.isoformat(),
                "featured_issue": call.get("featured_issue"),
                "source_case_id": call.get("source_case_id"),
            }
        )
    return {
        "tickers": tickers,
        "names": names,
        "entries": entries,
        "lookback_days": window,
        "as_of": as_of_date.isoformat(),
        "status": "ok",
    }


def is_blocked(asset, blocked):
    """True when asset ticker or normalized name is in the blocked sets."""
    if not blocked or blocked.get("status") == "no_publication_date":
        return False
    ticker = asset.get("ticker")
    if ticker and ticker in blocked.get("tickers", ()):
        return True
    return _company_key(asset.get("name")) in blocked.get("names", ())
