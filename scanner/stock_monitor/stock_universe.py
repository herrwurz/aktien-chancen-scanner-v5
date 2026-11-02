"""Opt-in automatic SEC universe mapping for a bounded stock research pass."""

from __future__ import annotations

import httpx

from scanner.stock_monitor.worker import SecTarget

WATCH_SYMBOLS = (
    "AAPL",
    "MSFT",
    "NVDA",
    "AMZN",
    "GOOGL",
    "META",
    "TSLA",
    "AVGO",
    "AMD",
    "PLTR",
    "CRM",
    "ORCL",
    "NFLX",
    "COST",
    "JPM",
    "V",
    "MA",
    "UNH",
    "LLY",
    "ABBV",
    "XOM",
    "CAT",
    "GE",
    "UBER",
    "COIN",
    "HOOD",
    "MU",
    "INTC",
    "ADBE",
    "PANW",
)


def select_targets(company_tickers: dict, *, slot: int, limit: int = 10) -> list[SecTarget]:
    """Map a rotating, disclosed US large-cap watchlist to SEC-issued CIKs."""
    if not isinstance(company_tickers, dict):
        raise ValueError("Invalid SEC company ticker response")
    mapping = {}
    for row in company_tickers.values():
        if not isinstance(row, dict):
            continue
        ticker = row.get("ticker")
        cik = row.get("cik_str")
        if isinstance(ticker, str) and isinstance(cik, int) and cik > 0:
            mapping[ticker] = cik
    available = [SecTarget(cik=mapping[s], symbol=s) for s in WATCH_SYMBOLS if s in mapping]
    if not available:
        raise ValueError("No configured watch symbols resolved from SEC")
    start = (slot * limit) % len(available)
    count = min(limit, len(available))
    return [available[(start + index) % len(available)] for index in range(count)]


def discover_sec_targets(*, user_agent: str, slot: int) -> list[SecTarget]:
    if not user_agent or "@" not in user_agent:
        raise ValueError("SEC_USER_AGENT must include a valid contact email")
    response = httpx.get(
        "https://www.sec.gov/files/company_tickers.json",
        headers={"User-Agent": user_agent, "Accept": "application/json"},
        timeout=20,
        follow_redirects=True,
    )
    response.raise_for_status()
    return select_targets(response.json(), slot=slot)
