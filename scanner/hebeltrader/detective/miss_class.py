"""One diagnostic class for a frozen first prediction versus a later resolution.

The class is derived from the stored ranking and the local universe. It does not
read a solution PDF and it does not rewrite the first prediction.
"""

from __future__ import annotations

LABELS = {
    "confirmed": "Rang 1 bestätigt",
    "not_in_universe": "Nicht im Universum",
    "in_universe_not_retrieved": "Im Universum, nicht abgerufen",
    "retrieved_misranked": "Abgerufen, falsch sortiert",
    "contradicted": "Beleg widerspricht dem Teaser",
}


def _norm(value) -> str:
    return " ".join(str(value or "").casefold().split())


def _row_name(row: dict) -> str:
    identity = row.get("identity") or {}
    if not isinstance(identity, dict):
        identity = {}
    return identity.get("name") or row.get("name") or ""


def _row_asset(row: dict) -> str:
    identity = row.get("identity") or {}
    if not isinstance(identity, dict):
        identity = {}
    return str(row.get("asset_id") or identity.get("asset_id") or "")


def _matches(row: dict, *, asset: str, name: str) -> bool:
    row_asset = _row_asset(row)
    row_name = _norm(_row_name(row))
    if asset and row_asset == asset:
        return True
    if name and row_name == name:
        return True
    if name and row_name and (name in row_name or row_name in name):
        return True
    return False


def _contradicted(row: dict | None) -> bool:
    if not row:
        return False
    if row.get("hard_contradictions"):
        return True
    return any(cell.get("status") == "contradicted" for cell in (row.get("evidence_matrix") or []))


def classify_miss(report, *, resolved_name, resolved_asset_id=None) -> dict:
    """Return exactly one class for the first frozen ranking."""
    report = report or {}
    candidates = list(report.get("candidates") or [])
    checked = list(report.get("checked_candidates") or [])
    asset = (resolved_asset_id or "").strip()
    name = _norm(resolved_name)

    rank = None
    ranked_row = None
    for index, row in enumerate(candidates, 1):
        if _matches(row, asset=asset, name=name):
            rank = index
            ranked_row = row
            break
    retrieved = ranked_row
    if retrieved is None:
        for row in checked:
            if _matches(row, asset=asset, name=name):
                retrieved = row
                break

    from .structure_screen import find_asset

    in_universe = find_asset(resolved_name or "") is not None
    disputed = _contradicted(retrieved)
    if rank == 1 and not disputed:
        kind = "confirmed"
    elif retrieved is not None and disputed and rank != 1:
        kind = "contradicted"
    elif retrieved is not None:
        kind = "retrieved_misranked"
    elif in_universe:
        kind = "in_universe_not_retrieved"
    else:
        kind = "not_in_universe"
    return {"miss_class": kind, "label": LABELS[kind]}
