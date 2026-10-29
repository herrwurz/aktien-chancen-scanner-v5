"""Post-ranking case persistence and compact report; labels never enter Investigator."""

from pathlib import Path

from .case_journal import CaseJournal, input_keys


def compact_report(report):
    lines = [
        f"# Teaser: {report.get('headline') or 'Ohne Überschrift'}",
        "",
        f"Fall: {report['case_id']}",
        f"Status: {report['decision']['label']}",
        f"Geprüfte Gegenkandidaten: {report.get('countercandidate_count', 0)}",
        "",
        "## Top-Kandidaten",
        "",
    ]
    for rank, row in enumerate(report.get("candidates", [])[:3], 1):
        identity = row.get("identity", {})
        lines += [
            f"{rank}. {identity.get('name')} "
            f"({identity.get('ticker') or 'Ticker unbestätigt'}) "
            f"– Evidenzscore {row.get('evidence_score')}",
            f"   Begründung: {row.get('ranking_reason', 'Evidenzmatrix prüfen')}",
            f"   Gegenargumente: {'; '.join(row.get('counterarguments', []))}",
            "   Fehlende Hinweise: "
            + (", ".join(row.get("unknown_clues", [])) or "keine ausgewiesen"),
        ]
        for source in row.get("sources", []):
            lines.append(
                f"   Quelle: {source.get('url')} (publiziert {source.get('published_at')}; "
                f"verfügbar {source.get('source_available_at')}; "
                f"abgerufen {source.get('retrieved_at')})"
            )
    lines += ["", "## Offene Belege", ""] + [f"- {item}" for item in report.get("limitations", [])]
    lines += ["", "Evidenzscore ist keine Trefferwahrscheinlichkeit. Keine Kaufempfehlung.", ""]
    return "\n".join(lines)


def run_case(engine, request, *, documents=None, historical_blind=False, register_path=None):
    payload = request.model_dump(mode="json")
    journal = None
    # Strict blind ranking runs before opening any case journal or solution register.
    if historical_blind:
        content_key, source_key = input_keys(payload)
        case_id = "TI-" + (source_key or content_key)[:20]
    else:
        journal = CaseJournal(engine.root / "cases", clock=engine.clock)
        case_id = journal.intake(payload)
        journal.begin(case_id)
    try:
        report = engine.analyze(
            request, documents=documents, historical_blind=historical_blind, case_id=case_id
        )
    except Exception as exc:
        if journal:
            journal.failure(case_id, type(exc).__name__)
        raise
    if journal is None:
        journal = CaseJournal(engine.root / "cases", clock=engine.clock)
        canonical_id = journal.intake(payload)
    else:
        canonical_id = case_id
    journal.record_analysis(canonical_id, Path(report["artifact_directory"]) / "ranking.json")
    report["journal_case_id"] = canonical_id
    report["case_status"] = journal.case(canonical_id)["status"]
    report["journal_integrity"] = journal.verify()
    journal.export_register(engine.root / "case-register.md")
    if register_path:
        journal.export_register(register_path)
    Path(report["artifact_directory"], "report.md").write_text(compact_report(report))
    return report
