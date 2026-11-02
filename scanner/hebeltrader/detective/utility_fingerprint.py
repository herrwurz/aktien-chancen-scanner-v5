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
    r")",
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
    value = match.groupdict().get("value") or match.groupdict().get("value2")
    if value is None:
        return None
    return float(value.replace(",", "."))


def extract_utility_fingerprint(text: str) -> UtilityFingerprint:
    blob = text or ""
    capex = None
    for match in _CAPEX.finditer(blob):
        amount = _capex_billions(match)
        if amount is not None and (capex is None or amount > capex):
            capex = amount
    return UtilityFingerprint(
        has_offtake=bool(_OFFTAKE.search(blob)),
        has_data_center_link=bool(_DATA_CENTER.search(blob)),
        capex_billions=capex,
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


def fingerprint_from_documents(documents: list[dict]) -> UtilityFingerprint:
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


def apply_utility_fingerprints(
    ranked: list[dict], documents_by_asset: dict[str, list[dict]], *, teaser_text: str = ""
) -> dict:
    """Score offtake/capex fingerprints when the teaser cues a utility power story."""
    summary = {"status": "applied", "scored": []}
    if not teaser_wants_utility_fingerprint(teaser_text):
        summary["status"] = "skipped_no_utility_cues"
        return summary
    if not ranked:
        summary["status"] = "skipped_empty"
        return summary
    for row in ranked:
        docs = documents_by_asset.get(row.get("asset_id")) or []
        fingerprint = fingerprint_from_documents(docs if isinstance(docs, list) else [])
        bonus = utility_fingerprint_score(fingerprint)
        row["utility_fingerprint"] = {
            "has_offtake": fingerprint.has_offtake,
            "has_data_center_link": fingerprint.has_data_center_link,
            "capex_billions": fingerprint.capex_billions,
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
