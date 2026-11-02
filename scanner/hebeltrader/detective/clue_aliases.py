"""German teaser terms → English filing/news aliases for PIT evidence matching.

Teasers name clues in German; SEC IR and most US utility press use English.
Exact-string overlap then silently fails (e.g. Rechenzentrumsbetreibern vs data center).
"""

from __future__ import annotations

import re

# Longest keys first when matching; values are English search phrases.
_TERM_ALIASES: dict[str, tuple[str, ...]] = {
    "rechenzentrumsbetreibern": (
        "data center",
        "data centres",
        "data centre",
        "hyperscale",
        "colocation",
        "co-location",
    ),
    "rechenzentrumsbetreiber": (
        "data center",
        "data centres",
        "data centre",
        "hyperscale",
        "colocation",
    ),
    "rechenzentren": ("data centers", "data centres", "hyperscale campuses"),
    "rechenzentrum": ("data center", "data centre", "hyperscale"),
    "abnahmeverträgen": (
        "power purchase agreement",
        "power purchase agreements",
        "offtake agreement",
        "offtake",
        "take-or-pay",
        "long-term contract",
        "long term contract",
    ),
    "abnahmeverträge": (
        "power purchase agreement",
        "power purchase agreements",
        "offtake agreement",
        "offtake",
        "take-or-pay",
        "long-term contract",
    ),
    "abnahmevertrag": (
        "power purchase agreement",
        "offtake agreement",
        "offtake",
        "take-or-pay",
    ),
    "investitionsoffensive": (
        "capital investment",
        "capital expenditure",
        "capex",
        "investment program",
        "growth plan",
        "multi-year investment",
    ),
    "quartalszahlen": ("quarterly results", "quarterly earnings", "earnings results"),
}


def clue_search_terms(term: str) -> list[str]:
    """Return the original term plus English aliases (deduped, original first)."""
    raw = (term or "").strip()
    if not raw:
        return []
    folded = raw.casefold()
    aliases = _TERM_ALIASES.get(folded)
    if aliases is None:
        for key, values in _TERM_ALIASES.items():
            if folded.startswith(key) or key.startswith(folded):
                aliases = values
                break
    out = [raw]
    for alias in aliases or ():
        if alias.casefold() not in {t.casefold() for t in out}:
            out.append(alias)
    return out


def term_pattern(term: str) -> re.Pattern[str]:
    """Regex that matches the German clue term or any English alias as a phrase."""
    flexible = []
    for item in clue_search_terms(term):
        tokens = re.split(r"[\s-]+", item)
        if len(tokens) > 1:
            flexible.append(r"(?<!\w)" + r"[\s-]+".join(map(re.escape, tokens)) + r"(?!\w)")
        else:
            flexible.append(r"(?<!\w)" + re.escape(item) + r"(?!\w)")
    if not flexible:
        return re.compile(r"(?!)")
    return re.compile("|".join(flexible), re.I)
