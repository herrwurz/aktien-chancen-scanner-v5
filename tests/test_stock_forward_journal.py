from datetime import datetime, timedelta, timezone
from hashlib import sha256

import pytest

from scanner.stock_monitor.journal import Decision, Evidence, append_run


T = datetime(2026, 10, 28, 14, 0, tzinfo=timezone.utc)


def evidence(**changes):
    values = dict(event_id="test-1", symbol="TEST", source_url="https://example.org/filing",
                  source_type="primary", published_at=T, first_seen_at=T + timedelta(minutes=1),
                  retrieved_at=T + timedelta(minutes=2), content_sha256=sha256(b"filing").hexdigest())
    values.update(changes)
    return Evidence(**values)


def test_append_and_duplicate_rejection(tmp_path):
    path = tmp_path / "runs.jsonl"
    kw = dict(path=path, run_id="run-1", cutoff=T + timedelta(minutes=3),
              evidence=[evidence()], decisions=[Decision("test-1", "event_detected", "New filing", "unavailable")],
              code_version="test", coverage="1 source checked; no live quotes")
    assert len(append_run(**kw)) == 64
    with pytest.raises(ValueError, match="Duplicate"):
        append_run(**kw)


def test_future_evidence_rejected(tmp_path):
    with pytest.raises(ValueError, match="unavailable"):
        append_run(tmp_path / "runs.jsonl", run_id="a", cutoff=T,
                   evidence=[evidence()], decisions=[], code_version="test", coverage="partial")


def test_delayed_quote_cannot_be_executable():
    d = Decision("test-1", "paper_entry_eligible", "research only", "delayed",
                 T, 10, 9, 12)
    with pytest.raises(ValueError, match="Executable"):
        d.validate(T)


def test_corrupt_journal_rejected(tmp_path):
    path = tmp_path / "runs.jsonl"
    kwargs = dict(cutoff=T + timedelta(minutes=3), evidence=[evidence()], decisions=[],
                  code_version="test", coverage="partial")
    append_run(path, run_id="a", **kwargs)
    path.write_text(path.read_text().replace("partial", "complete"))
    with pytest.raises(ValueError, match="Corrupted"):
        append_run(path, run_id="b", **kwargs)
