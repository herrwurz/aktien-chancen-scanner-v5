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
REMAP_PATH = Path(__file__).resolve().parent / "index_pool_ticker_remap_v1.json"
POOL_FORMAT = "hebeltrader-index-pool-v1"
_NORDIC_EXCHANGES = frozenset({"ST", "CO", "HE", "OL"})

# Wikipedia / publisher suffixes → EODHD exchange codes used by chart_check.
_SUFFIX_MAP = {
    "DE": "XETRA",
    # Frankfurt stay .F (some AT names like Immofinanz have no Vienna EODHD listing).
    "F": "F",
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


def _nordic_share_class(base: str) -> str:
    """ASSAB / ERICB → ASSA-B / ERIC-B (EODHD Nordic class form)."""
    if "-" in base:
        return base
    match = re.fullmatch(r"([A-Z]{2,})([ABC])", base)
    if match:
        return f"{match.group(1)}-{match.group(2)}"
    return base


def normalize_eodhd_ticker(
    symbol: str | None,
    *,
    country: str | None = None,
    default_exchange: str | None = None,
) -> str | None:
    """Return an EODHD-ready ticker (US bare, else CODE.EXCHANGE).

    Preserves Nordic ``ASSA-B.ST`` hyphens. Maps US share classes ``BF.B`` → ``BF-B``.
    Collapses publisher forms like ``NDA.FI`` + Finland into ``NDA-FI.HE``.
    """
    if not symbol:
        return None
    raw = str(symbol).strip().upper().replace(" ", "")
    if not raw or raw in {".", ".."}:
        return None

    country_exchange = None
    if country:
        country_exchange = _COUNTRY_SUFFIX.get(country.strip().casefold())
    country_exchange = country_exchange or default_exchange

    # Share class without venue: BF.B → BF-B; BT.A + UK → BT-A.LSE.
    if re.fullmatch(r"[A-Z]{1,5}\.[A-Z]", raw):
        base = raw.replace(".", "-")
        if not country_exchange or country_exchange == "US":
            return base
        return f"{base}.{country_exchange}"

    exchange = None
    base = raw
    if "." in raw:
        parts = raw.split(".")
        if len(parts) == 2:
            base, suffix = parts
            if suffix in _SUFFIX_MAP:
                exchange = _SUFFIX_MAP[suffix]
            elif suffix.isalpha() and len(suffix) <= 3:
                # Publisher tag, not a venue: NDA.FI → NDA-FI (+ country → .HE).
                base = f"{base}-{suffix}"
            else:
                exchange = suffix
        elif len(parts) >= 3:
            # NDA.FI.HE → NDA-FI.HE
            if parts[-1] in _SUFFIX_MAP:
                exchange = _SUFFIX_MAP[parts[-1]]
                base = "-".join(parts[:-1])
            else:
                base = "-".join(parts)
        else:
            return None

    if not base:
        return None

    exchange = exchange or country_exchange
    if exchange in _NORDIC_EXCHANGES:
        base = _nordic_share_class(base)

    if not exchange or exchange == "US":
        return base
    return f"{base}.{exchange}"


def _company_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (name or "").casefold())


@lru_cache(maxsize=1)
def load_ticker_remaps(path: str | None = None) -> dict[str, str]:
    target = Path(path) if path else REMAP_PATH
    if not target.is_file():
        return {}
    payload = json.loads(target.read_text(encoding="utf-8"))
    remaps = payload.get("remaps") or {}
    return {str(key): str(value) for key, value in remaps.items()}


def apply_ticker_remap(ticker: str | None, remaps: dict[str, str] | None = None) -> str | None:
    if not ticker:
        return None
    table = remaps if remaps is not None else load_ticker_remaps()
    return table.get(ticker, ticker)


@lru_cache(maxsize=1)
def load_pool_document(path: str | None = None) -> dict:
    target = Path(path) if path else POOL_PATH
    payload = json.loads(target.read_text(encoding="utf-8"))
    if payload.get("format") not in {POOL_FORMAT, "hebeltrader-index-pool-v1"}:
        raise ValueError(f"unsupported index pool format: {payload.get('format')}")
    return payload


def load_pool_assets(path: str | None = None) -> list[dict]:
    remaps = load_ticker_remaps()
    assets = []
    for raw in load_pool_document(path)["assets"]:
        asset = dict(raw)
        ticker = asset.get("ticker")
        mapped = apply_ticker_remap(ticker, remaps)
        if mapped and mapped != ticker:
            asset.setdefault("ticker_original", ticker)
            asset["ticker"] = mapped
        assets.append(asset)
    return assets


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
    return _dedupe_by_ticker(sorted(by_key.values(), key=lambda a: a["name"].casefold()))


def _asset_quality(asset: dict) -> tuple:
    """Higher is better when collapsing same-ticker pool/overlay rows."""
    sources = asset.get("sources") or []
    sector = (asset.get("sector") or "").casefold()
    return (
        1 if asset.get("structure") else 0,
        1 if asset.get("layer") else 0,
        1 if "curated_global_universe" in sources else 0,
        0 if sector in {"", "information technology"} else 1,
        -len(asset.get("name") or ""),
    )


def _dedupe_by_ticker(assets: list[dict]) -> list[dict]:
    """One market row per ticker (SPX/NDX/curated name variants collapse)."""
    without: list[dict] = []
    by_ticker: dict[str, dict] = {}
    for asset in assets:
        ticker = asset.get("ticker")
        if not ticker:
            without.append(dict(asset))
            continue
        existing = by_ticker.get(ticker)
        if existing is None:
            by_ticker[ticker] = dict(asset)
            continue
        winner = existing if _asset_quality(existing) >= _asset_quality(asset) else asset
        loser = asset if winner is existing else existing
        merged = dict(winner)
        merged["sources"] = sorted(
            set([*(existing.get("sources") or []), *(asset.get("sources") or [])])
        )
        for field in ("structure", "layer", "sector"):
            if merged.get(field) in (None, "", "information technology") and loser.get(field):
                if field != "sector" or loser.get(field) != "information technology":
                    merged[field] = loser[field]
        aliases = list(
            dict.fromkeys([*(existing.get("aliases") or []), *(asset.get("aliases") or [])])
        )
        if aliases:
            merged["aliases"] = aliases
        # Keep alternate display names discoverable without duplicating rank rows.
        alt = loser.get("name")
        if alt and alt != merged.get("name"):
            merged.setdefault("aliases", [])
            if alt not in merged["aliases"]:
                merged["aliases"] = list(dict.fromkeys([*merged["aliases"], alt]))
        by_ticker[ticker] = merged
    return sorted([*by_ticker.values(), *without], key=lambda a: a["name"].casefold())


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
