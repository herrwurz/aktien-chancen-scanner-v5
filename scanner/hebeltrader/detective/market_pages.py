"""Search a fixed set of market pages and keep names that co-occur.

Any two market terms in the teaser open the same hosts. The search text is the
terms that were found, not one fixed pair. Company names come from the pages,
and only when the same name is on at least two hosts inside the publication
window. SEC or IR text is then read against those same terms.
"""

from __future__ import annotations

import inspect
import re
from datetime import datetime, timedelta
from typing import NamedTuple
from urllib.parse import urlsplit

import httpx

from .research_plan import stock_text
from .source_kind import MARKET_NEWS_HOSTS, classify_live_source_kind


class _Term(NamedTuple):
    term_id: str
    teaser: re.Pattern
    search_de: str
    search_en: str
    page: re.Pattern


def _term(term_id: str, teaser: str, search_de: str, search_en: str, page: str) -> _Term:
    return _Term(term_id, re.compile(teaser, re.I), search_de, search_en, re.compile(page, re.I))


# Global catalog. Two different hits are enough; the pair is not fixed.
_TERMS = (
    _term(
        "order_book",
        r"auftragsb[uü]ch\w*|auftragsbestand|order\s+backlog|\bbacklog\b",
        "Auftragsbestand",
        "order backlog",
        r"backlog|auftragsbestand|order\s+book",
    ),
    _term(
        "order_intake",
        r"auftragseingang|großauftrag|bookings",
        "Auftragseingang",
        "orders bookings",
        r"orders?\s+received|bookings|auftragseingang",
    ),
    _term(
        "profit_growth",
        r"gewinne?\s+wach\w*|gewinn(?:e)?\s+steig\w*|gewinnsteiger\w*|gewinnsprung|"
        r"earnings\s+growth",
        "Gewinnwachstum",
        "earnings growth",
        r"(?:profit|net income|earnings per share|\beps\b).{0,48}"
        r"(?:increased|increase|up\b|grew|growth|higher|rose)|"
        r"(?:increased|higher|growth).{0,32}(?:profit|earnings|net income)",
    ),
    _term(
        "revenue_growth",
        r"umsatz\w*\s+(?:wach\w*|steig\w*|plus)|erlöse\s+steig\w*|revenue\s+growth",
        "Umsatzwachstum",
        "revenue growth",
        r"revenue.{0,40}(?:increased|growth|up\b|grew|higher)",
    ),
    _term(
        "guidance_raise",
        r"prognose\w*\s+angehoben|prognoseanhebung|jahresziel\w*\s+angehoben|"
        r"guidance\s+raise",
        "Prognose angehoben",
        "raised guidance",
        r"raised\s+(?:guidance|outlook)|prognose\s+angehoben",
    ),
    _term(
        "correction",
        r"korrektur|rücksetzer|konsolidierung",
        "Korrektur",
        "share pullback",
        r"pullback|correction|sell-?off|korrektur",
    ),
    _term(
        "trend_reversal",
        r"trendwende|trendwechsel",
        "Trendwende",
        "trend reversal",
        r"trend\s+reversal|turnaround|trendwende",
    ),
    _term(
        "uptrend",
        r"aufwärtstrend|aufwärtswelle",
        "Aufwärtstrend",
        "uptrend",
        r"uptrend|rally|aufwärtstrend",
    ),
    _term("wall_street", r"wall\s*street", "Wall Street", "Wall Street", r"wall\s*street"),
    _term(
        "sleeping_giant",
        r"schlafend\w*\s+riese\w*",
        "schlafender Riese",
        "sleeping giant",
        r"sleeping\s+giant|schlafend\w*\s+riese",
    ),
    _term(
        "billion_scale",
        r"milliardenschwer\w*",
        "Milliardenkonzern",
        "billion revenue",
        r"billion|milliarden",
    ),
    _term("dividend", r"dividende\w*", "Dividende", "dividend", r"dividend|dividende"),
    _term(
        "buyback",
        r"aktienrückkauf\w*|share\s+buyback",
        "Aktienrückkauf",
        "share buyback",
        r"buyback|repurchase|aktienrückkauf",
    ),
    _term(
        "acquisition",
        r"übernahme\w*|akquisition\w*|\bacquisition\b",
        "Übernahme",
        "acquisition",
        r"acquisition|acquire|übernahme",
    ),
    _term(
        "record_result",
        r"rekordgewinn|rekordumsatz|rekordauftrag\w*|rekordergebnis",
        "Rekordergebnis",
        "record results",
        r"record\s+(?:revenue|profit|earnings|backlog|orders)|rekord",
    ),
    _term(
        "margin",
        r"gewinnmarge|umsatzmarge|marge\b|profit\s+margin",
        "Marge",
        "profit margin",
        r"margin|marge",
    ),
    _term(
        "data_center",
        r"rechenzentr\w*|data\s*cent(?:er|re)",
        "Rechenzentrum",
        "data center",
        r"data\s*cent(?:er|re)|rechenzentr",
    ),
    _term(
        "defense",
        r"rüstung\w*|verteidigung\w*|defen[sc]e",
        "Rüstung",
        "defense",
        r"defense|missile|rüstung",
    ),
    _term(
        "partnership",
        r"partnerschaft\w*|kooperation\w*|partnership",
        "Partnerschaft",
        "partnership",
        r"partnership|partnerschaft",
    ),
    _term(
        "approval",
        r"zulassung\w*|regulatory\s+approval",
        "Zulassung",
        "regulatory approval",
        r"approval|cleared|zulassung",
    ),
    _term(
        "new_high",
        r"allzeithoch|rekordhoch|jahreshoch",
        "Allzeithoch",
        "record high",
        r"all[- ]time\s+high|record\s+high|allzeithoch",
    ),
)
_MIN_TERMS = 2
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
_FILING_CAP = 6


def teaser_market_terms(text: str) -> tuple[str, ...]:
    """Every catalog term the teaser states, in catalog order."""
    clean = stock_text(text or "")
    return tuple(term.term_id for term in _TERMS if term.teaser.search(clean))


def teaser_asks_market_pages(text: str) -> bool:
    """True when at least two different market terms are present."""
    return len(teaser_market_terms(text)) >= _MIN_TERMS


def news_queries(term_ids: tuple[str, ...]) -> tuple[str, str]:
    """One German and one English query built from the terms that were found."""
    by_id = {term.term_id: term for term in _TERMS}
    chosen = [by_id[term_id] for term_id in term_ids if term_id in by_id]
    german = " ".join(dict.fromkeys(term.search_de for term in chosen))
    english = " ".join(dict.fromkeys(term.search_en for term in chosen))
    return german[:350], english[:350]


def terms_on_page(text: str, term_ids: tuple[str, ...]) -> tuple[str, ...]:
    """Catalog terms whose page pattern appears in the lead of a primary document."""
    lead = (text or "")[:2500]
    by_id = {term.term_id: term for term in _TERMS}
    return tuple(
        term_id for term_id in term_ids if term_id in by_id and by_id[term_id].page.search(lead)
    )


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
    web, *, text: str, publication_at: datetime, universe: list[dict]
) -> tuple[dict, list]:
    """Open the fixed news hosts, then one SEC or IR page per co-occurring name."""
    terms = teaser_market_terms(text)
    start, end = publication_window(publication_at)
    index = _label_index(universe)
    errors: list[dict] = []
    news_hits: list[dict] = []
    for query in news_queries(terms):
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
            row["terms_on_page"] = list(
                terms_on_page(
                    "\n".join(str(primary.get(field) or "") for field in ("title", "text")),
                    terms,
                )
            )
        else:
            row["sec_url"] = None
            row["backlog"] = None
            row["profit"] = None
            row["terms_on_page"] = []
    for row in clustered[_PRIMARY_CAP:]:
        row["sec_url"] = None
        row["backlog"] = None
        row["profit"] = None
        row["terms_on_page"] = []
    names = [
        {
            "name": row["name"],
            "ticker": row.get("ticker"),
            "hosts": sorted(row["hosts"]),
            "urls": row["urls"],
            "sec_url": row.get("sec_url"),
            "backlog": row.get("backlog"),
            "profit": row.get("profit"),
            "terms_on_page": row.get("terms_on_page") or [],
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
        "terms": list(terms),
        "window": {"start": start, "end": end},
        "names": names,
        "primary_checks_capped": len(clustered) > _PRIMARY_CAP,
        "errors": errors,
    }
    # A name that only co-occurs on a roundup, with none of the teaser terms on
    # its filing, does not become a ranking document.
    anchored = [row for row in names if row.get("terms_on_page")]
    documents = _stamp(news_docs, anchored, index) + _stamp(primary_docs, anchored, index)
    return report, documents


def collect_issuer_filings(web, names: list[dict], *, publication_at: datetime):
    """Read one SEC filing, or else one IR page, for each shortlist name.

    At most six names. News hosts are not accepted as a filing.
    """
    start, end = publication_window(publication_at)
    documents = []
    errors: list[dict] = []
    checked = []
    seen: set[str] = set()
    for asset in names or []:
        name = str((asset or {}).get("name") or "").strip()
        key = name.casefold()
        if not name or key in seen:
            continue
        seen.add(key)
        if len(checked) >= _FILING_CAP:
            break
        ticker = str((asset or {}).get("ticker") or "").split(".")[0]
        label = f'"{name}"' + (f" {ticker}" if ticker else "")
        doc = None
        surface = "none"
        for surface_name, query, domains in (
            ("sec", f"{label} 8-K OR 10-Q OR 6-K earnings", ("sec.gov",)),
            ("ir", f"{label} investor relations quarterly results", None),
        ):
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
                if domains:
                    host = _host(hit["url"])
                    if host == "sec.gov" or host.endswith(".sec.gov"):
                        kept.append(hit)
                    continue
                if classify_live_source_kind(hit["url"]) in {"issuer", "regulatory"}:
                    kept.append(hit)
            if not kept:
                continue
            loaded, load_errors = _load(web, kept, limit=1)
            errors.extend(load_errors)
            if loaded:
                doc = loaded[0]
                surface = surface_name
                break
        checked.append({"name": name, "ticker": ticker or None, "surface": surface})
        if doc is None:
            continue
        stamped = dict(doc)
        stamped["company_name"] = name
        stamped["ticker"] = ticker or stamped.get("ticker")
        stamped["identity_basis"] = "issuer_filing"
        documents.append(stamped)
    report = {
        "status": "read" if documents else "empty",
        "cap": _FILING_CAP,
        "names": checked,
        "errors": errors,
    }
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
