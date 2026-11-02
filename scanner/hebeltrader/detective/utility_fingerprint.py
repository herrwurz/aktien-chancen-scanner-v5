"""Utility / power-infra fingerprints: offtake/PPA + multi-$bn capex.

For Strom-/Versorger teasers with Rechenzentrum / Abnahmevertrag / Investitionsoffensive
cues, English IR and earnings prose often carries the decisive combo. Generic
„utility + Golden Cross“ peers without contracted load or a named investment plan
must not tie an issuer that uniquely shows both in fetched text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_OFFTAKE = re.compile(
    r"(?:"
    r"power\s+purchase\s+agreements?|\bPPAs?\b|"
    r"offtake\s+agreements?|\bofftake\b|"
    r"take[\s-]*or[\s-]*pay|"
    r"electric\s+service\s+agreements?|\bESAs?\b|"
    r"contracted\s+load|incremental\s+contracted\s+load|"
    r"long[\s-]*term\s+(?:power|electricity|energy)\s+contracts?|"
    r"data[\s-]*cent(?:er|re)s?\s+(?:power|electricity|energy)\s+"
    r"(?:contracts?|agreements?|deals?|demand)|"
    r"(?:contracts?|agreements?|deals?)\s+with\s+(?:data[\s-]*cent(?:er|re)|hyperscale)"
    r")",
    re.I,
)
_CAPEX = re.compile(
    r"(?:"
    r"(?:capital\s+(?:investment|expenditure|plan|program)|capex|"
    r"investment\s+(?:plan|program|initiative)|growth\s+plan|"
    r"multi[\s-]*year\s+investment)"
    r"[^\d]{0,48}?"
    r"(?:\$|usd)?\s*(?P<value>\d+(?:[.,]\d+)?)\s*"
    r"(?P<unit>billion|bn\b|mrd\.?)"
    r"|"
    r"(?:\$|usd)?\s*(?P<value2>\d+(?:[.,]\d+)?)\s*"
    r"(?P<unit2>billion|bn\b|mrd\.?)\s*(?:dollar|usd|\$)?"
    r"[^\n]{0,48}?"
    r"(?:capital\s+(?:investment|expenditure|plan)|capex|investment\s+plan)"
    r"|"
    # "$100 billion five-year capital plan" / "five-year, $72 billion capital plan"
    r"(?:five[\s-]*year|5[\s-]*year|multi[\s-]*year)[^\d$]{0,40}"
    r"(?:\$|usd)?\s*(?P<value3>\d+(?:[.,]\d+)?)\s*"
    r"(?P<unit3>billion|bn\b|mrd\.?)"
    r")"
    r"(?!\s*\d+(?:[.,]\d+)?\s*%)",  # reject table cells like "$2.5 billion 200.0%"
    re.I,
)
_CAPEX_PLAN_HINT = re.compile(
    r"capital\s+plan|capex\s+plan|five[\s-]*year|5[\s-]*year|multi[\s-]*year|"
    r"investment\s+(?:plan|program)",
    re.I,
)
_DATA_CENTER = re.compile(
    r"data[\s-]*cent(?:er|re)s?|hyperscale|colocation|co[\s-]*location",
    re.I,
)

_TEASER_UTILITY_CUES = re.compile(
    r"versorger|utilit|strom\w*|rechenzentr\w*|abnahmevertr\w*|investitionsoffensive|"
    r"data\s*cent(?:er|re)|power\s+purchase|offtake",
    re.I,
)


def teaser_wants_utility_fingerprint(text: str) -> bool:
    return bool(_TEASER_UTILITY_CUES.search(text or ""))


@dataclass(frozen=True)
class UtilityFingerprint:
    has_offtake: bool = False
    has_data_center_link: bool = False
    capex_billions: float | None = None

    @property
    def components(self) -> int:
        return sum(
            [
                self.has_offtake,
                self.has_data_center_link,
                self.capex_billions is not None,
            ]
        )


def _capex_billions(match: re.Match) -> float | None:
    groups = match.groupdict()
    value = groups.get("value") or groups.get("value2") or groups.get("value3")
    if value is None:
        return None
    return float(value.replace(",", "."))


def _capex_match_quality(match: re.Match) -> int:
    """Prefer multi-year capital *plans* over proxy-table „Capital Investment“ noise."""
    # Include a short tail so "… capital investment plan" still counts as a plan.
    span = (match.group(0) + match.string[match.end() : match.end() + 16]).casefold()
    after = match.string[match.end() : match.end() + 24]
    if re.search(r"^\s*\d+(?:[.,]\d+)?\s*%", after):
        return -10
    quality = 0
    if _CAPEX_PLAN_HINT.search(span):
        quality += 3
    if re.search(r"five[\s-]*year|5[\s-]*year|multi[\s-]*year", span):
        quality += 2
    if "plan" in span or "program" in span:
        quality += 1
    # Bare "capital investment $X billion" without plan/years is weak.
    if "capital investment" in span and "plan" not in span and quality < 3:
        quality -= 2
    return quality


def extract_utility_fingerprint(text: str) -> UtilityFingerprint:
    blob = text or ""
    best: tuple[int, float] | None = None
    for match in _CAPEX.finditer(blob):
        amount = _capex_billions(match)
        if amount is None:
            continue
        quality = _capex_match_quality(match)
        if quality < 0:
            continue
        # Utility mega-plans are typically ≥$5bn; keep smaller only with strong plan cues.
        if amount < 5 and quality < 3:
            continue
        key = (quality, amount)
        if best is None or key > best:
            best = key
    return UtilityFingerprint(
        has_offtake=bool(_OFFTAKE.search(blob)),
        has_data_center_link=bool(_DATA_CENTER.search(blob)),
        capex_billions=None if best is None else best[1],
    )


def utility_fingerprint_score(fingerprint: UtilityFingerprint) -> int:
    if fingerprint.components == 0:
        return 0
    score = 6 * fingerprint.components
    if fingerprint.has_offtake and fingerprint.has_data_center_link:
        score += 14
    if fingerprint.capex_billions is not None:
        if fingerprint.capex_billions >= 1:
            score += 8
        if fingerprint.capex_billions >= 5:
            score += 6
        if fingerprint.capex_billions >= 10:
            score += 4
    # Full combo mirrors the ARR fingerprint lesson for utilities.
    if fingerprint.components >= 3:
        score += 20
    return score


def _fingerprint_scan(documents: list[dict]) -> UtilityFingerprint:
    offtake = dc = False
    capex = None
    for doc in documents or []:
        text = str(doc.get("text") or "")
        if doc.get("title"):
            text = str(doc["title"]) + "\n" + text
        found = extract_utility_fingerprint(text)
        offtake = offtake or found.has_offtake
        dc = dc or found.has_data_center_link
        if found.capex_billions is not None and (capex is None or found.capex_billions > capex):
            capex = found.capex_billions
    return UtilityFingerprint(has_offtake=offtake, has_data_center_link=dc, capex_billions=capex)


def fingerprint_from_documents(documents: list[dict]) -> UtilityFingerprint:
    """Prefer issuer/SEC for offtake/DC; allow capex figures from any fetched doc."""
    from .source_kind import document_is_primary

    docs = list(documents or [])
    primary = [d for d in docs if document_is_primary(d)]
    primary_fp = _fingerprint_scan(primary)
    all_fp = _fingerprint_scan(docs)
    # Rare combo on primary wins; still pick up a larger $bn plan from IR decks/news.
    if primary_fp.has_offtake and primary_fp.has_data_center_link:
        capex = all_fp.capex_billions
        if primary_fp.capex_billions is not None and (
            capex is None or primary_fp.capex_billions > capex
        ):
            capex = primary_fp.capex_billions
        return UtilityFingerprint(
            has_offtake=True,
            has_data_center_link=True,
            capex_billions=capex,
        )
    if primary_fp.components and primary_fp.components >= all_fp.components:
        return primary_fp
    return all_fp


def apply_utility_fingerprints(
    ranked: list[dict], documents_by_asset: dict[str, list[dict]], *, teaser_text: str = ""
) -> dict:
    """Score offtake/capex fingerprints when the teaser cues a utility power story."""
    from .source_kind import document_is_primary

    summary = {"status": "applied", "scored": []}
    if not teaser_wants_utility_fingerprint(teaser_text):
        summary["status"] = "skipped_no_utility_cues"
        return summary
    if not ranked:
        summary["status"] = "skipped_empty"
        return summary
    for row in ranked:
        docs = documents_by_asset.get(row.get("asset_id")) or []
        docs = docs if isinstance(docs, list) else []
        primary = [d for d in docs if document_is_primary(d)]
        primary_fp = _fingerprint_scan(primary)
        fingerprint = fingerprint_from_documents(docs)
        bonus = utility_fingerprint_score(fingerprint)
        # Full combo only from secondary news is weaker than issuer/SEC primary.
        provenance = "primary" if primary_fp.components >= 2 else "secondary_or_mixed"
        if (
            fingerprint.components >= 2
            and primary_fp.components < 2
            and provenance == "secondary_or_mixed"
        ):
            bonus = max(0, bonus - 14)
            provenance = "secondary_only"
        row["utility_fingerprint"] = {
            "has_offtake": fingerprint.has_offtake,
            "has_data_center_link": fingerprint.has_data_center_link,
            "capex_billions": fingerprint.capex_billions,
            "components": fingerprint.components,
            "bonus": bonus,
            "provenance": provenance,
            "primary_components": primary_fp.components,
        }
        if bonus and not row.get("hard_contradictions"):
            row["evidence_score"] = int(row.get("evidence_score") or 0) + bonus
        summary["scored"].append(
            {
                "asset_id": row.get("asset_id"),
                "bonus": bonus,
                "components": fingerprint.components,
                "provenance": provenance,
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
