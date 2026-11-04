"""Search a fixed set of market pages and keep names that co-occur.

The teaser only decides whether those pages are opened. Company names come from
the pages, and only when the same name is on at least two of the news hosts
inside the publication window. SEC or IR text then checks backlog and profit.
"""

from __future__ import annotations

import inspect
import re
from datetime import datetime, timedelta
from urllib.parse import urlsplit

import httpx

from .source_kind import MARKET_NEWS_HOSTS, classify_live_source_kind

_ORDER_BOOK = re.compile(r"auftragsb[uü]ch\w*|auftragsbestand|order\s+backlog|\bbacklog\b", re.I)
_PROFIT_GROWTH = re.compile(
    r"gewinne?\s+wach\w*|gewinn(?:e)?\s+steig\w*|gewinnsteiger\w*|earnings\s+growth",
    re.I,
)
_NEWS_QUERIES = (
    "Auftragsbestand Gewinn Quartal",
    "order backlog earnings",
)
_LEGAL_SUFFIX = re.compile(
    r"\b(?:corporation|incorporated|corp|inc|plc|ag|se|sa|nv|ltd|company|holdings?)\b\.?",
    re.I,
)
_BACKLOG = re.compile(r"backlog|auftragsbestand|order\s+book", re.I)
_PROFIT_UP = re.compile(
    r"(?:profit|net income|earnings per share|\beps\b).{0,48}"
    r"(?:increased|increase|up\b|grew|growth|higher|rose)|"
    r"(?:increased|higher|growth).{0,32}(?:profit|earnings|net income)",
    re.I,
)
_PROFIT_DOWN = re.compile(
    r"(?:net income|profit|earnings).{0,40}(?:decreased|declined|lower|loss)|"
    r"net\s+loss|loss\s+per\s+share",
    re.I,
)
_WINDOW_DAYS = 21
_NEWS_FETCH_CAP = 6
_PRIMARY_CAP = 4


def teaser_asks_market_pages(text: str) -> bool:
    """True when the teaser states an order book and growing profits together."""
    blob = text or ""
    return bool(_ORDER_BOOK.search(blob) and _PROFIT_GROWTH.search(blob))


def publication_window(end: datetime) -> tuple[str, str]:
    stop = end.date()
    start = stop - timedelta(days=_WINDOW_DAYS)
    return start.isoformat(), stop.isoformat()


def _host(url: str) -> str:
    return (urlsplit(url or "").hostname or "").lower()


def news_host(url: str) -> str | None:
    host = _host(url)
    for domain in MARKET_NEWS_HOSTS:
        if host == domain or host.endswith("." + domain):
            return domain
    return None


def _call_search(web, query, *, limit, include_domains=None, start_date=None, end_date=None):
    params = inspect.signature(web.search).parameters
    accepts = any(item.kind is inspect.Parameter.VAR_KEYWORD for item in params.values())
    kwargs = {}
    if include_domains and (accepts or "include_domains" in params):
        kwargs["include_domains"] = list(include_domains)
    if start_date and (accepts or "start_date" in params):
        kwargs["start_date"] = start_date
        kwargs["end_date"] = end_date
    if accepts or "limit" in params:
        return web.search(query, limit=limit, **kwargs)
    return web.search(query, limit, **kwargs)


def _in_window(published_at, start: str, end: str) -> bool:
    raw = str(published_at or "")
    if len(raw) < 10 or raw[4] != "-" or raw[7] != "-":
        return True
    day = raw[:10]
    return start <= day <= end


def _label_index(universe: list[dict]) -> dict[str, tuple[dict, bool, str]]:
    owners: dict[str, list[tuple[dict, bool, str]]] = {}
    for asset in universe:
        name = str(asset.get("name") or "").strip()
        if not name:
            continue
        ticker = str(asset.get("ticker") or "").split(".")[0]
        labels: list[tuple[str, bool]] = []
        if len(name) >= 5:
            labels.append((name, False))
        short = " ".join(_LEGAL_SUFFIX.sub(" ", name).split())
        if short and short.casefold() != name.casefold() and len(short) >= 5:
            labels.append((short, False))
        elif (
            3 <= len(short) <= 5
            and short.isupper()
            and ticker
            and short.casefold() == ticker.casefold()
        ):
            labels.append((short, True))
        for label, strict in labels:
            owners.setdefault(label.casefold(), []).append((asset, strict, label))
    unique = {}
    for key, rows in owners.items():
        names = {row[0].get("name") for row in rows}
        if len(names) == 1:
            unique[key] = rows[0]
    return unique


def _mentioned(label: str, strict: bool, raw: str) -> bool:
    if strict:
        return re.search(rf"(?<![A-Za-z0-9]){re.escape(label)}(?![A-Za-z0-9])", raw) is not None
    return re.search(rf"(?<!\w){re.escape(label)}(?!\w)", raw, re.I) is not None


def names_in_text(raw: str, index: dict) -> list[dict]:
    found = {}
    for asset, strict, label in index.values():
        if _mentioned(label, strict, raw or ""):
            found[asset.get("name")] = asset
    return list(found.values())


def read_backlog_and_profit(text: str) -> tuple[bool, str]:
    """Read the lead of a primary page. Returns backlog flag and profit direction."""
    lead = (text or "")[:2500]
    backlog = bool(_BACKLOG.search(lead))
    up = bool(_PROFIT_UP.search(lead))
    down = bool(_PROFIT_DOWN.search(lead))
    if up and not down:
        return backlog, "up"
    if down and not up:
        return backlog, "down"
    return backlog, "unknown"


def _load(web, hits: list[dict], *, limit: int) -> tuple[list[dict], list[dict]]:
    chosen = []
    seen = set()
    for hit in hits:
        url = hit.get("url")
        if not url or url in seen:
            continue
        seen.add(url)
        chosen.append(hit)
        if len(chosen) >= limit:
            break
    urls = [hit["url"] for hit in chosen]
    fetch_many = getattr(web, "fetch_many", None)
    loaded: dict[str, dict] = {}
    errors = []
    if fetch_many:
        documents, batch_errors = fetch_many(urls)
        errors.extend(batch_errors)
        for doc in documents:
            loaded[doc.get("url") or ""] = doc
    else:
        for url in urls:
            try:
                loaded[url] = web.fetch(url)
            except (ValueError, httpx.HTTPError) as exc:
                errors.append({"url": url, "error": str(exc)[:120]})
    documents = []
    for hit in chosen:
        doc = dict(loaded.get(hit["url"]) or {})
        doc.setdefault("url", hit["url"])
        doc.setdefault("title", hit.get("title") or "")
        if not doc.get("text"):
            doc["text"] = hit.get("content") or ""
        doc.setdefault("published_at", hit.get("published_at"))
        doc.setdefault(
            "source_kind",
            classify_live_source_kind(hit["url"]) or "news",
        )
        documents.append(doc)
    return documents, errors


def _stamp(documents: list[dict], names: list[dict], index: dict) -> list[dict]:
    """One document per clustered name that the page actually mentions."""
    wanted = {item["name"] for item in names}
    by_name = {item["name"]: item for item in names}
    stamped = []
    for doc in documents:
        raw = "\n".join(str(doc.get(field) or "") for field in ("title", "text"))
        hits = [asset for asset in names_in_text(raw, index) if asset.get("name") in wanted]
        if not hits and doc.get("company_name") in wanted:
            hits = [by_name[doc["company_name"]]]
        for asset in hits:
            copy = dict(doc)
            copy["company_name"] = asset.get("name")
            copy["ticker"] = asset.get("ticker")
            copy["identity_basis"] = "market_page_cooccurrence"
            stamped.append(copy)
    return stamped


def collect_market_pages(
    web, *, publication_at: datetime, universe: list[dict]
) -> tuple[dict, list]:
    """Open the fixed news hosts, then one SEC or IR page per co-occurring name."""
    start, end = publication_window(publication_at)
    index = _label_index(universe)
    errors: list[dict] = []
    news_hits: list[dict] = []
    for query in _NEWS_QUERIES:
        try:
            found = _call_search(
                web,
                query,
                limit=6,
                include_domains=MARKET_NEWS_HOSTS,
                start_date=start,
                end_date=end,
            )
        except (ValueError, httpx.HTTPError) as exc:
            errors.append({"query": query, "error": str(exc)[:120]})
            continue
        for hit in found or []:
            if not isinstance(hit, dict) or not news_host(str(hit.get("url") or "")):
                continue
            if not _in_window(hit.get("published_at"), start, end):
                continue
            news_hits.append(hit)
    news_docs, load_errors = _load(web, news_hits, limit=_NEWS_FETCH_CAP)
    errors.extend(load_errors)
    by_name: dict[str, dict] = {}
    for doc in news_docs:
        if not _in_window(doc.get("published_at"), start, end):
            continue
        host = news_host(str(doc.get("url") or ""))
        if not host:
            continue
        raw = "\n".join(str(doc.get(field) or "") for field in ("title", "text"))
        for asset in names_in_text(raw, index):
            row = by_name.setdefault(
                asset.get("name") or "",
                {
                    "name": asset.get("name"),
                    "ticker": asset.get("ticker"),
                    "hosts": set(),
                    "urls": [],
                },
            )
            row["hosts"].add(host)
            if doc.get("url") not in row["urls"]:
                row["urls"].append(doc["url"])
    clustered = [row for row in by_name.values() if row["name"] and len(row["hosts"]) >= 2]
    clustered.sort(key=lambda row: (-len(row["hosts"]), row["name"]))
    checked = clustered[:_PRIMARY_CAP]
    primary_docs = []
    for row in checked:
        primary, primary_errors = _primary_page(web, row["name"], start=start, end=end)
        errors.extend(primary_errors)
        if primary:
            primary["company_name"] = row["name"]
            primary["ticker"] = row.get("ticker")
            primary_docs.append(primary)
            backlog, profit = read_backlog_and_profit(
                "\n".join(str(primary.get(field) or "") for field in ("title", "text"))
            )
            row["sec_url"] = primary.get("url")
            row["backlog"] = backlog
            row["profit"] = profit
        else:
            row["sec_url"] = None
            row["backlog"] = None
            row["profit"] = None
    for row in clustered[_PRIMARY_CAP:]:
        row["sec_url"] = None
        row["backlog"] = None
        row["profit"] = None
    names = [
        {
            "name": row["name"],
            "ticker": row.get("ticker"),
            "hosts": sorted(row["hosts"]),
            "urls": row["urls"],
            "sec_url": row.get("sec_url"),
            "backlog": row.get("backlog"),
            "profit": row.get("profit"),
        }
        for row in clustered
    ]
    if len(names) >= 2:
        status = "cluster"
    elif len(names) == 1:
        status = "single"
    else:
        status = "no_overlap"
    report = {
        "status": status,
        "hosts": list(MARKET_NEWS_HOSTS),
        "window": {"start": start, "end": end},
        "names": names,
        "primary_checks_capped": len(clustered) > _PRIMARY_CAP,
        "errors": errors,
    }
    documents = _stamp(news_docs, names, index) + _stamp(primary_docs, names, index)
    return report, documents


def _primary_page(web, name: str, *, start: str, end: str) -> tuple[dict | None, list[dict]]:
    errors = []
    queries = (
        (f'"{name}" earnings backlog', ("sec.gov",)),
        (f'"{name}" investor relations quarterly results', None),
    )
    for query, domains in queries:
        try:
            hits = _call_search(
                web,
                query,
                limit=4,
                include_domains=domains,
                start_date=start,
                end_date=end,
            )
        except (ValueError, httpx.HTTPError) as exc:
            errors.append({"query": query, "error": str(exc)[:120]})
            continue
        kept = []
        for hit in hits or []:
            if not isinstance(hit, dict) or not hit.get("url"):
                continue
            if not _in_window(hit.get("published_at"), start, end):
                continue
            kind = classify_live_source_kind(hit["url"])
            if domains:
                host = _host(hit["url"])
                if host == "sec.gov" or host.endswith(".sec.gov"):
                    kept.append(hit)
            elif kind in {"issuer", "regulatory"}:
                kept.append(hit)
        if not kept:
            if domains:
                continue
            return None, errors
        docs, load_errors = _load(web, kept, limit=1)
        errors.extend(load_errors)
        if docs:
            return docs[0], errors
        if domains:
            continue
        return None, errors
    return None, errors
