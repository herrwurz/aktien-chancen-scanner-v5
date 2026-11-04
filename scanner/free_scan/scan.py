"""Non-binding watchlist from free public pages.

Paid tokens (EODHD, Tiingo, Tavily, OpenAI, Twelve Data) are never read.
A source is fetched only when its public rules allow that exact request.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from html.parser import HTMLParser
from typing import Any
from zoneinfo import ZoneInfo

import httpx

DISCLAIMER = (
    "Unverbindliche Beobachtung, kein Kaufauftrag und keine geprüfte Trefferbilanz. "
    "Kurse sind verzögert. Dieselbe Aktie in zwei Quellen ist eine Übereinstimmung "
    "des heutigen Filters, kein Nachweis künftiger Kursbewegung."
)

USER_AGENT = "aktien-chancen-scanner/0.1 (non-binding free-source scan)"
MAX_HITS = 8

BROWSER_ONLY: tuple[dict[str, str], ...] = (
    {
        "id": "finviz",
        "title": "Finviz",
        "page_url": "https://finviz.com/screener.ashx",
        "reason": (
            "Die öffentliche robots.txt untersagt /screener. "
            "Die Seite bleibt im Browser nutzbar und wird hier nicht abgerufen."
        ),
    },
    {
        "id": "yahoo_api",
        "title": "Yahoo Kurs-API",
        "page_url": "https://finance.yahoo.com/research-hub/screener/equity/",
        "reason": (
            "query1.finance.yahoo.com untersagt jeden Abruf. "
            "Verwendet wird nur die öffentliche HTML-Liste der Tagesgewinner."
        ),
    },
    {
        "id": "onvista",
        "title": "onvista",
        "page_url": "https://www.onvista.de/",
        "reason": (
            "Die robots.txt verweist auf die AGB und untersagt Spidering ohne Erlaubnis. "
            "Kein automatischer Abruf."
        ),
    },
    {
        "id": "investing",
        "title": "Investing.com",
        "page_url": "https://www.investing.com/stock-screener",
        "reason": "Der Abruf von robots.txt antwortet mit 403. Kein automatischer Abruf.",
    },
    {
        "id": "finanzen",
        "title": "finanzen.net",
        "page_url": "https://www.finanzen.net/",
        "reason": (
            "Die öffentliche Indexseite enthält keine Signal-Tabelle. "
            "Der Ajax-Pfad ist in robots.txt gesperrt."
        ),
    },
    {
        "id": "stock3",
        "title": "stock3",
        "page_url": "https://stock3.com/",
        "reason": (
            "Der Screener hängt an einem kostenlosen Konto. "
            "Ohne Anmeldung gibt es keine maschinenlesbare Signalliste."
        ),
    },
)

_QUOTE = re.compile(r"/quote/([A-Z0-9.\-=^]+)")
_TV_URL = "https://scanner.tradingview.com/global/scan"
_YAHOO_URL = "https://finance.yahoo.com/research-hub/screener/day_gainers"
_WSO_URL = "https://www.wallstreet-online.de/aktien/signale/finder"
_BINANCE_URL = "https://api.binance.com/api/v3/ticker/24hr"


def run_free_scan(client: httpx.Client) -> dict[str, Any]:
    """Ask each allowed source once. One failure leaves the other sources intact."""
    sources = [
        _tradingview(client, _stock_query(), "tradingview_stocks", "TradingView Aktien"),
        _tradingview(client, _crypto_query(), "tradingview_crypto", "TradingView Krypto"),
        _yahoo(client),
        _wallstreet(client),
        _binance(client),
    ]
    sources.extend(_browser_only())
    return {
        "disclaimer": DISCLAIMER,
        "generated_at": datetime.now(ZoneInfo("Europe/Berlin")).isoformat(timespec="minutes"),
        "subscriptions_used": [],
        "sources": sources,
        "overlap": _overlap(sources),
    }


def _browser_only() -> list[dict[str, Any]]:
    return [
        {
            "id": item["id"],
            "title": item["title"],
            "status": "browser_only",
            "reason": item["reason"],
            "page_url": item["page_url"],
            "hits": [],
        }
        for item in BROWSER_ONLY
    ]


def _stock_query() -> dict[str, Any]:
    return {
        "columns": ["name", "close", "change", "volume", "RSI", "sector"],
        "filter": [
            {"left": "type", "operation": "in_range", "right": ["stock", "dr"]},
            {"left": "close", "operation": "greater", "right": 5},
            {"left": "volume", "operation": "greater", "right": 500_000},
            {"left": "SMA200", "operation": "less", "right": "close"},
            {"left": "change", "operation": "greater", "right": 1},
            {"left": "change", "operation": "less", "right": 12},
        ],
        "ignore_unknown_fields": False,
        "options": {"lang": "de"},
        "range": [0, 15],
        "sort": {"sortBy": "volume", "sortOrder": "desc"},
        "symbols": {},
        "markets": ["america", "germany"],
    }


def _crypto_query() -> dict[str, Any]:
    return {
        "columns": ["name", "close", "change", "volume", "exchange"],
        "filter": [
            {
                "left": "exchange",
                "operation": "in_range",
                "right": ["BINANCE", "COINBASE", "KRAKEN"],
            },
            {"left": "volume", "operation": "greater", "right": 10_000_000},
            {"left": "close", "operation": "greater", "right": 0.05},
            {"left": "change", "operation": "greater", "right": 2},
            {"left": "change", "operation": "less", "right": 25},
        ],
        "ignore_unknown_fields": False,
        "options": {"lang": "de"},
        "range": [0, 40],
        "sort": {"sortBy": "volume", "sortOrder": "desc"},
        "symbols": {},
        "markets": ["crypto"],
    }


def _tradingview(
    client: httpx.Client, query: dict[str, Any], source_id: str, title: str
) -> dict[str, Any]:
    rule = (
        "Öffentlicher Pfad /global/scan, den robots.txt ausdrücklich erlaubt. "
        "Aktien: über der 200-Tage-Linie, Tagesplus 1–12 %, Mindestvolumen. "
        "Krypto: Binance, Coinbase oder Kraken, Tagesplus 2–25 %. Spot vor Perpetual."
        if source_id == "tradingview_stocks"
        else "Dieselbe erlaubte Adresse, Markt Krypto. Perpetual (.P) nur als Lückenfüller."
    )
    try:
        response = client.post(_TV_URL, json=query, headers=_headers("application/json"))
    except httpx.HTTPError as exc:
        return _failed(source_id, title, _TV_URL, "error", type(exc).__name__, rule)
    if response.status_code != 200:
        return _failed(source_id, title, _TV_URL, "blocked", f"HTTP {response.status_code}", rule)
    try:
        payload = response.json()
    except json.JSONDecodeError:
        return _failed(source_id, title, _TV_URL, "error", "Antwort ist kein JSON", rule)
    hits = _tradingview_hits(payload, source_id)
    return _done(source_id, title, _TV_URL, hits, rule)


def _tradingview_hits(payload: dict[str, Any], source_id: str) -> list[dict[str, str]]:
    rows = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return []
    spot: list[dict[str, str]] = []
    perpetual: list[dict[str, str]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        raw = str(row.get("s") or "")
        values = row.get("d")
        if ":" not in raw or not isinstance(values, list) or len(values) < 4:
            continue
        ticker = raw.split(":", 1)[1]
        plain = ticker.removesuffix(".P")
        if source_id == "tradingview_crypto" and not plain.endswith(("USDT", "USD")):
            continue
        name = str(values[0])
        move = _percent(values[2])
        price = _price(values[1])
        detail = f"Volumen {_compact(values[3])}"
        if source_id == "tradingview_stocks" and len(values) > 5 and values[5]:
            detail = f"{values[5]} · {detail}"
        hit = {
            "label": _ticker(ticker.removesuffix(".P")),
            "name": name,
            "side": "Beobachtung aufwärts",
            "detail": detail,
            "price": price,
            "move": move,
        }
        if ticker.endswith(".P"):
            hit["detail"] = "Perpetual · " + hit["detail"]
            perpetual.append(hit)
        else:
            spot.append(hit)
    chosen = spot if source_id == "tradingview_stocks" else spot + perpetual
    if source_id == "tradingview_crypto" and len(spot) >= 4:
        chosen = spot
    return _unique(chosen)[:MAX_HITS]


def _yahoo(client: httpx.Client) -> dict[str, Any]:
    title = "Yahoo Finance Tagesgewinner"
    rule = (
        "Öffentliche HTML-Liste der Tagesgewinner. "
        "Die Kursschnittstelle auf query1.finance.yahoo.com wird nicht verwendet."
    )
    try:
        response = client.get(_YAHOO_URL, headers=_headers("text/html"))
    except httpx.HTTPError as exc:
        return _failed("yahoo", title, _YAHOO_URL, "error", type(exc).__name__, rule)
    if response.status_code != 200:
        return _failed("yahoo", title, _YAHOO_URL, "blocked", f"HTTP {response.status_code}", rule)
    hits = _yahoo_hits(response.text)
    return _done("yahoo", title, _YAHOO_URL, hits, rule)


class _YahooTable(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[dict[str, Any]] = []
        self._row: dict[str, Any] | None = None
        self._cell: list[str] | None = None
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self._skip += 1
        if self._skip:
            return
        if tag == "tr":
            self._row = {"cells": [], "ticker": ""}
        if tag in {"td", "th"} and self._row is not None:
            self._cell = []
        if tag == "a" and self._row is not None:
            href = dict(attrs).get("href") or ""
            match = _QUOTE.search(href)
            if match and not self._row["ticker"]:
                self._row["ticker"] = match.group(1)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"}:
            self._skip = max(0, self._skip - 1)
        if self._skip:
            return
        if tag in {"td", "th"} and self._cell is not None and self._row is not None:
            self._row["cells"].append(" ".join("".join(self._cell).split()))
            self._cell = None
        if tag == "tr" and self._row is not None:
            if self._row["ticker"]:
                self.rows.append(self._row)
            self._row = None

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)


def _yahoo_hits(html: str) -> list[dict[str, str]]:
    parser = _YahooTable()
    parser.feed(html)
    hits: list[dict[str, str]] = []
    for row in parser.rows:
        cells = row["cells"]
        name = _yahoo_name(cells, row["ticker"])
        move = next((cell for cell in cells if "%" in cell), "")
        price = next((cell for cell in cells if _looks_like_price(cell)), "")
        hits.append(
            {
                "label": row["ticker"],
                "name": name,
                "side": "Tagesgewinner",
                "detail": "Größtes Tagesplus in der öffentlichen Yahoo-Liste",
                "price": price,
                "move": move,
            }
        )
    return _unique(hits)[:MAX_HITS]


def _wallstreet(client: httpx.Client) -> dict[str, Any]:
    title = "wallstreetONLINE Chartsignale"
    rule = (
        "Öffentliche Finder-Seite, in robots.txt nicht gesperrt. "
        "Die Tabelle ist alphabetisch, die ersten Zeilen sind keine Rangliste."
    )
    try:
        response = client.get(_WSO_URL, headers=_headers("text/html"))
    except httpx.HTTPError as exc:
        return _failed("wallstreet", title, _WSO_URL, "error", type(exc).__name__, rule)
    if response.status_code != 200:
        return _failed(
            "wallstreet", title, _WSO_URL, "blocked", f"HTTP {response.status_code}", rule
        )
    hits = _wallstreet_hits(response.text)
    return _done("wallstreet", title, _WSO_URL, hits, rule)


class _Rows(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self._skip += 1
        if self._skip:
            return
        if tag == "tr":
            self._row = []
        if tag in {"td", "th"} and self._row is not None:
            self._cell = []

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"}:
            self._skip = max(0, self._skip - 1)
        if self._skip:
            return
        if tag in {"td", "th"} and self._cell is not None and self._row is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        if tag == "tr" and self._row is not None:
            if any(self._row):
                self.rows.append(self._row)
            self._row = None

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)


def _wallstreet_hits(html: str) -> list[dict[str, str]]:
    parser = _Rows()
    parser.feed(html)
    hits: list[dict[str, str]] = []
    for cells in parser.rows:
        if len(cells) < 5 or cells[0] == "Signal":
            continue
        # Page order: Signal, Wertpapier, Uhrzeit, Kurs, Strategie, Performance.
        # Some rows put the strategy in column 4. Accept either place.
        strategy = ""
        for cell in cells:
            if cell.strip().lower() in {"long", "short"}:
                strategy = cell.strip().lower()
                break
        if strategy not in {"long", "short"}:
            continue
        name = cells[1].removesuffix(" Chartsignale").strip() if len(cells) > 1 else cells[0]
        price = next(
            (
                cell
                for cell in cells
                if cell[:1].isdigit() and any(mark in cell for mark in ("$", "€", "kr", "zł"))
            ),
            "",
        )
        performance = next((cell for cell in cells if "%" in cell), "")
        hits.append(
            {
                "label": name or cells[0],
                "name": name,
                "side": "long" if strategy == "long" else "short",
                "detail": cells[0],
                "price": price,
                "move": performance,
            }
        )
        if len(hits) >= MAX_HITS:
            break
    return hits


def _binance(client: httpx.Client) -> dict[str, Any]:
    title = "Binance Spot 24h"
    rule = (
        "Öffentliche Markt-API ohne Schlüssel, bereits der Krypto-Scanner des Projekts. "
        "USDT-Paare mit mindestens 20 Mio. Quote-Volumen und 2–25 % Tagesplus."
    )
    try:
        response = client.get(_BINANCE_URL, headers=_headers("application/json"))
    except httpx.HTTPError as exc:
        return _failed("binance", title, _BINANCE_URL, "error", type(exc).__name__, rule)
    if response.status_code == 451:
        return _failed(
            "binance",
            title,
            _BINANCE_URL,
            "blocked",
            "HTTP 451: dieser Standort ist von Binance gesperrt",
            rule,
        )
    if response.status_code != 200:
        return _failed(
            "binance", title, _BINANCE_URL, "blocked", f"HTTP {response.status_code}", rule
        )
    try:
        payload = response.json()
    except json.JSONDecodeError:
        return _failed("binance", title, _BINANCE_URL, "error", "Antwort ist kein JSON", rule)
    if isinstance(payload, dict):
        message = str(payload.get("msg") or "keine Liste")[:180]
        return _failed("binance", title, _BINANCE_URL, "blocked", message, rule)
    hits = _binance_hits(payload)
    return _done("binance", title, _BINANCE_URL, hits, rule)


def _binance_hits(rows: Any) -> list[dict[str, str]]:
    if not isinstance(rows, list):
        return []
    ranked: list[tuple[float, dict[str, str]]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        symbol = str(row.get("symbol") or "")
        if not symbol.endswith("USDT") or _leveraged_token(symbol):
            continue
        try:
            change = float(row["priceChangePercent"])
            quote = float(row["quoteVolume"])
            price = float(row["lastPrice"])
        except (KeyError, TypeError, ValueError):
            continue
        if quote < 20_000_000 or not 2 <= change <= 25:
            continue
        ranked.append(
            (
                quote,
                {
                    "label": symbol.removesuffix("USDT"),
                    "name": symbol,
                    "side": "24h-Anstieg",
                    "detail": f"Quote-Volumen {_compact(quote)} USDT",
                    "price": _price(price),
                    "move": _percent(change),
                },
            )
        )
    ranked.sort(key=lambda item: item[0], reverse=True)
    return _unique([hit for _, hit in ranked])[:MAX_HITS]


def _overlap(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: dict[str, list[str]] = {}
    for source in sources:
        if source["status"] != "delivered" or source["id"] == "wallstreet":
            continue
        for hit in source["hits"]:
            key = _overlap_key(hit["label"])
            if len(key) < 2:
                continue
            titles = seen.setdefault(key, [])
            if source["title"] not in titles:
                titles.append(source["title"])
    shared = [
        {"label": label, "sources": titles} for label, titles in seen.items() if len(titles) >= 2
    ]
    shared.sort(key=lambda item: (-len(item["sources"]), item["label"]))
    return shared


def _done(
    source_id: str, title: str, url: str, hits: list[dict[str, str]], rule: str
) -> dict[str, Any]:
    return {
        "id": source_id,
        "title": title,
        "status": "delivered" if hits else "empty",
        "reason": rule if hits else rule + " Die Antwort enthielt keine Zeile im Filter.",
        "page_url": url,
        "hits": hits,
    }


def _failed(
    source_id: str, title: str, url: str, status: str, detail: str, rule: str
) -> dict[str, Any]:
    return {
        "id": source_id,
        "title": title,
        "status": status,
        "reason": f"{rule} Abruf: {detail}.",
        "page_url": url,
        "hits": [],
    }


def _headers(accept: str) -> dict[str, str]:
    return {"User-Agent": USER_AGENT, "Accept": accept}


def _leveraged_token(symbol: str) -> bool:
    if symbol.endswith(("DOWNUSDT", "BULLUSDT", "BEARUSDT")):
        return True
    return symbol.endswith("UPUSDT") and symbol != "JUPUSDT"


def _ticker(value: str) -> str:
    return re.sub(r"[^A-Z0-9.]", "", value.upper())


def _overlap_key(value: str) -> str:
    text = value.upper()
    for suffix in ("USDT", "USD"):
        if text.endswith(suffix) and len(text) > len(suffix) + 1:
            text = text[: -len(suffix)]
            break
    if "." in text:
        base, suffix = text.split(".", 1)
        if suffix in {"DE", "F", "PA", "L", "SW", "AS", "MI", "HK", "TO"}:
            text = base
    return re.sub(r"[^A-Z0-9]", "", text)


def _unique(hits: list[dict[str, str]]) -> list[dict[str, str]]:
    kept: list[dict[str, str]] = []
    labels: set[str] = set()
    for hit in hits:
        if hit["label"] in labels:
            continue
        labels.add(hit["label"])
        kept.append(hit)
    return kept


def _percent(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    return f"{number:+.2f} %"


def _price(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    if number >= 100:
        return f"{number:.2f}"
    return f"{number:.4f}".rstrip("0").rstrip(".")


def _compact(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    if number >= 1_000_000_000:
        return f"{number / 1_000_000_000:.1f} Mrd."
    if number >= 1_000_000:
        return f"{number / 1_000_000:.1f} Mio."
    return f"{number:.0f}"


def _yahoo_name(cells: list[str], ticker: str) -> str:
    names = [cell for cell in cells if _company_name(cell, ticker)]
    return max(names, key=len) if names else ""


def _company_name(cell: str, ticker: str) -> bool:
    if not cell or "%" in cell or cell == ticker or _looks_like_price(cell):
        return False
    letters = re.sub(r"[^A-Za-z]", "", cell).upper()
    compact = re.sub(r"[^A-Z0-9]", "", ticker.upper())
    if not letters or letters in {compact, compact[:1] + compact}:
        return False
    return len(cell) > len(ticker) + 2


def _looks_like_price(cell: str) -> bool:
    text = cell.replace(",", "").replace(" ", "")
    return bool(re.fullmatch(r"\d+\.\d+", text)) and len(text) <= 14
