"""Background semiconductor profit machine.

HT-200 lesson: „während alle auf die großen KI-Namen starren“ plus ein
Halbleiter-Schwergewicht „im Hintergrund“ mit Rekordgewinn, Weltklasse-Bruttomarge
und Zukäufen in KI-Rechenzentren und Robotik ist nicht GPU, Foundry oder Anlage.
Die passende Schicht ist Analog- und Mixed-Signal. Jeder Name dieser Schicht bleibt
Kandidat; ein einzelner Firmenname wird nicht fest verdrahtet.
"""

from __future__ import annotations

import re

from .chip_bottleneck import teaser_wants_hidden_chip_bottleneck

_CHIP = re.compile(r"halbleiter|\bchip\w*|semiconductor", re.I)
_BACKGROUND = re.compile(
    r"im hintergrund|gro[sß]e[n]?\s+ki-namen",
    re.I,
)
_PROFIT = re.compile(
    r"gewinnmaschine|bruttomarge|zukäuf\w*|freier?\s+cash\s*flow|freier?\s+cashflow",
    re.I,
)
_FAMOUS_LAYERS = frozenset(
    {
        "ai-processors",
        "foundry",
        "lithography",
        "wafer-fab-equipment",
        "inspection-metrology",
        "memory",
    }
)
_ANALOG_LAYER = "analog-mcu"
_BOOST = 36
_FAMOUS_DEMOTE = 36

BACKGROUND_CHIP_QUERIES = (
    "analog mixed-signal semiconductor acquisitions AI data center robotics gross margin earnings",
    "semiconductor record revenue EPS free cash flow beat estimates investor relations",
    "analog chip industrial robotics data center signal chain acquisition quarterly results",
)


def teaser_wants_background_chip_profit(text: str) -> bool:
    blob = text or ""
    if teaser_wants_hidden_chip_bottleneck(blob):
        return False
    return bool(_CHIP.search(blob) and _BACKGROUND.search(blob) and _PROFIT.search(blob))


def _name(row: dict) -> str:
    data = row.get("identity")
    if isinstance(data, dict):
        return data.get("name") or ""
    if data is not None and hasattr(data, "model_dump"):
        return data.model_dump().get("name") or ""
    return ""


def apply_background_chip_profit(ranked: list[dict], *, teaser_text: str = "") -> dict:
    """Boost the analog layer and demote the AI names everyone is staring at."""
    from .structure_screen import find_asset

    summary: dict = {"status": "applied", "scored": []}
    if not teaser_wants_background_chip_profit(teaser_text):
        summary["status"] = "skipped_not_background_chip"
        return summary
    if not ranked:
        summary["status"] = "skipped_empty"
        return summary
    for row in ranked:
        asset = find_asset(_name(row))
        layer = (asset or {}).get("layer")
        if layer == _ANALOG_LAYER:
            role, delta = "analog", _BOOST
            note = (
                "Teaser sucht das Halbleiter-Schwergewicht hinter den großen KI-Namen; "
                "die Analog- und Mixed-Signal-Schicht bleibt in der engeren Wahl."
            )
        elif layer in _FAMOUS_LAYERS:
            role, delta = "obvious_ai", -_FAMOUS_DEMOTE
            note = (
                "Teaser sagt, alle starren auf die großen KI-Namen; "
                "GPU, Foundry und Anlagenbauer werden zurückgestuft."
            )
        else:
            summary["scored"].append({"asset_id": row.get("asset_id"), "role": "other", "delta": 0})
            continue
        counters = list(row.get("counterarguments") or [])
        if note not in counters:
            counters.append(note)
        row["counterarguments"] = counters
        row["background_chip"] = {"role": role, "layer": layer, "delta": delta}
        row["evidence_score"] = int(row.get("evidence_score") or 0) + delta
        summary["scored"].append(
            {"asset_id": row.get("asset_id"), "role": role, "layer": layer, "delta": delta}
        )
    ranked.sort(
        key=lambda row: (
            bool(row.get("hard_contradictions")),
            -int(row.get("evidence_score") or 0),
            row.get("asset_id") or "",
        )
    )
    return summary
