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


def _score(row):
    value = row.get("evidence_score")
    if value is None:
        value = row.get("relevance_score_not_probability")
    return value


def _clue_text(item):
    if item is None:
        return ""
    if isinstance(item, str):
        return item
    return (
        item.get("value") or item.get("normalized") or item.get("clue_id") or item.get("type") or ""
    )


def _confidence_label(row, rank):
    score = _score(row)
    contradictions = row.get("hard_contradictions") or []
    supported = row.get("supporting_clues") or row.get("hard_facts") or []
    if contradictions:
        return "niedrig"
    if score is None:
        return "mittel" if rank == 1 else "niedrig–mittel"
    try:
        score = float(score)
    except (TypeError, ValueError):
        return "mittel"
    if score >= 20 and len(supported) >= 2:
        return "hoch"
    if score >= 10:
        return "mittel–hoch" if rank == 1 else "mittel"
    if score >= 5:
        return "mittel"
    return "niedrig"


def _why(row):
    parts = []
    reason = row.get("ranking_reason")
    if reason:
        parts.append(reason.rstrip("."))
    for key in ("hypothesis_reasons",):
        for item in row.get(key) or []:
            text = _clue_text(item)
            if text:
                parts.append(text.rstrip("."))
    for item in (row.get("supporting_clues") or row.get("hard_facts") or [])[:3]:
        text = _clue_text(item)
        if text:
            parts.append(f"stützt: {text.rstrip('.')}")
    for item in (row.get("hard_contradictions") or [])[:2]:
        text = _clue_text(item)
        if text:
            parts.append(f"Widerspruch: {text.rstrip('.')}")
    for item in (row.get("counterarguments") or [])[:2]:
        text = _clue_text(item)
        if text:
            parts.append(f"Gegenargument: {text.rstrip('.')}")
    unknown = row.get("unknown_clues") or []
    if unknown:
        parts.append(
            "offen: " + ", ".join(_clue_text(item) for item in unknown[:3] if _clue_text(item))
        )
    return "; ".join(parts) if parts else "Noch keine belastbare Primärbegründung."


def prose_briefing(report):
    """Build a chat-style German briefing from an investigation report."""
    report = report or {}
    lines = []
    competition = report.get("competition_mode") or "official"
    if competition == "out_of_competition":
        lines.append(
            "**Außer Konkurrenz** — Analyse zur Orientierung; nicht in Meine Fälle, "
            "Quality oder Blind-Listing."
        )
    else:
        lines.append("**Arbeitsanalyse** — Identifikationshilfe, keine Kaufempfehlung.")

    decision = report.get("decision") or {}
    identification = report.get("identification") or {}
    label = decision.get("label") or identification.get("label") or identification.get("status")
    if label:
        lines.append(f"Status: **{label}**.")
    if report.get("ranking_tie"):
        lines.append("Die führenden Kandidaten liegen gleichauf — derzeit kein eindeutiger Rang 1.")

    candidates = list(report.get("candidates") or [])[:3]
    if not candidates:
        lines.append("")
        lines.append("### Ergebnis")
        lines.append(
            "Keine belastbaren Kandidaten. Die Hinweise reichen für eine belastbare "
            "Unternehmenszuordnung noch nicht aus."
        )
        failure = identification.get("failure_code") or identification.get("reason")
        if failure:
            lines.append(f"Kurzgrund: {failure}.")
    else:
        lines.append("")
        lines.append("### Ranking")
        for rank, row in enumerate(candidates, 1):
            ticker = _ticker(row)
            ticker_bit = f" (`{ticker}`)" if ticker else ""
            score = _score(row)
            score_bit = f", Evidenz {score}" if score is not None else ""
            confidence = _confidence_label(row, rank)
            lines.append(
                f"**{rank}. {_name(row)}**{ticker_bit} — Confidence **{confidence}**{score_bit}."
            )
            lines.append(_why(row) + ".")

        tickers = [t for t in (_ticker(row) for row in candidates) if t]
        names = [_name(row) for row in candidates]
        lines.append("")
        lines.append("### Working hypothesis")
        if tickers:
            lines.append("**`" + "` + `".join(tickers) + "`**.")
        else:
            lines.append("**" + " · ".join(names) + "**.")
        lines.append(
            "Verifiziert erst mit Report, Primärquelle oder unabhängiger Produktprüfung — "
            "nicht als Original-HEBELTRADER-Call behandeln."
        )

    limits = [item for item in (report.get("limitations") or []) if isinstance(item, str)][:4]
    if limits:
        lines.append("")
        lines.append("### Offene Punkte")
        for item in limits:
            lines.append(f"- {item}")

    lines.append("")
    lines.append(
        "Evidenzscore ist keine Trefferwahrscheinlichkeit. Keine Anlage- oder Kaufempfehlung."
    )
    return "\n".join(lines).strip() + "\n"


def call_search_prose(payload):
    """Chat-style prose for a call-search dry-run result."""
    payload = payload or {}
    lines = [
        "**Call-Suche / Dry-Run** — keine Liste, keine Kaufempfehlung, kein bestätigter "
        "Original-Call.",
        "",
        "HT-Muster (empirisch): klassischer Call, ~4–6 Monate, Omega ~8–13, "
        "Ask oft ~0,16–0,48 €, moderat OTM.",
    ]
    status = payload.get("status")
    if status == "abstain":
        lines.append("")
        lines.append(f"Gesamtstatus: **abstain** ({payload.get('reason') or 'keine Treffer'}).")
    elif status in ("dry_run_ranked", "manual_review_required", "partial"):
        lines.append("")
        lines.append(f"Gesamtstatus: **{status}**.")

    for block in payload.get("underlyings") or []:
        name = block.get("name") or "Unbekannt"
        ticker = block.get("ticker")
        head = f"**{name}**" + (f" (`{ticker}`)" if ticker else "")
        lines.append("")
        lines.append(f"### {head}")
        lines.append(f"Ergebnis: **{block.get('status') or 'abstain'}**.")
        if block.get("summary"):
            lines.append(block["summary"])
        proposals = block.get("proposals") or []
        if not proposals:
            lines.append(
                "Kein klassischer Call im HT-Band gefunden bzw. nur Turbos/KOs — "
                "Scorer verwirft non_classic_call."
            )
            continue
        for index, row in enumerate(proposals[:3], 1):
            metrics = row.get("metrics") or {}
            bits = [
                f"WKN **{row.get('wkn') or 'unbekannt'}**",
                row.get("issuer") or None,
                f"Strike {row['strike']}" if row.get("strike") is not None else None,
                f"Fälligkeit {row['maturity']}" if row.get("maturity") else None,
                f"Omega {metrics['omega']}" if metrics.get("omega") is not None else None,
                f"~{metrics['months']} Mo" if metrics.get("months") is not None else None,
                f"{metrics['warrant_px_eur']} €"
                if metrics.get("warrant_px_eur") is not None
                else None,
                f"Score {row.get('score')}" if row.get("score") is not None else None,
            ]
            lines.append(f"{index}. " + " · ".join(bit for bit in bits if bit))
            notes = row.get("notes") or []
            if notes:
                lines.append("   Hinweise: " + ", ".join(notes[:6]))

    lines.append("")
    lines.append(
        "Fazit: Nur manuelle Prüfung; AT-Handelbarkeit, Spread und Emittentenbedingungen "
        "bleiben Pflicht. Kein automatischer Original-Call."
    )
    return "\n".join(lines).strip() + "\n"
