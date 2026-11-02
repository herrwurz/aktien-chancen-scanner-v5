"""Distinctive earnings fingerprints beat generic fintech/ATH overlap.

Lesson from HEBELTRADER 199/26 (Nasdaq): the decisive combination was index-business
growth (~39%), absolute ARR (~USD 3.4bn) and a high adjusted operating margin (~57%).
Peers that only share „Fintech + Quartalszahlen + Allzeithoch“ must not tie or outrank
an issuer that uniquely carries that metric fingerprint in primary results text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_ARR = re.compile(
    r"(?:annualized recurring revenue|\bARR\b|j[äa]hrlich(?:e|en)? wiederkehrend(?:e|en)? "
    r"(?:erl[öo]se|ums[äa]tze|revenue))"
    r"[^\d]{0,40}?"
    r"(?P<value>\d+(?:[.,]\d+)?)\s*"
    r"(?P<unit>billion|bn\b|mrd\.?|million|mio\.?)?"
    r"(?:\s*(?:dollar|usd|\$|euro|eur))?",
    re.I,
)
# Also "record ARR of $3.4 billion" / "3.4 Milliarden Dollar"
_ARR_VALUE_FIRST = re.compile(
    r"(?:\$|usd)?\s*(?P<value>\d+(?:[.,]\d+)?)\s*"
    r"(?P<unit>billion|bn\b|mrd\.?)\s*(?:dollar|usd|\$)?"
    r"[^\n]{0,40}?(?:annualized recurring revenue|\bARR\b|"
    r"j[äa]hrlich(?:e|en)? wiederkehrend)",
    re.I,
)
_PCT = r"(?:%|percent|prozent)"
_OP_MARGIN = re.compile(
    r"(?:adjusted\s+)?"
    r"(?:"
    r"operating\s+margin|op(?:erating)?\.?\s*margin|"
    r"(?:operative[rn]?|bereinigt(?:e|en)?\s+operativ(?:e|en)?)\s+marge"
    r")"
    rf"[^\d%]{{0,30}}?(?P<value>\d+(?:[.,]\d+)?)\s*{_PCT}",
    re.I,
)
_OP_MARGIN_FLIP = re.compile(
    rf"(?P<value>\d+(?:[.,]\d+)?)\s*{_PCT}[^\n]{{0,40}}?"
    r"(?:adjusted\s+)?(?:operating margin|operative[rn]?\s+marge)",
    re.I,
)
_SEGMENT_GROWTH = re.compile(
    r"(?P<segment>index(?:geschäft| business| revenues?)?|markets?|solutions?|"
    r"financial technology|fintech|data|analytics|listings?)"
    r"[^\d%]{0,48}?(?:grew|growth|wuchs|stieg|kletterte|explodierte|zulegte|"
    rf"\+\s*|um\s+)?(?P<value>\d+(?:[.,]\d+)?)\s*{_PCT}",
    re.I,
)
_SEGMENT_GROWTH_FLIP = re.compile(
    rf"(?P<value>\d+(?:[.,]\d+)?)\s*{_PCT}[^\n]{{0,48}}?"
    r"(?P<segment>index(?:geschäft| business| revenues?)?|markets?|solutions?|"
    r"financial technology|fintech)",
    re.I,
)


def _num(value: str) -> float:
    return float(value.replace(",", "."))


def _arr_billions(value: str, unit: str | None) -> float | None:
    amount = _num(value)
    unit = (unit or "").casefold()
    if unit.startswith("mrd") or unit.startswith("billion") or unit == "bn":
        return amount
    if unit.startswith("mio") or unit.startswith("million"):
        return amount / 1000.0
    # Bare number next to ARR: treat >= 1 as billions when in ARR grammar.
    if amount >= 1:
        return amount
    return None


@dataclass(frozen=True)
class MetricFingerprint:
    arr_billions: float | None = None
    operating_margin_pct: float | None = None
    segment_growth: tuple[str, float] | None = None  # segment label, pct

    @property
    def components(self) -> int:
        return sum(
            [
                self.arr_billions is not None,
                self.operating_margin_pct is not None,
                self.segment_growth is not None,
            ]
        )


def extract_metric_fingerprint(text: str) -> MetricFingerprint:
    """Pull ARR, operating margin and a named segment growth rate from issuer text."""
    arr = None
    for match in list(_ARR.finditer(text or "")) + list(_ARR_VALUE_FIRST.finditer(text or "")):
        billions = _arr_billions(match.group("value"), match.groupdict().get("unit"))
        if billions is not None:
            arr = billions
            break

    margin = None
    for match in list(_OP_MARGIN.finditer(text or "")) + list(_OP_MARGIN_FLIP.finditer(text or "")):
        margin = _num(match.group("value"))
        break

    segment = None
    for match in list(_SEGMENT_GROWTH.finditer(text or "")) + list(
        _SEGMENT_GROWTH_FLIP.finditer(text or "")
    ):
        label = re.sub(r"\s+", " ", match.group("segment").casefold()).strip()
        segment = (label, _num(match.group("value")))
        break

    return MetricFingerprint(arr_billions=arr, operating_margin_pct=margin, segment_growth=segment)


def fingerprint_rarity_score(fingerprint: MetricFingerprint) -> int:
    """Higher score for rare absolute ARR + high margin + named segment growth combos."""
    if fingerprint.components == 0:
        return 0
    score = 8 * fingerprint.components
    if fingerprint.arr_billions is not None and fingerprint.arr_billions >= 1:
        score += 12
        if fingerprint.arr_billions >= 3:
            score += 8
    if fingerprint.operating_margin_pct is not None and fingerprint.operating_margin_pct >= 40:
        score += 10
        if fingerprint.operating_margin_pct >= 50:
            score += 6
    if fingerprint.segment_growth is not None:
        label, pct = fingerprint.segment_growth
        if pct >= 20:
            score += 8
        if pct >= 30:
            score += 6
        if "index" in label:
            score += 4
    # Full three-component fingerprint (the 199/26 lesson) is decisive vs peers.
    if fingerprint.components >= 3:
        score += 25
    return score


def fingerprint_from_documents(documents: list[dict]) -> MetricFingerprint:
    """Merge the strongest components seen across a candidate's fetched docs."""
    arr = margin = None
    segment = None
    for doc in documents or []:
        text = str(doc.get("text") or "")
        if doc.get("title"):
            text = str(doc["title"]) + "\n" + text
        found = extract_metric_fingerprint(text)
        if found.arr_billions is not None and (arr is None or found.arr_billions > arr):
            arr = found.arr_billions
        if found.operating_margin_pct is not None and (
            margin is None or found.operating_margin_pct > margin
        ):
            margin = found.operating_margin_pct
        if found.segment_growth is not None:
            if segment is None or found.segment_growth[1] > segment[1]:
                segment = found.segment_growth
    return MetricFingerprint(arr_billions=arr, operating_margin_pct=margin, segment_growth=segment)


def apply_metric_fingerprints(
    ranked: list[dict], documents_by_asset: dict[str, list[dict]]
) -> dict:
    """Add fingerprint bonuses; full three-metric combos outrank generic peers."""
    summary = {"status": "applied", "scored": []}
    if not ranked:
        summary["status"] = "skipped_empty"
        return summary
    for row in ranked:
        docs = documents_by_asset.get(row.get("asset_id")) or row.get("sources") or []
        # sources may be evidence records; prefer explicit docs map.
        fingerprint = fingerprint_from_documents(docs if isinstance(docs, list) else [])
        bonus = fingerprint_rarity_score(fingerprint)
        row["metric_fingerprint"] = {
            "arr_billions": fingerprint.arr_billions,
            "operating_margin_pct": fingerprint.operating_margin_pct,
            "segment_growth": (
                {"segment": fingerprint.segment_growth[0], "pct": fingerprint.segment_growth[1]}
                if fingerprint.segment_growth
                else None
            ),
            "components": fingerprint.components,
            "bonus": bonus,
        }
        if bonus and not row.get("hard_contradictions"):
            row["evidence_score"] = int(row.get("evidence_score") or 0) + bonus
        summary["scored"].append(
            {
                "asset_id": row.get("asset_id"),
                "bonus": bonus,
                "components": fingerprint.components,
            }
        )
    ranked.sort(
        key=lambda row: (
            bool(row.get("hard_contradictions")),
            -row.get("evidence_score", 0),
            row.get("asset_id") or "",
        )
    )
    return summary
