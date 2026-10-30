#!/usr/bin/env python3
"""Build ``index_pool_v1.json`` from public index constituent sources.

Sources (no paid Fundamentals, no Tiingo):
  - S&P 500: Wikipedia List of S&P 500 companies
  - Nasdaq-100: Nasdaq.com list-type API
  - DAX / MDAX / EURO STOXX 50 / STOXX Europe 600: Wikipedia wikitables

Writes: scanner/hebeltrader/detective/index_pool_v1.json
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "scanner/hebeltrader/detective/index_pool_v1.json"
sys.path.insert(0, str(ROOT))

from scanner.hebeltrader.detective.index_pool import (  # noqa: E402
    POOL_FORMAT,
    normalize_eodhd_ticker,
    normalize_sector,
)

UA = "hebeltrader-index-pool-builder/1.0 (research; +https://github.com/herrwurz/aktien-chancen-scanner-v5)"


class WikiTableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables = []
        self._in_table = False
        self._in_tr = False
        self._in_cell = False
        self._cell = []
        self._row = []
        self._rows = []
        self._depth = 0
        self._skip = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "table" and "wikitable" in (attrs.get("class") or "").split():
            self._in_table = True
            self._rows = []
            self._depth = 1
        elif tag == "table" and self._in_table:
            self._depth += 1
        elif self._in_table and tag == "tr":
            self._in_tr = True
            self._row = []
        elif self._in_table and self._in_tr and tag in ("td", "th"):
            self._in_cell = True
            self._cell = []
            self._skip = False
        elif self._in_cell and tag == "br":
            self._cell.append(" ")
        elif self._in_cell and tag == "sup":
            self._skip = True

    def handle_endtag(self, tag):
        if self._in_cell and tag in ("td", "th"):
            self._row.append(" ".join("".join(self._cell).split()))
            self._in_cell = False
        elif self._in_tr and tag == "tr":
            if self._row:
                self._rows.append(self._row)
            self._in_tr = False
        elif tag == "table" and self._in_table:
            self._depth -= 1
            if self._depth <= 0:
                self.tables.append(self._rows)
                self._in_table = False
        elif self._in_cell and tag == "sup":
            self._skip = False

    def handle_data(self, data):
        if self._in_cell and not self._skip:
            self._cell.append(data)


def _fetch(url: str) -> bytes:
    headers = {
        "User-Agent": UA,
        "Accept": "application/json,text/html,*/*",
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        import httpx

        response = httpx.get(url, headers=headers, timeout=90.0, follow_redirects=True)
        response.raise_for_status()
        return response.content
    except Exception:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=90) as resp:  # noqa: S310 - fixed public URLs
            return resp.read()


def _fetch_text(url: str) -> str:
    return _fetch(url).decode("utf-8", errors="ignore")


def _fetch_json(url: str):
    return json.loads(_fetch(url))


def _tables(html: str):
    parser = WikiTableParser()
    parser.feed(html)
    return parser.tables


def _rows_as_dicts(table):
    if not table:
        return []
    header = [h.strip() for h in table[0]]
    out = []
    for row in table[1:]:
        padded = list(row) + [""] * (len(header) - len(row))
        out.append(dict(zip(header, padded[: len(header)], strict=False)))
    return out


def _clean_name(name: str) -> str:
    name = re.sub(r"\s+", " ", (name or "").strip())
    name = re.sub(r"\s*\(.*?\)\s*$", "", name).strip()
    return name


def _company_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (name or "").casefold())


def _add(bucket: dict, *, name, ticker, sector_raw, source, country=None, extra=None):
    name = _clean_name(name)
    if not name:
        return
    key = _company_key(name)
    ticker = normalize_eodhd_ticker(ticker, country=country)
    sector = normalize_sector(sector_raw)
    row = bucket.get(key)
    if row is None:
        row = {
            "name": name,
            "ticker": ticker,
            "sector": sector,
            "sector_raw": sector_raw,
            "sources": [],
            "countries": [],
        }
        if extra:
            row.update(extra)
        bucket[key] = row
    else:
        prefer_us = source.startswith(("spx", "ndx"))
        if ticker and (not row.get("ticker") or prefer_us):
            # Prefer US-listed ticker when the same name appears in US indexes.
            if prefer_us or not row.get("ticker"):
                row["ticker"] = ticker
        if sector and not row.get("sector"):
            row["sector"] = sector
        if sector_raw and not row.get("sector_raw"):
            row["sector_raw"] = sector_raw
    if source not in row["sources"]:
        row["sources"].append(source)
    if country and country not in row["countries"]:
        row["countries"].append(country)


def collect_spx(bucket):
    html = _fetch_text("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")
    table = _tables(html)[0]
    for row in _rows_as_dicts(table):
        _add(
            bucket,
            name=row.get("Security") or row.get("Company"),
            ticker=row.get("Symbol"),
            sector_raw=row.get("GICS Sector") or row.get("GICS Sub-Industry"),
            source="spx",
            country="United States",
            extra={"gics_sub": row.get("GICS Sub-Industry")},
        )


def collect_ndx(bucket):
    # Optional offline override when Nasdaq.com rate-limits the builder host.
    override = os.environ.get("INDEX_POOL_NDX_JSON")
    if override and Path(override).is_file():
        payload = json.loads(Path(override).read_text(encoding="utf-8"))
    else:
        payload = _fetch_json("https://api.nasdaq.com/api/quote/list-type/nasdaq100")
    rows = (((payload.get("data") or {}).get("data") or {}).get("rows")) or []
    for row in rows:
        name = row.get("companyName") or ""
        name = re.sub(
            r"\s+Common Stock$|\s+Ordinary Shares$|\s+Class [A-Z].*$",
            "",
            name,
            flags=re.I,
        ).strip()
        _add(
            bucket,
            name=name,
            ticker=row.get("symbol"),
            sector_raw=row.get("sector") or "Information Technology",
            source="ndx",
            country="United States",
        )


def collect_dax(bucket):
    html = _fetch_text("https://en.wikipedia.org/wiki/DAX")
    # Constituents table: header starts with Ticker / Company
    for table in _tables(html):
        if not table:
            continue
        header = [h.casefold() for h in table[0]]
        if "ticker" in header and "company" in header:
            for row in _rows_as_dicts(table):
                _add(
                    bucket,
                    name=row.get("Company"),
                    ticker=row.get("Ticker"),
                    sector_raw=row.get("Prime Standard Sector") or row.get("Sector"),
                    source="dax",
                    country="Germany",
                )
            return
    raise RuntimeError("DAX constituents table not found")


def collect_mdax(bucket):
    html = _fetch_text("https://en.wikipedia.org/wiki/MDAX")
    table = _tables(html)[0]
    for row in _rows_as_dicts(table):
        _add(
            bucket,
            name=row.get("Name") or row.get("Company"),
            ticker=row.get("Symbol"),
            sector_raw=row.get("Industry"),
            source="mdax",
            country="Germany",
        )


def collect_sx5e(bucket):
    html = _fetch_text("https://en.wikipedia.org/wiki/EURO_STOXX_50")
    for table in _tables(html):
        if not table:
            continue
        header = [h.casefold() for h in table[0]]
        if "ticker" in header and "name" in header:
            for row in _rows_as_dicts(table):
                country = None
                office = row.get("Registered office") or ""
                # office often "Germany" / "France" etc.
                if office:
                    country = office.split(",")[-1].strip()
                _add(
                    bucket,
                    name=row.get("Name"),
                    ticker=row.get("Ticker"),
                    sector_raw=row.get("Sector"),
                    source="sx5e",
                    country=country,
                )
            return
    raise RuntimeError("EURO STOXX 50 constituents table not found")


def collect_sxxp(bucket):
    html = _fetch_text("https://en.wikipedia.org/wiki/STOXX_Europe_600")
    for table in _tables(html):
        if not table:
            continue
        header = [h.casefold() for h in table[0]]
        if "ticker" in header and "company" in header and len(table) > 100:
            for row in _rows_as_dicts(table):
                _add(
                    bucket,
                    name=row.get("Company"),
                    ticker=row.get("Ticker"),
                    sector_raw=row.get("ICB Sector") or row.get("Sector"),
                    source="sxxp",
                    country=row.get("Country"),
                )
            return
    raise RuntimeError("STOXX Europe 600 constituents table not found")


# Wikipedia ATX table has no tickers; map to EODHD Vienna (.VI) codes.
# Preferred names align with SXXP/DAX-style labels so the union dedupes cleanly.
_ATX_TICKERS = {
    "erstebank": ("EBS.VI", "Erste Group"),
    "verbund": ("VER.VI", "Verbund"),
    "omv": ("OMV.VI", "OMV"),
    "bawag": ("BG.VI", "BAWAG Group"),
    "andritz": ("ANDR.VI", "Andritz"),
    "wienerberger": ("WIE.VI", "Wienerberger"),
    "voestalpine": ("VOE.VI", "Voestalpine"),
    "raiffeiseninternational": ("RBI.VI", "Raiffeisen Bank International"),
    "porr": ("POS.VI", "Porr"),
    "caimmo": ("CAI.VI", "CA Immo"),
    "evngroup": ("EVN.VI", "EVN"),
    "ats": ("ATS.VI", "AT&S"),
    "austrianpost": ("POST.VI", "Austrian Post"),
    "viennainsurancegroup": ("VIG.VI", "Vienna Insurance Group"),
    "lenzing": ("LNZ.VI", "Lenzing"),
    "uniqainsurancegroup": ("UQA.VI", "Uniqa Insurance Group"),
    "schoellerbleckmannoilfieldequipment": (
        "SBO.VI",
        "Schoeller-Bleckmann Oilfield Equipment",
    ),
    # Immofinanz: no Vienna common-stock row in EODHD VI list; Frankfurt works.
    "immofinanz": ("IMO1.F", "Immofinanz"),
    "strabag": ("STR.VI", "Strabag"),
    "doco": ("DOC.VI", "Do & Co"),
}


def collect_atx(bucket):
    html = _fetch_text("https://en.wikipedia.org/wiki/Austrian_Traded_Index")
    for table in _tables(html):
        if not table:
            continue
        header = [h.casefold() for h in table[0]]
        if "company" in header and ("industry" in header or "sector" in header):
            missing = []
            for row in _rows_as_dicts(table):
                company = row.get("Company") or ""
                key = _company_key(company)
                mapped = _ATX_TICKERS.get(key)
                if not mapped:
                    missing.append(company)
                    continue
                ticker, preferred = mapped
                sector_raw = row.get("Sector") or row.get("Industry")
                _add(
                    bucket,
                    name=preferred,
                    ticker=ticker,
                    sector_raw=sector_raw,
                    source="atx",
                    country="Austria",
                )
            if missing:
                raise RuntimeError(f"ATX ticker map incomplete: {missing}")
            return
    raise RuntimeError("ATX constituents table not found")


# Manual fixes when Wikipedia Symbol cells are empty / mis-parsed.
_TICKER_OVERRIDES = {
    "sussmicrotecse": "SMHN.XETRA",
    "süssmicrotecse": "SMHN.XETRA",
}


def build():
    bucket = {}
    collectors = [
        ("spx", collect_spx),
        ("ndx", collect_ndx),
        ("dax", collect_dax),
        ("mdax", collect_mdax),
        ("sx5e", collect_sx5e),
        ("sxxp", collect_sxxp),
        ("atx", collect_atx),
    ]
    source_counts = {}
    for name, fn in collectors:
        fn(bucket)
        source_counts[name] = sum(1 for a in bucket.values() if name in a["sources"])
        print(f"{name}: {source_counts[name]} members (union size {len(bucket)})", file=sys.stderr)

    assets = []
    for row in sorted(bucket.values(), key=lambda a: a["name"].casefold()):
        ticker = row.get("ticker") or _TICKER_OVERRIDES.get(_company_key(row["name"]))
        asset = {
            "name": row["name"],
            "ticker": ticker,
            "sector": row.get("sector"),
            "sector_raw": row.get("sector_raw"),
            "sources": sorted(row.get("sources") or []),
        }
        if row.get("countries"):
            asset["countries"] = sorted(row["countries"])
        if row.get("gics_sub"):
            asset["gics_sub"] = row["gics_sub"]
        # structure screen fields optional; filled later by curated overlay
        assets.append(asset)

    payload = {
        "format": POOL_FORMAT,
        "schema_version": 1,
        "built_at": datetime.now(UTC).isoformat(),
        "note": (
            "Index-union identity pool for market hypotheses. Membership from public "
            "constituent lists only. Curated structure tags are overlaid at load time. "
            "Not a solution list."
        ),
        "indexes": ["spx", "ndx", "dax", "mdax", "sx5e", "sxxp", "atx"],
        "source_counts": source_counts,
        "asset_count": len(assets),
        "assets": assets,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {len(assets)} assets → {OUT}", file=sys.stderr)
    return payload


if __name__ == "__main__":
    # repair collect_mdax signature if needed
    build()
