"""Classify live/web document URLs into issuer / regulatory / news kinds.

Tavily tags everything as ``search_snippet`` / ``tavily_extract``. Fingerprints and
``source_quality.primary_documents`` need SEC/IR surfaces labeled as primary.
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit

# Pages that carry the current tape in the same language as a teaser.
# They are news, never issuer primary.
MARKET_NEWS_HOSTS = (
    "finanznachrichten.de",
    "wallstreet-online.de",
    "marketwatch.com",
)

_AGGREGATOR_HOST = re.compile(
    r"(?:^|\.)(?:"
    r"seekingalpha|yahoo|finance\.yahoo|fool|reuters|bloomberg|marketwatch|"
    r"alphaspread|stocktitan|fortune|youtube|baidu|intellectia|marketwise|"
    r"financialcontent|theeveningleader|barrons|cnbc|wsj|ft\.com|"
    r"tavily|wikipedia|wikidata|quartr|motleyfool|investing\.com|benzinga|"
    r"businesswire|prnewswire|globenewswire|accesswire"
    r")(?:\.|$)",
    re.I,
)
_IR_PATH = re.compile(
    r"/(?:investors?|investor-relations|shareholder(?:s)?-relations|"
    r"shareholders|stockholder(?:s)?)(?:/|$)",
    re.I,
)
_IR_HOST = re.compile(r"^(?:investors?|ir)\.", re.I)
_SEC_FILING_PATH = re.compile(r"/sec-filings?(?:/|$)|/Archives/edgar/", re.I)


_PRIMARY_KINDS = frozenset({"issuer", "regulatory", "regulator"})


def classify_live_source_kind(url: str) -> str | None:
    """Return ``issuer`` / ``regulatory`` when the URL itself is primary evidence.

    Returns ``None`` when the URL does not justify overriding provider tags
    (generic news, aggregators, unknown hosts).
    """
    parts = urlsplit(url or "")
    host = (parts.hostname or "").lower()
    path = parts.path or ""
    if not host:
        return None
    if any(host == domain or host.endswith("." + domain) for domain in MARKET_NEWS_HOSTS):
        return "news"
    if host == "sec.gov" or host.endswith(".sec.gov"):
        return "regulatory"
    if _SEC_FILING_PATH.search(path) and ("sec" in host or "edgar" in host or "stocktitan" in host):
        return "regulatory"
    if _AGGREGATOR_HOST.search(host):
        return None
    if _IR_HOST.match(host) or _IR_PATH.search(path):
        return "issuer"
    return None


def effective_source_kind(document: dict) -> str:
    """Prefer explicit primary kinds; else upgrade from URL heuristics."""
    kind = str((document or {}).get("source_kind") or "unknown")
    if kind in _PRIMARY_KINDS:
        return "regulatory" if kind == "regulator" else kind
    classified = classify_live_source_kind((document or {}).get("url") or "")
    return classified or kind


def document_is_primary(document: dict) -> bool:
    return effective_source_kind(document) in _PRIMARY_KINDS
