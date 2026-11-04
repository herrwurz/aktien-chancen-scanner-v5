"""Operator-entered post-freeze resolution; separate from teaser input schemas."""

from __future__ import annotations

import re
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


_MATRIX_STATUS = {
    "confirmed": "belegt",
    "contradicted": "widersprochen",
    "unknown": "nicht belegt",
}
_MATRIX_REASON = {
    "eod_price_above_sma200_pit": "Kurs über der 200-Tage-Linie",
    "eod_price_below_sma200_pit": "Kurs unter der 200-Tage-Linie",
    "eod_sma200_reclaim_within_20d_pit": "200-Tage-Linie kürzlich zurückerobert",
    "eod_no_recent_sma200_reclaim_pit": "kein jüngeres Zurückerobern der 200-Tage-Linie",
    "eod_golden_cross_sma_or_ema_within_20d_pit": "Golden Cross im Kursverlauf",
    "eod_golden_cross_sma_within_20d_pit": "Golden Cross der einfachen Durchschnitte",
    "eod_golden_cross_ema_within_20d_pit": "Golden Cross der exponentiellen Durchschnitte",
    "eod_no_recent_golden_cross_pit": "kein jüngeres Golden Cross",
    "unsupported_by_archived_sources": "in den abgerufenen Quellen nicht belegt",
    "no_concrete_evidence": "kein konkreter Beleg",
    "chart_unavailable": "kein Chart verfügbar",
}


def _matrix_lines(row, *, limit=8):
    lines = []
    for cell in list((row or {}).get("evidence_matrix") or [])[:limit]:
        quote = " ".join(str(cell.get("quote") or "").split())
        if not quote:
            continue
        if re.search(r"optionsschein|renditepotenzial", quote, re.I):
            continue
        status = _MATRIX_STATUS.get(cell.get("status") or "", cell.get("status") or "offen")
        reason = _MATRIX_REASON.get(cell.get("reason") or "", "")
        detail = f"{status} ({reason})" if reason else status
        lines.append(f"- „{quote}“: {detail}")
    return lines


def _metric_line(row):
    fingerprint = (row or {}).get("metric_fingerprint") or {}
    bonus = fingerprint.get("bonus") or fingerprint.get("bonus_applied") or 0
    if not bonus:
        return ""
    bits = []
    if fingerprint.get("arr_billions") is not None:
        bits.append(f"jährlich wiederkehrende Erlöse {fingerprint['arr_billions']} Mrd.")
    if fingerprint.get("operating_margin_pct") is not None:
        bits.append(f"operative Marge {fingerprint['operating_margin_pct']} %")
    growth = fingerprint.get("segment_growth") or None
    if isinstance(growth, dict) and growth.get("pct") is not None:
        bits.append(f"Segment {growth.get('segment') or '?'} {growth['pct']} %")
    if not bits:
        return ""
    return (
        "Kennzahlen-Aufschlag aus abgerufenen Texten, nicht aus dem Teaser: "
        + ", ".join(bits)
        + "."
    )


def _find_checked(report, *, resolved_asset_id=None, resolved_name=None):
    rows = list(report.get("checked_candidates") or [])
    asset = (resolved_asset_id or "").strip()
    name = _norm(resolved_name)
    for row in rows:
        if asset and _candidate_asset_id(row) == asset:
            return row
        if name and _norm(_row_name(row)) == name:
            return row
    if name:
        for row in rows:
            row_name = _norm(_row_name(row))
            if name in row_name or row_name in name:
                return row
    return None


def _detail_block(row, heading):
    lines = [heading]
    why = why_sentence(row)
    if why:
        lines.append(why)
    lines.extend(_matrix_lines(row))
    metric = _metric_line(row)
    if metric:
        lines.append(metric)
    return "\n".join(lines)


def draft_error_analysis(report, *, resolved_name, resolved_asset_id=None):
    """Build a German confirmation/error text from the frozen ranking vs. resolution."""
    report = report or {}
    candidates = list(report.get("candidates") or [])[:3]
    resolved = (resolved_name or "").strip()
    if not candidates:
        target = resolved or "Unbekannt"
        return (
            f"Keine belastbare Top-Auswahl vorhanden. Auflösung laut Report/Eingabe: {target}. "
            "Die Hinweise reichten für eine Unternehmenszuordnung nicht aus."
        )

    top = candidates[0]
    top_name = _row_name(top)
    top_why = why_sentence(top)
    if not resolved and not (resolved_asset_id or "").strip():
        return "\n\n".join(
            [
                f"Noch keine Originalauflösung. Top-Auswahl ist {top_name}.",
                f"Analysebegründung: {top_why}",
                _detail_block(top, "Belege der Top-Auswahl:"),
            ]
        )

    resolved = resolved or "Unbekannt"
    rank, matched = _match_rank(
        candidates, resolved_asset_id=resolved_asset_id, resolved_name=resolved
    )
    if rank == 1:
        lead = (
            f"Bestätigung: Top-Auswahl {top_name} entspricht der Auflösung {resolved}. "
            f"Analysebegründung: {top_why}"
        )
        return lead + "\n\n" + _detail_block(top, "Belege der Top-Auswahl:")
    if rank is not None and matched is not None:
        matched_why = why_sentence(matched)
        lead = (
            f"Abweichung: Top-Auswahl war {top_name}, Auflösung ist {resolved} "
            f"(stand auf Rang {rank}). "
            f"Analyse zur Top-Auswahl: {top_why} "
            f"Hinweis zur richtigen Aktie: {matched_why}"
        )
        return "\n\n".join(
            [
                lead,
                _detail_block(top, "Warum die Top-Auswahl vorn lag:"),
                _detail_block(matched, "Belege der Auflösung:"),
            ]
        )
    lead = (
        f"Abweichung: Top-Auswahl war {top_name}; die Auflösung {resolved} "
        "war nicht unter den Top-3. "
        f"Analyse zur Top-Auswahl: {top_why}"
    )
    blocks = [lead, _detail_block(top, "Warum die Top-Auswahl vorn lag:")]
    checked = _find_checked(report, resolved_asset_id=resolved_asset_id, resolved_name=resolved)
    if checked is not None:
        blocks.append(
            f"Die Auflösung {_row_name(checked)} wurde geprüft, aber nicht in die Top-3 übernommen."
        )
        blocks.append(_detail_block(checked, "Belege der geprüften Auflösung:"))
    else:
        blocks.append(
            f"Die Auflösung {resolved} taucht in den geprüften Kandidaten nicht auf. "
            "Der Teaser hat sie mit den vorhandenen Hinweisen nicht in die engere Wahl gebracht."
        )
    return "\n\n".join(blocks)
