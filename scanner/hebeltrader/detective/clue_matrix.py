"""Sector shortlist plus a clue matrix.

A layer decides who may be searched. It does not add points. Points come from
confirmed teaser clues and are reduced by contradictions. No company is named
as the winner.
"""

from __future__ import annotations

import re

from .featured_calls import is_blocked
from .structure_screen import find_asset, load_universe, sectors_in
from .us_session_quote import listed_outside_us_session, teaser_quotes_from_us_session

_METRIC_BITS = (
    (r"bruttomarge|gross margin", "gross margin"),
    (r"freier?\s+cash\s*flow|freier?\s+cashflow|free cash flow", "free cash flow"),
    (r"gewinn je aktie|earnings per share", "earnings per share"),
    (r"\bumsatz\b|\brevenue\b", "revenue"),
    (r"\bgewinn\b|\bearnings\b", "earnings"),
)
_EVENT_BITS = (
    (r"zukäuf\w*|übernah\w*|acqui\w*", "acquisition"),
    (r"robot\w*", "robotics"),
    (r"rechenzentr\w*|data\s*cent", "data center"),
    (r"prognos\w*[^.!?]{0,45}angehoben|guidance raise", "raised guidance"),
)
_ROLE = re.compile(r"im hintergrund|gro[sß]e[n]?\s+ki-namen", re.I)
_SPECIFIC = frozenset({"fact_claims", "financial_metric", "semantic_fact"})


def extract_constraints(text: str) -> list[dict]:
    """Typed demands from the teaser. Empty when the text has no sector cue."""
    blob = text or ""
    constraints: list[dict] = []
    sectors = sectors_in(blob)
    if sectors:
        constraints.append({"kind": "sector", "label": sectors[0]})
    for pattern, label in _METRIC_BITS:
        if re.search(pattern, blob, re.I):
            constraints.append({"kind": "metric", "label": label})
    for pattern, label in _EVENT_BITS:
        if re.search(pattern, blob, re.I):
            constraints.append({"kind": "event", "label": label})
    if _ROLE.search(blob):
        constraints.append({"kind": "role", "label": "Hintergrund gegenüber bekannten Namen"})
    if teaser_quotes_from_us_session(blob):
        constraints.append({"kind": "venue", "label": "US-Handelssitz"})
    return constraints


def constraint_phrase(text: str) -> str:
    labels = [
        item["label"] for item in extract_constraints(text) if item["kind"] in {"metric", "event"}
    ]
    if not labels:
        return "quarterly results"
    return " ".join(labels[:4])


def _round_robin(assets: list[dict], limit: int) -> list[dict]:
    layers: dict[str, list[dict]] = {}
    for asset in assets:
        layers.setdefault(asset.get("layer") or "other", []).append(asset)
    for layer in layers:
        layers[layer].sort(key=lambda item: item.get("name") or "")
    order = sorted(layers)
    picked: list[dict] = []
    depth = 0
    while len(picked) < limit:
        progressed = False
        for layer in order:
            bucket = layers[layer]
            if depth < len(bucket):
                picked.append(bucket[depth])
                progressed = True
                if len(picked) >= limit:
                    break
        if not progressed:
            break
        depth += 1
    return picked


def eligible_shortlist(text: str, *, blocked=None, limit: int = 40) -> list[dict]:
    """Every universe name in the teaser's sector, one layer at a time.

    Venue wording drops listings outside that session. Layer membership is the
    filter, not a score.
    """
    sectors = set(sectors_in(text))
    if not sectors or limit < 1:
        return []
    us_session = teaser_quotes_from_us_session(text)
    eligible = []
    for asset in load_universe():
        if asset.get("sector") not in sectors:
            continue
        if is_blocked(asset, blocked):
            continue
        ticker = asset.get("ticker")
        if us_session and listed_outside_us_session(ticker):
            continue
        eligible.append(asset)
    return _round_robin(eligible, limit)


def shortlist_queries(text: str, assets: list[dict], *, limit: int = 8) -> list[str]:
    """Name-scoped queries so the paid budget reaches each eligible layer."""
    if limit < 1:
        return []
    phrase = constraint_phrase(text)
    queries = []
    for asset in assets:
        name = str(asset.get("name") or "").strip()
        if not name:
            continue
        queries.append(f'"{name}" {phrase} investor relations')
        if len(queries) >= limit:
            break
    return queries


def _identity_name(row: dict) -> str:
    data = row.get("identity")
    if isinstance(data, dict):
        return data.get("name") or ""
    if data is not None and hasattr(data, "model_dump"):
        return data.model_dump().get("name") or ""
    return ""


def _layer_delta(row: dict) -> int:
    """Points that came from a layer or a market-structure bonus, not from a filing."""
    total = 0
    for key in ("background_chip", "chip_bottleneck"):
        block = row.get(key) or {}
        if isinstance(block, dict):
            total += int(block.get("delta") or 0)
    structure = row.get("market_structure") or {}
    if isinstance(structure, dict):
        total += int(structure.get("bonus") or 0)
    return total


def _clue_counts(row: dict) -> tuple[int, int]:
    confirmed = contradicted = 0
    for cell in row.get("evidence_matrix") or []:
        if not isinstance(cell, dict):
            continue
        category = cell.get("category")
        status = cell.get("status")
        if status == "confirmed" and category in _SPECIFIC:
            confirmed += 1
        elif status == "contradicted":
            contradicted += 1
    return confirmed, contradicted


def apply_clue_matrix(ranked: list[dict], *, teaser_text: str = "") -> dict:
    """Drop layer bonuses from the score and record the clue matrix.

    Confirmed and contradicted clues already sit in ``evidence_score``. This step
    removes only the layer and structure deltas, once per row.
    """
    constraints = extract_constraints(teaser_text)
    summary_rows = []
    for row in ranked:
        if row.get("clue_matrix_layer_stripped") is None:
            stripped = _layer_delta(row)
            if stripped:
                row["evidence_score"] = int(row.get("evidence_score") or 0) - stripped
            row["clue_matrix_layer_stripped"] = stripped
        else:
            stripped = int(row.get("clue_matrix_layer_stripped") or 0)
        confirmed, contradicted = _clue_counts(row)
        asset = find_asset(_identity_name(row))
        matrix = {
            "layer": (asset or {}).get("layer"),
            "layer_points": 0,
            "stripped_layer_points": stripped,
            "confirmed": confirmed,
            "contradicted": contradicted,
            "constraints": [item["label"] for item in constraints],
        }
        row["clue_matrix"] = matrix
        summary_rows.append(
            {
                "asset_id": row.get("asset_id"),
                "layer": matrix["layer"],
                "layer_points": 0,
                "confirmed": confirmed,
                "contradicted": contradicted,
            }
        )
    ranked.sort(
        key=lambda row: (
            bool(row.get("hard_contradictions")),
            -int(row.get("evidence_score") or 0),
            row.get("asset_id") or "",
        )
    )
    return {
        "status": "applied",
        "layer_points": 0,
        "constraints": [item["label"] for item in constraints],
        "rows": summary_rows,
    }
