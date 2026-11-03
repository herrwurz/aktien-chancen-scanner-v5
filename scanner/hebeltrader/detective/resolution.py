"""Operator-entered post-freeze resolution; separate from teaser input schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .prose_briefing import why_sentence


class ResolutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    asset_id: str | None = Field(default=None, min_length=1, max_length=300)
    name: str = Field(min_length=1, max_length=300)
    source: str = Field(min_length=1, max_length=2000)
    basis: Literal["user", "primary_source"] = "user"
    call_wkn: str | None = Field(default=None, pattern=r"^[A-Z0-9]{6}$")
    # Optional: journal drafts from the frozen ranking when empty.
    error_analysis: str = Field(default="", max_length=5000)
    algorithm_change: str = Field(default="", max_length=5000)
    confirmed_at: str | None = None
    original_sha256: str | None = None


def _norm(value):
    return " ".join(str(value or "").casefold().split())


def _row_name(row):
    identity = row.get("identity") or {}
    return identity.get("name") or row.get("name") or "Unbekannt"


def _candidate_asset_id(row):
    return row.get("asset_id") or (row.get("identity") or {}).get("asset_id")


def _match_rank(candidates, *, resolved_asset_id=None, resolved_name=None):
    asset = (resolved_asset_id or "").strip()
    name = _norm(resolved_name)
    for index, row in enumerate(candidates[:3], 1):
        if asset and _candidate_asset_id(row) == asset:
            return index, row
    if name:
        for index, row in enumerate(candidates[:3], 1):
            if _norm(_row_name(row)) == name:
                return index, row
    return None, None


def draft_error_analysis(report, *, resolved_name, resolved_asset_id=None):
    """Build German confirmation/error draft from frozen ranking vs. resolution."""
    report = report or {}
    candidates = list(report.get("candidates") or [])[:3]
    resolved = (resolved_name or "").strip() or "Unbekannt"
    if not candidates:
        return (
            f"Keine belastbare Top-Auswahl vorhanden. Auflösung laut Report/Eingabe: {resolved}. "
            "Die Hinweise reichten für eine Unternehmenszuordnung nicht aus."
        )

    top = candidates[0]
    top_name = _row_name(top)
    top_why = why_sentence(top)
    rank, matched = _match_rank(
        candidates, resolved_asset_id=resolved_asset_id, resolved_name=resolved
    )

    if rank == 1:
        return (
            f"Bestätigung: Top-Auswahl {top_name} entspricht der Auflösung {resolved}. "
            f"Analysebegründung: {top_why}"
        )
    if rank is not None and matched is not None:
        matched_why = why_sentence(matched)
        return (
            f"Abweichung: Top-Auswahl war {top_name}, Auflösung ist {resolved} "
            f"(stand auf Rang {rank}). "
            f"Analyse zur Top-Auswahl: {top_why} "
            f"Hinweis zur richtigen Aktie: {matched_why}"
        )
    return (
        f"Abweichung: Top-Auswahl war {top_name}; die Auflösung {resolved} "
        "war nicht unter den Top-3. "
        f"Analyse zur Top-Auswahl: {top_why}"
    )
