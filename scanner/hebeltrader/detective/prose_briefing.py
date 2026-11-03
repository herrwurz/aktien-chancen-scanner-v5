"""Readable German prose briefings for operator UI (chat-style, not raw JSON dump)."""

from __future__ import annotations


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
    return str(
        item.get("value") or item.get("normalized") or item.get("quote") or item.get("text") or ""
    ).strip()


def _is_noise(text):
    if not text:
        return True
    lowered = text.casefold()
    noisy = (
        "unknown",
        "unbekannt",
        "n/a",
        "none",
        "null",
        "failure_code",
        "clue_id",
        "asset_id",
        "status=",
    )
    return any(token in lowered for token in noisy) or len(text) < 3


def _clean_sentences(parts):
    seen = set()
    out = []
    for part in parts:
        text = " ".join(str(part or "").split()).strip(" .;")
        if not text or _is_noise(text):
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


def _why(row):
    """Human-facing why-text: ranking reason + a few supporting facts, no unknown dump."""
    parts = []
    reason = row.get("ranking_reason")
    if reason:
        parts.append(reason)
    for item in row.get("hypothesis_reasons") or []:
        text = _clue_text(item) if not isinstance(item, str) else item
        parts.append(text)
    for item in (row.get("supporting_clues") or row.get("hard_facts") or [])[:4]:
        text = _clue_text(item)
        if text:
            parts.append(text)
    cleaned = _clean_sentences(parts)
    if cleaned:
        return cleaned[0] + (
            (". " + ". ".join(cleaned[1:3]) + ".") if len(cleaned) > 1 else "."
        )
    contradictions = _clean_sentences(
        _clue_text(item) for item in (row.get("hard_contradictions") or [])[:2]
    )
    if contradictions:
        return "Gegen die Auswahl sprechen: " + "; ".join(contradictions) + "."
    return "Die Hinweise deuten auf dieses Unternehmen, ohne eine einzelne klare Primärbegründung."


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
            "Einschätzung: Top-3-Hypothese zur manuellen Prüfung — "
            "keine bestätigte Identifikation."
        )
    return (
        "Einschätzung: Arbeitsergebnis zur Orientierung, keine bestätigte Identifikation."
    )


def _readable_limits(report):
    limits = []
    for item in report.get("limitations") or []:
        if not isinstance(item, str):
            continue
        text = " ".join(item.split()).strip()
        if _is_noise(text):
            continue
        # Skip internal machine codes / enum dumps.
        if text.isupper() or "_" in text and " " not in text:
            continue
        limits.append(text)
    return limits[:3]


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
        "Keine Anlage- oder Kaufempfehlung. "
        "Bestätigung nur über Originalreport oder Primärquelle."
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
        lines.append(
            f"Kein passender Call gefunden ({payload.get('reason') or 'keine Treffer'})."
        )
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
    lines.append(
        "Nur manuelle Prüfung; Handelbarkeit und Emittentenbedingungen bleiben Pflicht."
    )
    return "\n".join(lines).strip() + "\n"
