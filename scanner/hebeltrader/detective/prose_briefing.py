"""Readable German prose briefings for operator UI (chat-style, not raw JSON dump)."""

from __future__ import annotations

import re

_HASH_RE = re.compile(r"\b(?:ai:)?[a-f0-9]{16,}\b", re.I)
_TECH_MARKERS = (
    "offen:",
    "score ",
    "evidenz",
    "confidence",
    "rang 1:",
    "rang 2:",
    "rang 3:",
    "kernhinweise",
    "ki-beleg",
    "working hypothesis",
    "usable_for_ranking",
    "failure_code",
    "clue_id",
    "asset_id",
)

_LIMIT_LABELS = {
    "ai_interpretation_requires_manual_verification": (
        "KI-Interpretation der Quellen muss manuell geprüft werden."
    ),
    "fewer_than_five_countercandidates": "Es wurden nur wenige Gegenkandidaten geprüft.",
    "insufficient_specific_primary_evidence": (
        "Es fehlen noch spezifische Primärbelege für eine sichere Zuordnung."
    ),
    "listed_underlying_identity_unverified": (
        "Börsennotierung bzw. Unternehmensidentität ist noch nicht unabhängig verifiziert."
    ),
    "insufficient_evidence": (
        "Die vorliegenden Hinweise reichen für eine sichere Identifikation nicht aus."
    ),
}


def _identity(row):
    return row.get("identity") or {}


def _name(row):
    identity = _identity(row)
    return identity.get("name") or row.get("name") or "Unbekannt"


def _ticker(row):
    identity = _identity(row)
    return identity.get("ticker") or row.get("ticker")


def _clue_text(item):
    if item is None:
        return ""
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, dict):
        return str(
            item.get("value")
            or item.get("normalized")
            or item.get("quote")
            or item.get("text")
            or item.get("label")
            or ""
        ).strip()
    return str(item).strip()


def _is_noise(text):
    if not text:
        return True
    cleaned = " ".join(str(text).split()).strip()
    if len(cleaned) < 4:
        return True
    if _HASH_RE.search(cleaned):
        return True
    lowered = cleaned.casefold()
    if any(marker in lowered for marker in _TECH_MARKERS):
        return True
    if cleaned.isupper() and "_" in cleaned:
        return True
    if re.fullmatch(r"[a-z0-9_]+", lowered) and "_" in lowered:
        return True
    noisy = ("unknown", "unbekannt", "n/a", "none", "null", "status=")
    return any(token in lowered for token in noisy)


_PREFIX_RE = re.compile(
    r"^(gegenargument|widerspruch|stützt|offen)\s*:\s*",
    re.I,
)


def _normalize_piece(piece):
    piece = " ".join(str(piece or "").split()).strip(" .;")
    piece = _PREFIX_RE.sub("", piece).strip(" .;")
    if piece:
        piece = piece[0].upper() + piece[1:]
    return piece


def _human_segments(text):
    """Split machine ranking text into human-usable fragments."""
    if not text:
        return []
    parts = re.split(r"[;|]\s*|\.\s+", str(text))
    out = []
    for part in parts:
        piece = _normalize_piece(part)
        if _is_noise(piece):
            continue
        # Drop pure count boilerplate.
        if re.match(r"^\d+\s+\w+", piece) and any(
            token in piece.casefold() for token in ("hinweis", "widerspruch", "beleg", "score")
        ):
            continue
        out.append(piece)
    return out


def _clean_sentences(parts):
    seen = set()
    out = []
    for part in parts:
        for piece in _human_segments(part):
            key = piece.casefold()
            if key in seen:
                continue
            seen.add(key)
            out.append(piece)
    return out


_MACHINE_REASON_RE = re.compile(
    r"^(confirmed|category|retrieval_score|uncertainty|clue_id|asset_id):",
    re.I,
)


def why_sentence(row):
    """Human-facing why-text without hashes, scores or internal codes."""
    parts = []
    for item in row.get("confirmed_specific_clues") or []:
        parts.append(_clue_text(item))
    for item in row.get("supporting_clues") or row.get("hard_facts") or []:
        parts.append(_clue_text(item))
    for item in row.get("hypothesis_reasons") or []:
        text = _clue_text(item) if not isinstance(item, str) else item
        if text and not _MACHINE_REASON_RE.match(text.strip()):
            parts.append(text)
    for item in row.get("counterarguments") or []:
        text = _clue_text(item) if not isinstance(item, str) else item
        if text and not _is_noise(text):
            parts.append(text)
    for finding in row.get("cited_findings") or []:
        if not isinstance(finding, dict):
            continue
        if finding.get("status") == "supported" or finding.get("usable_for_ranking"):
            parts.append(_clue_text(finding))
            quote = finding.get("quote") or finding.get("snippet")
            if quote:
                parts.append(quote)
    # ranking_reason only after stripping technical boilerplate.
    parts.extend(_human_segments(row.get("ranking_reason") or ""))

    cleaned = _clean_sentences(parts)
    if cleaned:
        lead = cleaned[0]
        extra = cleaned[1:3]
        if extra:
            return lead.rstrip(".") + ". " + ". ".join(extra) + "."
        return lead.rstrip(".") + "."

    confirmed = len(row.get("confirmed_specific_clues") or [])
    contradictions = len(row.get("hard_contradictions") or [])
    cited = len(row.get("cited_findings") or [])
    if confirmed:
        return f"Es liegen {confirmed} bestätigte Kernhinweise vor" + (
            f"; {contradictions} harte Widersprüche sind vermerkt." if contradictions else "."
        )
    if cited and not contradictions:
        return (
            "Die Rangfolge stützt sich vor allem auf vorläufige Quellenhinweise — "
            "ohne unabhängige Primärbestätigung."
        )
    if contradictions:
        return "Es gibt vermerkte Widersprüche; die Zuordnung bleibt unsicher."
    return (
        "Die Hinweise deuten vergleichsweise auf dieses Unternehmen, "
        "ohne eine einzelne klare Primärbegründung."
    )


def _why(row):
    return why_sentence(row)


def _status_sentence(report):
    decision = report.get("decision") or {}
    identification = report.get("identification") or {}
    label = decision.get("label") or identification.get("label")
    status = identification.get("status") or ""
    if label and not _is_noise(str(label)):
        return f"Einschätzung: **{label}**."
    if status == "identified":
        return "Einschätzung: belastbarer Top-Kandidat, manuelle Bestätigung bleibt nötig."
    if status == "hypothesis_top3":
        return (
            "Einschätzung: Top-3-Hypothese zur manuellen Prüfung — keine bestätigte Identifikation."
        )
    return "Einschätzung: Arbeitsergebnis zur Orientierung, keine bestätigte Identifikation."


def _readable_limits(report):
    limits = []
    seen = set()
    for item in report.get("limitations") or []:
        if not isinstance(item, str):
            continue
        raw = " ".join(item.split()).strip()
        label = _LIMIT_LABELS.get(raw, raw)
        if _is_noise(label) and raw not in _LIMIT_LABELS:
            continue
        if raw not in _LIMIT_LABELS and (raw.isupper() or ("_" in raw and " " not in raw)):
            continue
        key = label.casefold()
        if key in seen:
            continue
        seen.add(key)
        limits.append(label)
    return limits[:4]


def prose_briefing(report):
    """Build a reader-facing German briefing: top pick, why, short runner-ups."""
    report = report or {}
    lines = []
    competition = report.get("competition_mode") or "official"
    if competition == "out_of_competition":
        lines.append(
            "**Außer Konkurrenz** — Analyse zur Orientierung; nicht im offiziellen Listing."
        )
    else:
        lines.append("**Arbeitsanalyse** — Identifikationshilfe, keine Kaufempfehlung.")

    lines.append(_status_sentence(report))
    if report.get("ranking_tie"):
        lines.append(
            "Die führenden Kandidaten liegen eng beieinander — derzeit kein eindeutiger Favorit."
        )

    candidates = list(report.get("candidates") or [])[:3]
    if not candidates:
        lines.append("")
        lines.append("### Ergebnis")
        lines.append(
            "Es konnten keine belastbaren Unternehmens-Kandidaten "
            "aus den Hinweisen abgeleitet werden."
        )
    else:
        top = candidates[0]
        ticker = _ticker(top)
        ticker_bit = f" ({ticker})" if ticker else ""
        lines.append("")
        lines.append("### Top-Auswahl")
        lines.append(f"**{_name(top)}**{ticker_bit}")
        lines.append(_why(top))

        if len(candidates) > 1:
            lines.append("")
            lines.append("### Weitere geprüfte Kandidaten")
            for rank, row in enumerate(candidates[1:], 2):
                ticker = _ticker(row)
                ticker_bit = f" ({ticker})" if ticker else ""
                lines.append(f"**{rank}. {_name(row)}**{ticker_bit}")
                lines.append(_why(row))

        checked = report.get("checked_candidates") or []
        extra = max(0, len(checked) - len(candidates)) if checked else 0
        if extra:
            lines.append("")
            lines.append(
                f"Zusätzlich wurden **{extra}** weitere Unternehmen geprüft und verworfen "
                "(Details im technischen Anhang)."
            )

    limits = _readable_limits(report)
    if limits:
        lines.append("")
        lines.append("### Bitte noch prüfen")
        for item in limits:
            lines.append(f"- {item}")

    lines.append("")
    lines.append(
        "Keine Anlage- oder Kaufempfehlung. Bestätigung nur über Originalreport oder Primärquelle."
    )
    return "\n".join(lines).strip() + "\n"


def call_search_prose(payload):
    """Chat-style prose for a call-search dry-run result."""
    payload = payload or {}
    lines = [
        "**Call-Suche** — Dry-Run nach dem üblichen HEBELTRADER-Muster, keine Kaufempfehlung.",
        "",
        "Typisches Muster: klassischer Call, Laufzeit etwa 4–6 Monate, moderat aus dem Geld.",
    ]
    status = payload.get("status")
    if status == "abstain":
        lines.append("")
        lines.append(f"Kein passender Call gefunden ({payload.get('reason') or 'keine Treffer'}).")
    elif status:
        lines.append("")
        lines.append(f"Status: **{status}**.")

    for block in payload.get("underlyings") or []:
        name = block.get("name") or "Unbekannt"
        ticker = block.get("ticker")
        head = f"**{name}**" + (f" ({ticker})" if ticker else "")
        lines.append("")
        lines.append(f"### {head}")
        if block.get("summary") and not _is_noise(block["summary"]):
            lines.append(block["summary"])
        proposals = block.get("proposals") or []
        if not proposals:
            lines.append("Kein klassischer Call im erwarteten Band gefunden.")
            continue
        for index, row in enumerate(proposals[:3], 1):
            metrics = row.get("metrics") or {}
            bits = [
                f"WKN **{row.get('wkn') or '–'}**",
                row.get("issuer") or None,
                f"Strike {row['strike']}" if row.get("strike") is not None else None,
                f"Fälligkeit {row['maturity']}" if row.get("maturity") else None,
                f"Hebel ~{metrics['omega']}" if metrics.get("omega") is not None else None,
                f"{metrics['warrant_px_eur']} €"
                if metrics.get("warrant_px_eur") is not None
                else None,
            ]
            lines.append(f"{index}. " + " · ".join(bit for bit in bits if bit))

    lines.append("")
    lines.append("Nur manuelle Prüfung; Handelbarkeit und Emittentenbedingungen bleiben Pflicht.")
    return "\n".join(lines).strip() + "\n"
