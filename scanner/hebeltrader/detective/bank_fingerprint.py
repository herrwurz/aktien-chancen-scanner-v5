"""Bank capital-base fingerprints.

HT-202 lesson: „Kapitalbasis“, wiederkehrende Rekordgewinne und Dividenden/Rückkäufe
„in greifbarer Nähe“ beschreiben eine Bankbilanz. Industriekonzerne dürfen davor nicht
allein durch einen Chart-Treffer oder eine Kennzahl führen, die der Teaser nicht nennt.
Der Aufschlag gilt jeder Bank im Universum, nicht einem einzelnen Namen.
"""

from __future__ import annotations

import re

from .defense_fingerprint import teaser_wants_defense_fingerprint
from .utility_fingerprint import teaser_wants_utility_fingerprint

_CAPITAL_BASE = re.compile(
    r"kapitalbasis|kernkapital|\bcet\s*1\b|common\s+equity\s+tier\s*1|"
    r"harte[rn]?\s+kernkapital",
    re.I,
)
_BANK_NAME = re.compile(r"bank|banco|banque", re.I)
_INSURER_NAME = re.compile(
    r"\b("
    r"allianz|axa|generali|zurich|talanx|prudential|metlife|"
    r"swiss\s+re|aig|m[üu]nchener\s+r[üu]ck|munich\s+re|hannover\s+r[üu]ck"
    r")\b",
    re.I,
)

# Larger than a single 200-day confirmation, smaller than a real multi-source lead
# once false ARR bonuses are gated off.
_BANK_BOOST = 36
_INSURER_DEMOTE = 20
_OTHER_DEMOTE = 48


def teaser_wants_bank_capital(text: str) -> bool:
    return bool(_CAPITAL_BASE.search(text or ""))


def _identity(row: dict) -> dict:
    data = row.get("identity")
    if isinstance(data, dict):
        return data
    if data is not None and hasattr(data, "model_dump"):
        return data.model_dump()
    return {}


def _role(name: str) -> str:
    if _BANK_NAME.search(name or ""):
        return "bank"
    if _INSURER_NAME.search(name or ""):
        return "insurer"
    return "other"


def apply_bank_capital_fingerprints(ranked: list[dict], *, teaser_text: str = "") -> dict:
    """Boost banks and demote industrials when the teaser asserts a capital base."""
    summary: dict = {"status": "applied", "scored": []}
    if not teaser_wants_bank_capital(teaser_text):
        summary["status"] = "skipped_no_capital_base"
        return summary
    if teaser_wants_utility_fingerprint(teaser_text) or teaser_wants_defense_fingerprint(
        teaser_text
    ):
        summary["status"] = "skipped_other_sector"
        return summary
    if not ranked:
        summary["status"] = "skipped_empty"
        return summary

    for row in ranked:
        name = _identity(row).get("name") or ""
        role = _role(name)
        if role == "bank":
            delta = _BANK_BOOST
            note = "Teaser nennt eine Kapitalbasis; der Kandidat ist eine Bank."
        elif role == "insurer":
            delta = -_INSURER_DEMOTE
            note = (
                "Teaser nennt eine Kapitalbasis. Versicherer bleiben Kandidaten, "
                "stehen aber hinter Banken."
            )
        else:
            delta = -_OTHER_DEMOTE
            note = (
                "Teaser nennt eine Kapitalbasis; Industrie- oder Sachkonzern "
                "ohne Bankbilanz wird zurückgestuft."
            )
        counters = list(row.get("counterarguments") or [])
        if note not in counters:
            counters.append(note)
        row["counterarguments"] = counters
        row["bank_fingerprint"] = {"role": role, "delta": delta}
        row["evidence_score"] = int(row.get("evidence_score") or 0) + delta
        summary["scored"].append({"asset_id": row.get("asset_id"), "role": role, "delta": delta})

    ranked.sort(
        key=lambda row: (
            bool(row.get("hard_contradictions")),
            -int(row.get("evidence_score") or 0),
            row.get("asset_id") or "",
        )
    )
    return summary
