"""Cross-asset run journal integrity and replay tests."""

import pytest

from scanner.stock_monitor.cross_asset_journal import append_cross_asset_run, read_run_journal


def _run(run_id):
    return {
        "run_id": run_id,
        "started_at": "2026-11-01T12:00:00+00:00",
        "completed_at": "2026-11-01T12:01:00+00:00",
        "results": {
            "stock": {"status": "complete"},
            "crypto": {"status": "unavailable", "reason": "feed_missing"},
        },
    }


def test_round_trip_and_duplicate_protection(tmp_path):
    path = tmp_path / "runs.jsonl"
    append_cross_asset_run(path, _run("first"))
    append_cross_asset_run(path, _run("second"))
    assert [item["run_id"] for item in read_run_journal(path)] == ["first", "second"]
    with pytest.raises(ValueError, match="Duplicate"):
        append_cross_asset_run(path, _run("first"))


def test_tampering_is_rejected(tmp_path):
    path = tmp_path / "runs.jsonl"
    append_cross_asset_run(path, _run("first"))
    path.write_text(path.read_text().replace("feed_missing", "feed_present"))
    with pytest.raises(ValueError, match="checksum"):
        read_run_journal(path)


def test_both_asset_results_required(tmp_path):
    path = tmp_path / "runs.jsonl"
    run = _run("first")
    del run["results"]["crypto"]
    with pytest.raises(ValueError, match="Both asset"):
        append_cross_asset_run(path, run)
