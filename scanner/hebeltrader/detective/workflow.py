"""Post-ranking case persistence and compact report; labels never enter Investigator."""

from pathlib import Path

from .case_journal import CaseJournal, input_keys
from .prose_briefing import prose_briefing


def compact_report(report):
    """Prefer chat-style prose; keep a short machine appendix for artifacts."""
    prose = report.get("prose") or prose_briefing(report)
    appendix = [
        "",
        "---",
        f"Fall: {report.get('case_id')}",
        f"Status: {(report.get('decision') or {}).get('label')}",
        f"Geprüfte Gegenkandidaten: {report.get('countercandidate_count', 0)}",
        "",
    ]
    return prose.rstrip() + "\n" + "\n".join(appendix)


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
    case_state = journal.case(canonical_id)
    report["journal_case_id"] = canonical_id
    report["case_status"] = case_state["status"]
    report["competition_mode"] = case_state.get("competition_mode") or "official"
    report["prose"] = prose_briefing(report)
    report["journal_integrity"] = journal.verify()
    journal.export_register(engine.root / "case-register.md")
    if register_path:
        journal.export_register(register_path)
    Path(report["artifact_directory"], "report.md").write_text(compact_report(report))
    return report
