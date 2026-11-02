import datetime as dt  # noqa: I001

from scanner.stock_monitor.export import export_runs
from scanner.stock_monitor.sec_replay import replay_sec_snapshot
from scanner.stock_monitor.sec_receipts import record_sha256
from scanner.stock_monitor.worker import SecTarget, run_sec_monitor


def test_replay_restricts_cutoff_and_never_creates_entry(tmp_path):
    payload = {
        "filings": {
            "recent": {
                "accessionNumber": ["0001234567-26-000001", "0001234567-26-000002"],
                "acceptanceDateTime": ["2026-10-27T16:15:00", "2026-10-27T16:30:00"],
                "form": ["8-K", "8-K"],
            }
        }
    }
    record = {
        "payload": payload,
        "retrieved_at": "2026-10-27T20:20:00+00:00",
        "raw_sha256": record_sha256(payload),
    }
    path = tmp_path / "journal.jsonl"
    result = replay_sec_snapshot(
        record=record,
        cik=1234567,
        symbol="XYZ",
        cutoff=dt.datetime(2026, 10, 27, 20, 21, tzinfo=dt.UTC),
        journal_path=path,
        run_id="sec-test",
        code_version="test",
    )
    assert result["event_count"] == 1
    # Second acceptance is after retrieval → chronology reject, not cutoff leak.
    assert result["excluded_after_cutoff"] == 0
    assert result["excluded_chronology"] == 1
    assert result["excluded_outside_lookback"] == 0
    assert result["hash_scope"] == "submissions_response_not_filing_body"
    exported = export_runs(path)
    assert exported["runs"][0]["decisions"][0]["status"] == "event_detected"
    assert exported["runs"][0]["decisions"][0]["quote_kind"] == "unavailable"


def test_live_lookback_blocks_stale_cache_flood(tmp_path):
    """Live monitors must not re-journal the full SEC recent set from cache."""
    forms, times, accs = [], [], []
    for index in range(40):
        forms.append("8-K")
        times.append(f"2025-01-{(index % 28) + 1:02d}T15:00:00")
        accs.append(f"0000000000-25-{index:06d}")
    forms.extend(["8-K", "8-K"])
    times.extend(["2026-11-02T01:00:00", "2026-11-01T20:00:00"])
    accs.extend(["0000000000-26-000001", "0000000000-26-000002"])
    payload = {
        "filings": {"recent": {"form": forms, "acceptanceDateTime": times, "accessionNumber": accs}}
    }
    record = {
        "payload": payload,
        "retrieved_at": "2026-11-02T12:00:00+00:00",
        "raw_sha256": record_sha256(payload),
    }
    cutoff = dt.datetime(2026, 11, 2, 12, tzinfo=dt.UTC)
    historical = replay_sec_snapshot(
        record=record,
        cik=320193,
        symbol="AAPL",
        cutoff=cutoff,
        journal_path=tmp_path / "hist.jsonl",
        run_id="hist",
        code_version="test",
    )
    live = replay_sec_snapshot(
        record=record,
        cik=320193,
        symbol="AAPL",
        cutoff=cutoff,
        journal_path=tmp_path / "live.jsonl",
        run_id="live",
        code_version="test",
        lookback_hours=72,
    )
    assert historical["event_count"] == 42
    assert live["event_count"] == 2
    assert live["excluded_outside_lookback"] == 40

    monitor = run_sec_monitor(
        fetch_submissions=lambda cik: record,
        targets=[SecTarget(320193, "AAPL")],
        journal_path=tmp_path / "monitor.jsonl",
        run_id="live-monitor",
        code_version="test",
        cutoff=cutoff,
        live_mode=True,
    )
    assert monitor["status"] == "complete"
    assert monitor["outcomes"][0]["event_count"] == 2
    assert monitor["outcomes"][0]["recent_event_count"] == 2
