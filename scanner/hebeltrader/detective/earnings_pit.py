"""Point-in-time falsification for claimed quarterly results and all-time highs.

When a teaser already asserts strong quarterly numbers (or an all-time high), any
candidate whose results / ATH status was not public at ``publication_at`` gets a
hard contradiction. Morning HEBELTRADER Stand (Europe/Vienna) cannot use US
same-day before-open or after-close prints.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import httpx

from .chart_check import fetch_eod_bars

VIENNA = ZoneInfo("Europe/Vienna")
US_EASTERN = ZoneInfo("America/New_York")

_QUARTERLY_CLAIM = re.compile(
    r"quartalszahlen|quartalsergebnis|quartalszahlen|earnings(?:\s+beat)?|"
    r"quarterly results|starke quartals",
    re.I,
)
_ATH_CLAIM = re.compile(r"allzeithoch|all[\s-]?time[\s-]?high|rekordhoch| ATH\b", re.I)

_DATE_ISO = re.compile(r"\b(202\d)-(\d{2})-\d{2}\b")
_DATE_US = re.compile(
    r"\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|"
    r"Nov(?:ember)?|Dec(?:ember)?)\.?\s+(\d{1,2}),?\s+(202\d)\b",
    re.I,
)
_DATE_EU = re.compile(r"\b(\d{1,2})[./](\d{1,2})[./](202\d)\b")
_AFTER_CLOSE = re.compile(
    r"after(?:\s+the)?\s+close|nach\s+b[öo]rsenschluss|post[\s-]?market", re.I
)
_BEFORE_OPEN = re.compile(
    r"before(?:\s+the)?\s+(?:open|bell)|pre[\s-]?market|vor\s+b[öo]rsenbeginn", re.I
)

_MONTHS = {
    "january": 1,
    "jan": 1,
    "february": 2,
    "feb": 2,
    "march": 3,
    "mar": 3,
    "april": 4,
    "apr": 4,
    "may": 5,
    "june": 6,
    "jun": 6,
    "july": 7,
    "jul": 7,
    "august": 8,
    "aug": 8,
    "september": 9,
    "sept": 9,
    "sep": 9,
    "october": 10,
    "oct": 10,
    "november": 11,
    "nov": 11,
    "december": 12,
    "dec": 12,
}


@dataclass(frozen=True)
class EarningsEvent:
    """Dated results release for one issuer."""

    report_at: datetime
    session: str  # before_open | after_close | unknown | exact
    source: str
    confidence: str = "high"  # high | medium


def teaser_claims_reported_results(text: str) -> bool:
    return bool(_QUARTERLY_CLAIM.search(text or ""))


def teaser_claims_ath(text: str) -> bool:
    return bool(_ATH_CLAIM.search(text or ""))


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def results_known_by(event: EarningsEvent, publication_at: datetime) -> bool:
    """True only when the print was public at or before the teaser Stand."""
    pub = _aware(publication_at)
    reported = _aware(event.report_at)
    return reported <= pub


def assume_session_time(day: date, session: str, *, market: str = "US") -> datetime:
    """Map a calendar earnings day + session flag to a timezone-aware instant."""
    if market == "US":
        if session == "before_open":
            return datetime.combine(day, time(8, 0), tzinfo=US_EASTERN)
        if session == "after_close":
            return datetime.combine(day, time(16, 5), tzinfo=US_EASTERN)
        # Unknown same-day US print: fail closed at end of regular session.
        return datetime.combine(day, time(16, 5), tzinfo=US_EASTERN)
    # Default Europe morning print.
    if session == "before_open":
        return datetime.combine(day, time(7, 0), tzinfo=VIENNA)
    if session == "after_close":
        return datetime.combine(day, time(17, 45), tzinfo=VIENNA)
    return datetime.combine(day, time(7, 30), tzinfo=VIENNA)


def parse_earnings_snippets(snippets: list[str], *, around_year: int) -> EarningsEvent | None:
    """Best-effort parse of provider snippets; returns None when ambiguous."""
    blob = "\n".join(snippets)
    session = "unknown"
    if _AFTER_CLOSE.search(blob):
        session = "after_close"
    elif _BEFORE_OPEN.search(blob):
        session = "before_open"

    dates: list[date] = []
    for match in _DATE_US.finditer(blob):
        month = _MONTHS[match.group(1).casefold().rstrip(".")]
        day = int(match.group(2))
        year = int(match.group(3))
        if year == around_year or year == around_year - 1:
            try:
                dates.append(date(year, month, day))
            except ValueError:
                continue
    for match in _DATE_EU.finditer(blob):
        day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
        if year == around_year or year == around_year - 1:
            try:
                dates.append(date(year, month, day))
            except ValueError:
                continue
    for match in _DATE_ISO.finditer(blob):
        year = int(match.group(1))
        if year == around_year or year == around_year - 1:
            try:
                dates.append(date.fromisoformat(match.group(0)))
            except ValueError:
                continue
    if not dates:
        return None
    # Prefer dates in the earnings season window around the teaser year.
    dates = sorted(set(dates))
    # Take the latest date in Oct/Nov of around_year if present, else latest overall.
    seasonal = [d for d in dates if d.year == around_year and d.month in (7, 8, 9, 10, 11)]
    chosen = seasonal[-1] if seasonal else dates[-1]
    return EarningsEvent(
        report_at=assume_session_time(chosen, session, market="US"),
        session=session,
        source="snippet_parse",
        confidence="high" if session != "unknown" else "medium",
    )


def contradiction_for_unreported(event: EarningsEvent, publication_at: datetime) -> str:
    pub = _aware(publication_at).astimezone(VIENNA)
    reported = _aware(event.report_at).astimezone(VIENNA)
    return (
        f"Quartalszahlen erst {reported.isoformat()} ({event.session}); "
        f"Teaser-Stand {pub.isoformat()} — Ergebnis war noch nicht öffentlich."
    )


def contradiction_for_missing_ath(
    *, last: float, ath: float, ath_date: str, pct_below: float
) -> str:
    return (
        f"Kein Allzeithoch: letzter Schluss {last:g} liegt {pct_below:.1f}% "
        f"unter ATH {ath:g} vom {ath_date}."
    )


def ath_status(bars: list[dict], *, as_of: date) -> dict | None:
    """Return ATH vs last close through ``as_of`` (inclusive)."""
    prior = [b for b in bars if b["date"] <= as_of.isoformat()]
    if len(prior) < 2:
        return None
    last = prior[-1]
    peak = max(prior, key=lambda b: b["close"])
    pct = 0.0 if peak["close"] == 0 else (peak["close"] - last["close"]) / peak["close"] * 100
    return {
        "status": "ok",
        "last_date": last["date"],
        "last_close": last["close"],
        "ath_date": peak["date"],
        "ath_close": peak["close"],
        "pct_below_ath": round(pct, 2),
        "at_ath": abs(last["close"] - peak["close"]) < 1e-9,
        "near_ath_2pct": last["close"] >= peak["close"] * 0.98,
    }


class StaticEarningsLookup:
    """Test/operator table: ticker or casefolded name → EarningsEvent."""

    def __init__(self, events: dict[str, EarningsEvent]):
        self.events = {k.casefold(): v for k, v in events.items()}

    def __call__(self, *, name: str, ticker: str | None) -> EarningsEvent | None:
        for key in filter(None, [ticker, name]):
            hit = self.events.get(str(key).casefold())
            if hit:
                return hit
        return None


class TavilyEarningsLookup:
    """Live snippet lookup; never raises; returns None when unsure."""

    def __init__(self, *, api_key: str | None = None, poster=None, timeout: float = 45):
        self.api_key = api_key or os.environ.get("TAVILY_API_KEY") or os.environ.get(
            "DETECTIVE_SEARCH_API_KEY"
        )
        self.poster = poster or httpx.post
        self.timeout = timeout

    def __call__(self, *, name: str, ticker: str | None) -> EarningsEvent | None:
        if not self.api_key or not name:
            return None
        year = datetime.now(UTC).year
        query = (
            f"{name} {ticker or ''} Q3 {year} OR Q4 {year} earnings date "
            f"results before open after close"
        ).strip()
        try:
            response = self.poster(
                "https://api.tavily.com/search",
                headers={
                    "Authorization": "Bearer " + self.api_key,
                    "Content-Type": "application/json",
                },
                json={"query": query, "max_results": 5, "search_depth": "basic"},
                timeout=self.timeout,
            )
        except (httpx.HTTPError, RuntimeError):
            return None
        if getattr(response, "status_code", 500) != 200:
            return None
        try:
            payload = response.json()
        except ValueError:
            return None
        snippets = []
        for hit in payload.get("results") or []:
            if not isinstance(hit, dict):
                continue
            snippets.append(str(hit.get("title") or ""))
            snippets.append(str(hit.get("content") or ""))
        return parse_earnings_snippets(snippets, around_year=year)


def apply_earnings_pit(
    ranked: list[dict],
    publication_at: datetime | None,
    text: str,
    *,
    lookup=None,
    ath_bars_fetcher=None,
    top: int | None = None,
) -> dict:
    """Mutate ranked rows with hard contradictions when PIT facts fail.

    Returns a summary for the report ``falsification`` / diagnostics block.
    Checks every ranked row by default so demotions cannot elevate unchecked names.
    """
    from .structure_screen import ticker_for

    summary: dict = {
        "quarterly_claim": teaser_claims_reported_results(text),
        "ath_claim": teaser_claims_ath(text),
        "checked": [],
    }
    if publication_at is None or not ranked:
        summary["status"] = "skipped_no_publication_at_or_candidates"
        return summary
    pub = _aware(publication_at)
    # Morning Vienna Stand: last fully known US cash session is the previous calendar day.
    as_of = pub.astimezone(VIENNA).date()
    if pub.astimezone(VIENNA).time() < time(16, 0):
        as_of = as_of - timedelta(days=1)

    lookup = lookup or TavilyEarningsLookup()
    ath_bars_fetcher = ath_bars_fetcher or (
        lambda ticker: fetch_eod_bars(
            ticker,
            from_date=as_of - timedelta(days=3650),
            to_date=as_of,
        )
    )

    need_earnings = summary["quarterly_claim"]
    need_ath = summary["ath_claim"]
    if not need_earnings and not need_ath:
        summary["status"] = "skipped_no_claim"
        return summary

    scope = ranked if top is None else ranked[:top]
    for row in scope:
        identity = row.get("identity") or {}
        data = identity if isinstance(identity, dict) else identity.model_dump()
        name = data.get("name") or ""
        ticker = data.get("ticker") or ticker_for(name)
        entry: dict = {"asset_id": row.get("asset_id"), "name": name, "ticker": ticker}
        prior = list(row.get("hard_contradictions") or [])
        added: list[str] = []

        if need_earnings and (ticker or name):
            event = lookup(name=name, ticker=ticker)
            if event is None:
                entry["earnings"] = {"status": "unknown"}
            else:
                known = results_known_by(event, pub)
                entry["earnings"] = {
                    "status": "known" if known else "not_yet_public",
                    "report_at": event.report_at.isoformat(),
                    "session": event.session,
                    "source": event.source,
                    "confidence": event.confidence,
                }
                if not known and event.confidence in {"high", "medium"}:
                    msg = contradiction_for_unreported(event, pub)
                    if msg not in prior:
                        added.append(msg)

        if need_ath and ticker:
            bars = ath_bars_fetcher(ticker)
            if not bars:
                entry["ath"] = {"status": "unavailable"}
            else:
                status = ath_status(bars, as_of=as_of)
                if status is None:
                    entry["ath"] = {"status": "insufficient_history"}
                else:
                    entry["ath"] = status
                    if not status["near_ath_2pct"]:
                        msg = contradiction_for_missing_ath(
                            last=status["last_close"],
                            ath=status["ath_close"],
                            ath_date=status["ath_date"],
                            pct_below=status["pct_below_ath"],
                        )
                        if msg not in prior:
                            added.append(msg)

        if added:
            row["hard_contradictions"] = prior + added
            row["counterarguments"] = list(row["hard_contradictions"])
            row["evidence_score"] = int(row.get("evidence_score") or 0) - 100 * len(added)
        row["earnings_pit"] = entry
        summary["checked"].append(entry)

    ranked.sort(
        key=lambda row: (
            bool(row.get("hard_contradictions")),
            -row.get("evidence_score", 0),
            row.get("asset_id") or "",
        )
    )
    summary["status"] = "applied"
    return summary
