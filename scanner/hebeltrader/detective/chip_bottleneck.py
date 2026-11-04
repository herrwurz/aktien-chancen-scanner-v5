"""Hidden chip-bottleneck layer.

HT-201 lesson: „heimlicher Herrscher“ plus „Kunden haben kaum noch eine Wahl“ in der
Chipindustrie ist nicht der bekannte Anlagen- oder Foundry-Name. Die nicht offensichtliche
Schicht ist Design-Software (EDA) und IP. Beide Seiten eines Duopols bleiben Kandidaten;
ein einzelner Firmenname wird nicht fest verdrahtet.
"""

from __future__ import annotations

import re

from .us_session_quote import teaser_quotes_from_us_session

_CHIP = re.compile(r"\bchip\w*|halbleiter|semiconductor", re.I)
_HIDDEN = re.compile(r"heimlich\w*|geheimnis|im verborgenen", re.I)
_NO_CHOICE = re.compile(
    r"kaum\s+(?:noch\s+)?eine\s+wahl|keine\s+wahl|unverzichtbar|keine\s+alternative|"
    r"alternativlos|herrscher|monopol",
    re.I,
)
# If the teaser itself names the obvious layer, do not hide it.
_NAMED_OBVIOUS_LAYER = re.compile(
    r"\beuv\b|lithograph\w*|foundry|gießerei|grafikprozessor|\bgpu\b",
    re.I,
)
_EDA_IP = re.compile(
    r"\b(synopsys|cadence(?:\s+design)?|arm holdings|ansys|mentor graphics)\b",
    re.I,
)
_OBVIOUS_BOTTLENECK = re.compile(
    r"\b(asml|tsmc|taiwan semiconductor|nvidia|applied materials)\b",
    re.I,
)
_NON_US_PRIMARY = re.compile(
    r"\b(asml|tsmc|taiwan semiconductor|samsung electronics|sk hynix|infineon|"
    r"stmicroelectronics|tokyo electron|advantest)\b",
    re.I,
)

_EDA_BOOST = 36
_OBVIOUS_DEMOTE = 36
_OTHER_DEMOTE = 18
_NON_US_EXTRA = 16

HIDDEN_CHIP_QUERIES = (
    "chip design software duopoly market share customers no alternative",
    "semiconductor electronic design automation IP licensing indispensable supplier earnings",
    "EDA tools market share semiconductor design customers cannot switch",
)


def teaser_wants_hidden_chip_bottleneck(text: str) -> bool:
    blob = text or ""
    return bool(
        _CHIP.search(blob)
        and _HIDDEN.search(blob)
        and _NO_CHOICE.search(blob)
        and not _NAMED_OBVIOUS_LAYER.search(blob)
    )


def _name(row: dict) -> str:
    data = row.get("identity")
    if isinstance(data, dict):
        return data.get("name") or ""
    if data is not None and hasattr(data, "model_dump"):
        return data.model_dump().get("name") or ""
    return ""


def apply_hidden_chip_bottleneck(ranked: list[dict], *, teaser_text: str = "") -> dict:
    """Boost EDA/IP and demote famous equipment, foundry and GPU names."""
    summary: dict = {"status": "applied", "scored": []}
    if not teaser_wants_hidden_chip_bottleneck(teaser_text):
        summary["status"] = "skipped_not_hidden_chip_bottleneck"
        return summary
    if not ranked:
        summary["status"] = "skipped_empty"
        return summary
    us_session = teaser_quotes_from_us_session(teaser_text)
    for row in ranked:
        name = _name(row)
        if _EDA_IP.search(name):
            role, delta = "eda_ip", _EDA_BOOST
            note = (
                "Teaser nennt einen heimlichen Engpass der Chipindustrie; "
                "Design-Software und IP bleiben in der engeren Wahl."
            )
        elif _OBVIOUS_BOTTLENECK.search(name):
            role, delta = "obvious_bottleneck", -_OBVIOUS_DEMOTE
            note = (
                "Teaser nennt einen heimlichen Herrscher; "
                "bekannte Anlagen-, Foundry- oder GPU-Namen werden zurückgestuft."
            )
        else:
            role, delta = "other", -_OTHER_DEMOTE
            note = (
                "Teaser nennt einen heimlichen Engpass; "
                "ein reiner Chart-Treffer bei einem Produktkonzern reicht nicht."
            )
        if us_session and _NON_US_PRIMARY.search(name):
            delta -= _NON_US_EXTRA
            note += " Der Schein wird erst zum US-Handelsbeginn quotiert."
        counters = list(row.get("counterarguments") or [])
        if note not in counters:
            counters.append(note)
        row["counterarguments"] = counters
        row["chip_bottleneck"] = {"role": role, "delta": delta}
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
