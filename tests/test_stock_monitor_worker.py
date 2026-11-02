"""Bounded SEC monitor worker tests."""

from datetime import UTC, datetime  # noqa: I001

from scanner.stock_monitor.worker import SecTarget, run_sec_monitor


CUTOFF = datetime(2026, 10, 27, 21, 0, tzinfo=UTC)


def test_dry_run_does_not_create_journal(tmp_path):
    path = tmp_path / "journal.jsonl"
    result = run_sec_monitor(
        fetch_submissions=lambda cik: {"status": "dry_run"},
        targets=[SecTarget(1234567, "XYZ")],
        journal_path=path,
        run_id="dry-run",
        code_version="test",
        cutoff=CUTOFF,
    )
    assert result["status"] == "partial"
    assert result["successful_targets"] == 0
    assert not path.exists()


def test_budget_enforced_before_fetch(tmp_path):
    calls = []

    def fetch(cik):
        calls.append(cik)
        return {"status": "dry_run"}

    try:
        run_sec_monitor(
            fetch_submissions=fetch,
            targets=[SecTarget(1, "A"), SecTarget(2, "B")],
            journal_path=tmp_path / "journal.jsonl",
            run_id="budget",
            code_version="test",
            cutoff=CUTOFF,
            max_targets=1,
        )
    except ValueError as exc:
        assert "budget" in str(exc)
    else:
        raise AssertionError("Expected budget failure")
    assert not calls


def test_failed_fetch_does_not_claim_coverage(tmp_path):
    def unavailable(cik):
        raise ValueError("SEC cache miss")

    result = run_sec_monitor(
        fetch_submissions=unavailable,
        targets=[SecTarget(1234567, "XYZ")],
        journal_path=tmp_path / "journal.jsonl",
        run_id="missing",
        code_version="test",
        cutoff=CUTOFF,
    )
    assert result["status"] == "unavailable"
    assert result["outcomes"][0]["status"] == "unavailable"
    assert result["successful_targets"] == 0
