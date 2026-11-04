"""US-session warrant quote.

Hebeltrader boilerplate: the derivative is only quoted continuously once US trading
starts, because the German book is too thin. That narrows the listing venue to the
US session. A bare US symbol or ADR stays. A home-market ticker (Xetra, Euronext,
Tokyo, Korea, …) is demoted. No company name is hardcoded.
"""

from __future__ import annotations

import re

_US_OPEN = re.compile(r"handelsbeginn\s+in\s+den\s+usa|us-handelsbeginn", re.I)
_CLOCK = re.compile(r"14[:.]\s*30|15[:.]\s*30")
_QUOTED = re.compile(r"quotier\w*|fortlaufend\s+quot", re.I)
_LIQUIDITY = re.compile(
    r"geringe[rn]?\s+liquidit\w*|deutschen\s+b[öo]rsen",
    re.I,
)
# Venue suffixes used in the index pool and EODHD. Single-letter share classes
# (.B) are not venues.
_NON_US_SUFFIX = frozenset(
    {
        "DE",
        "F",
        "XETRA",
        "PA",
        "AS",
        "MI",
        "MC",
        "BR",
        "HE",
        "VI",
        "ST",
        "CO",
        "OL",
        "LS",
        "IR",
        "L",
        "LSE",
        "SW",
        "HK",
        "T",
        "TSE",
        "TO",
        "WAR",
        "WA",
        "PR",
        "KO",
        "KS",
        "TW",
        "SS",
        "SZ",
        "JP",
    }
)
_NON_US_PREFIX = re.compile(
    r"^(?:XETRA|LSE|EPA|FRA|ETR|TYO|HKG|TSE|SWX|MIL|AMS|PAR)\s*[:]",
    re.I,
)
_US_PREFIX = re.compile(r"^(?:NYSE|NASDAQ|AMEX)\s*[:]", re.I)
_HOME_COUNTRY = frozenset(
    {
        "de",
        "germany",
        "deutschland",
        "fr",
        "france",
        "nl",
        "netherlands",
        "the netherlands",
        "it",
        "italy",
        "es",
        "spain",
        "be",
        "belgium",
        "at",
        "austria",
        "ch",
        "switzerland",
        "se",
        "sweden",
        "no",
        "norway",
        "dk",
        "denmark",
        "fi",
        "finland",
        "pt",
        "portugal",
        "ie",
        "ireland",
        "pl",
        "poland",
        "jp",
        "japan",
        "kr",
        "korea",
        "south korea",
        "tw",
        "taiwan",
        "cn",
        "china",
        "hk",
        "hong kong",
        "gb",
        "uk",
        "united kingdom",
    }
)

# Larger than one chart confirmation, same order as other class demotions.
_VENUE_DEMOTE = 36
_NOTE = (
    "Der Schein wird erst zum US-Handelsbeginn quotiert; "
    "dieser Kandidat notiert an einer Börse außerhalb der US-Session."
)


def teaser_quotes_from_us_session(text: str) -> bool:
    """True when the warrant is only streamed from the US open."""
    blob = text or ""
    if _US_OPEN.search(blob):
        return True
    return bool(_CLOCK.search(blob) and _QUOTED.search(blob) and _LIQUIDITY.search(blob))


def listed_outside_us_session(ticker: str | None) -> bool:
    """True for a home-market symbol. Bare US tickers and ADRs stay eligible."""
    if not ticker:
        return False
    raw = str(ticker).strip()
    if _US_PREFIX.search(raw):
        return False
    if _NON_US_PREFIX.search(raw):
        return True
    compact = raw.upper().replace(" ", "")
    if "." not in compact:
        return False
    suffix = compact.rsplit(".", 1)[-1]
    if suffix in {"US", "N", "O"}:
        return False
    if len(suffix) == 1:
        return False
    return suffix in _NON_US_SUFFIX


def _identity(row: dict) -> dict:
    data = row.get("identity")
    if isinstance(data, dict):
        return data
    if data is not None and hasattr(data, "model_dump"):
        return data.model_dump()
    return {}


def row_listed_outside_us_session(row: dict) -> bool:
    identity = _identity(row)
    ticker = identity.get("ticker") or row.get("ticker") or ""
    if ticker:
        return listed_outside_us_session(str(ticker))
    country = (identity.get("country") or "").strip().casefold()
    return country in _HOME_COUNTRY


def apply_us_session_quote(ranked: list[dict], *, teaser_text: str = "") -> dict:
    """Demote home-market listings when the teaser quotes only from the US open."""
    summary: dict = {"status": "applied", "scored": []}
    if not teaser_quotes_from_us_session(teaser_text):
        summary["status"] = "skipped_no_us_session_quote"
        return summary
    if not ranked:
        summary["status"] = "skipped_empty"
        return summary
    for row in ranked:
        if not row_listed_outside_us_session(row):
            summary["scored"].append(
                {"asset_id": row.get("asset_id"), "role": "us_session", "delta": 0}
            )
            continue
        counters = list(row.get("counterarguments") or [])
        if _NOTE not in counters:
            counters.append(_NOTE)
        row["counterarguments"] = counters
        row["us_session_quote"] = {"role": "outside_us_session", "delta": -_VENUE_DEMOTE}
        row["evidence_score"] = int(row.get("evidence_score") or 0) - _VENUE_DEMOTE
        summary["scored"].append(
            {"asset_id": row.get("asset_id"), "role": "outside_us_session", "delta": -_VENUE_DEMOTE}
        )
    ranked.sort(
        key=lambda row: (
            bool(row.get("hard_contradictions")),
            -int(row.get("evidence_score") or 0),
            row.get("asset_id") or "",
        )
    )
    return summary
