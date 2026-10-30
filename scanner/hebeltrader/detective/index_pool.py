"""Index-union market pool (pool-v1): wide identity set for hypothesis ranking.

The curated ``global_universe.json`` remains the structure/layer overlay for offline
structure screens. Market ranking defaults to this pool so unknown sectors (banks,
autos, …) are candidateable without patching one sector at a time.

Pool members come from public index constituent lists (see ``scripts/build_index_pool_v1.py``).
No Tiingo. No EODHD Fundamentals subscription required for membership.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from .structure_screen import load_universe as load_curated_universe

POOL_PATH = Path(__file__).resolve().parent / "index_pool_v1.json"
POOL_FORMAT = "hebeltrader-index-pool-v1"

# Wikipedia / publisher suffixes → EODHD exchange codes used by chart_check.
_SUFFIX_MAP = {
    "DE": "XETRA",
    "F": "XETRA",
    "XETRA": "XETRA",
    "PA": "PA",
    "AS": "AS",
    "MI": "MI",
    "MC": "MC",
    "BR": "BR",
    "HE": "HE",
    "VI": "VI",
    "ST": "ST",
    "CO": "CO",
    "OL": "OL",
    "LS": "LS",
    "IR": "IR",
    "L": "LSE",
    "LSE": "LSE",
    "SW": "SW",
    "S": "SW",
    "HK": "HK",
    "T": "TSE",
    "TSE": "TSE",
    "TO": "TO",
    "WAR": "WAR",
    "WA": "WAR",
    "PR": "PR",
    "US": "US",
}

_COUNTRY_SUFFIX = {
    "germany": "XETRA",
    "luxembourg": "XETRA",
    "switzerland": "SW",
    "france": "PA",
    "netherlands": "AS",
    "italy": "MI",
    "spain": "MC",
    "belgium": "BR",
    "finland": "HE",
    "austria": "VI",
    "united kingdom": "LSE",
    "great britain": "LSE",
    "uk": "LSE",
    "sweden": "ST",
    "denmark": "CO",
    "norway": "OL",
    "ireland": "IR",
    "portugal": "LS",
    "poland": "WAR",
    "czech republic": "PR",
    "united states": "US",
    "usa": "US",
}

# Map publisher sector strings onto structure_screen SECTORS labels when unambiguous.
_SECTOR_RULES = (
    (
        r"bank|financial|capital market|diversified financial|investment banking",
        "financial services",
    ),
    (r"insurance|reinsurance|versicher", "insurance"),
    (r"pharma|biotech|life science", "pharmaceutical"),
    (r"health\s*care|healthcare|medtech|medical|health care equipment", "healthcare"),
    (r"semiconductor|halbleiter|\bchip\b|semiconductor equipment", "semiconductor"),
    (r"software|it service|application software|systems software", "software"),
    (
        r"utilit|electric|multi-utilities|gas utilities|strom|versorger|power",
        "power infrastructure",
    ),
    (r"aerospace|defence|defense|r[uü]stung", "defense"),
    (r"retail|consumer discretionary|consumer staples|apparel|food.?retail|handels", "retail"),
    (r"oil.?field|oil.?gas equipment|oil services", "oilfield services"),
)


def normalize_sector(raw: str | None) -> str | None:
    text = (raw or "").strip()
    if not text:
        return None
    folded = text.casefold()
    for pattern, label in _SECTOR_RULES:
        if re.search(pattern, folded, re.I):
            return label
    return text.casefold()


def normalize_eodhd_ticker(
    symbol: str | None,
    *,
    country: str | None = None,
    default_exchange: str | None = None,
) -> str | None:
    """Return an EODHD-ready ticker (US bare, else CODE.EXCHANGE)."""
    if not symbol:
        return None
    raw = str(symbol).strip().upper().replace(" ", "")
    raw = raw.replace("-", ".")
    if not raw or raw in {".", ".."}:
        return None
    if "." in raw:
        base, suffix = raw.rsplit(".", 1)
        if not base:
            return None
        mapped = _SUFFIX_MAP.get(suffix, suffix)
        if mapped == "US":
            return base
        return f"{base}.{mapped}"
    exchange = None
    if country:
        exchange = _COUNTRY_SUFFIX.get(country.strip().casefold())
    exchange = exchange or default_exchange
    if not exchange or exchange == "US":
        return raw
    return f"{raw}.{exchange}"


def _company_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (name or "").casefold())


@lru_cache(maxsize=1)
def load_pool_document(path: str | None = None) -> dict:
    target = Path(path) if path else POOL_PATH
    payload = json.loads(target.read_text(encoding="utf-8"))
    if payload.get("format") not in {POOL_FORMAT, "hebeltrader-index-pool-v1"}:
        raise ValueError(f"unsupported index pool format: {payload.get('format')}")
    return payload


def load_pool_assets(path: str | None = None) -> list[dict]:
    return list(load_pool_document(path)["assets"])


def _overlay_curated(pool_assets: list[dict], curated: list[dict] | None = None) -> list[dict]:
    """Merge pool identity with curated structure tags; curated ticker wins on name match."""
    curated = list(curated if curated is not None else load_curated_universe())
    by_key = {_company_key(a["name"]): dict(a) for a in pool_assets}
    for asset in curated:
        key = _company_key(asset["name"])
        if key in by_key:
            merged = dict(by_key[key])
            for field in ("sector", "layer", "structure", "ticker", "aliases"):
                if asset.get(field) is not None:
                    merged[field] = asset[field]
            if asset.get("aliases"):
                aliases = list(dict.fromkeys([*(merged.get("aliases") or []), *asset["aliases"]]))
                merged["aliases"] = aliases
            merged["sources"] = sorted(
                set([*(merged.get("sources") or []), "curated_global_universe"])
            )
            by_key[key] = merged
        else:
            row = dict(asset)
            row["sources"] = ["curated_global_universe"]
            by_key[key] = row
    return sorted(by_key.values(), key=lambda a: a["name"].casefold())


@lru_cache(maxsize=1)
def load_market_universe() -> tuple:
    """Frozen tuple of assets for market ranking (pool + curated overlay)."""
    return tuple(_overlay_curated(load_pool_assets()))


def market_universe_list() -> list[dict]:
    return list(load_market_universe())


def pool_stats(path: str | None = None) -> dict:
    doc = load_pool_document(path)
    assets = doc["assets"]
    return {
        "format": doc.get("format"),
        "built_at": doc.get("built_at"),
        "asset_count": len(assets),
        "indexes": doc.get("indexes"),
        "source_counts": doc.get("source_counts"),
        "with_ticker": sum(1 for a in assets if a.get("ticker")),
        "normalized_sector_labels": sorted({label for _, label in _SECTOR_RULES}),
    }
