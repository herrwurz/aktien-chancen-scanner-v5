"""Journal-based quality audit tests."""

from datetime import UTC, datetime

from scanner.stock_monitor.journal import Decision, Evidence, append_run
from scanner.stock_monitor.journal_quality import audit_stock_journal


def test_journal_receipt_is_pending_not_alert(tmp_path):
    path = tmp_path / "journal.jsonl"
    instant = datetime(2026, 11, 1, 12, tzinfo=UTC)
    evidence = Evidence(
        "sec:1",
        "ABC",
        "https://www.sec.gov/test",
        "primary",
        instant,
        instant,
        instant,
        "a" * 64,
    )
    append_run(
        path,
        run_id="first",
        cutoff=instant,
        evidence=[evidence],
        decisions=[Decision("sec:1", "event_detected", "SEC receipt", "unavailable")],
        code_version="test",
        coverage="offline test",
    )
    result = audit_stock_journal(path)
    assert result["distinct_decided_events"] == 1
    assert result["quality"]["outcomes"]["pending"] == 1
    assert result["quality"]["outcomes"]["alerted"] == 0
    assert result["quality"]["recall"] is None


def test_missing_journal_does_not_claim_no_signals(tmp_path):
    result = audit_stock_journal(tmp_path / "missing.jsonl")
    assert result["status"] == "unavailable"
    assert result["quality"]["total"] == 0
