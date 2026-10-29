from datetime import UTC, datetime
from pathlib import Path

from scanner.hebeltrader.detective.case_journal import CaseJournal
from scanner.hebeltrader.detective.investigation import InvestigationRequest, Investigator
from scanner.hebeltrader.detective.workflow import run_case


def test_input_metadata_case_lifecycle_and_compact_report(tmp_path):
    request = InvestigationRequest(
        teaser_text="Unbekannter Konzern mit Chancen.",
        author="Rudolf Wittmer",
        issue="201/26",
        headline="Unbekannt",
        publication_at=datetime(2026, 10, 28, 12, tzinfo=UTC),
    )
    report = run_case(Investigator(tmp_path), request, documents=[])
    case = CaseJournal(tmp_path / "cases").case(report["case_id"])
    assert case["input"]["author"] == "Rudolf Wittmer"
    assert case["input"]["issue"] == "201/26"
    assert case["first_prediction"]["case_id"] == report["case_id"]
    assert case["status"] == "ungeloest"
    assert Path(report["artifact_directory"], "report.md").exists()
    assert (tmp_path / "case-register.md").exists()
    assert (
        "Nicht ausreichend identifizierbar"
        in Path(report["artifact_directory"], "report.md").read_text()
    )


def test_strict_blind_ranking_freezes_before_opening_journal_or_register(tmp_path, monkeypatch):
    from scanner.hebeltrader.detective import history, workflow

    frozen = []
    original = history.freeze_analysis

    def freeze(report, path):
        result = original(report, path)
        frozen.append(True)
        return result

    monkeypatch.setattr(history, "freeze_analysis", freeze)
    actual = workflow.CaseJournal

    class GuardedJournal(actual):
        def __init__(self, *args, **kwargs):
            assert frozen, "Case/solution journal opened before blind ranking frozen"
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(workflow, "CaseJournal", GuardedJournal)
    request = InvestigationRequest(
        teaser_text="Unbekannter Titel ohne konkrete Unternehmenshinweise",
        publication_at=datetime(2026, 10, 28, 12, tzinfo=UTC),
    )
    report = run_case(Investigator(tmp_path), request, documents=[], historical_blind=True)
    assert report["journal_case_id"] == report["case_id"]
