import datetime as dt  # noqa: I001

from scanner.stock_monitor.export import export_runs
from scanner.stock_monitor.sec_replay import replay_sec_snapshot
from scanner.stock_monitor.sec_receipts import record_sha256


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
    assert result["excluded_after_cutoff"] == 1
    exported = export_runs(path)
    assert exported["runs"][0]["decisions"][0]["status"] == "event_detected"
    assert exported["runs"][0]["decisions"][0]["quote_kind"] == "unavailable"
