from datetime import UTC, datetime
from hashlib import sha256

import pytest

from scanner.stock_monitor.export import export_runs
from scanner.stock_monitor.journal import Decision, Evidence, append_run


def test_export_is_verified_and_limited(tmp_path):
    t = datetime(2026, 10, 28, 14, 0, tzinfo=UTC)
    p = tmp_path / "runs.jsonl"
    event = Evidence(
        "e1", "XYZ", "https://example.org/filing", "primary", t, t, t, sha256(b"filing").hexdigest()
    )
    for i in range(3):
        append_run(
            p,
            run_id=f"r{i}",
            cutoff=t,
            evidence=[event],
            decisions=[Decision("e1", "event_detected", "filing", "unavailable")],
            code_version="test",
            coverage="one issuer",
        )
    result = export_runs(p, limit=2)
    assert result["total_runs"] == 3
    assert len(result["runs"]) == 2
    assert result["runs"][0]["run_id"] == "r1"
    assert result["status"] == "partial"


def test_missing_journal_is_not_success(tmp_path):
    assert export_runs(tmp_path / "missing")["status"] == "unavailable"


def test_corrupt_chain_fails_closed(tmp_path):
    p = tmp_path / "runs.jsonl"
    p.write_text('{"previous_sha256":"bad","payload":"{}","record_sha256":"bad"}\n')
    with pytest.raises(ValueError, match="discontinuity"):
        export_runs(p)
