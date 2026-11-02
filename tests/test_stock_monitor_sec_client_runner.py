"""SEC client runner refuses unapproved network requests."""

import pytest

from scanner.stock_monitor.sec_client_runner import run_with_sec_client


def test_network_requires_explicit_budget(tmp_path):
    with pytest.raises(ValueError, match="positive request budget"):
        run_with_sec_client(
            cache_root=tmp_path / "cache",
            journal_path=tmp_path / "journal.jsonl",
            targets=[],
            run_id="test",
            code_version="test",
            allow_network=True,
            max_requests=0,
        )


def test_offline_missing_cache_is_unavailable(tmp_path):
    from scanner.stock_monitor.worker import SecTarget

    result = run_with_sec_client(
        cache_root=tmp_path / "cache",
        journal_path=tmp_path / "journal.jsonl",
        targets=[SecTarget(1234567, "XYZ")],
        run_id="test",
        code_version="test",
    )
    assert result["status"] == "unavailable"
    assert result["outcomes"][0]["status"] == "unavailable"
    assert result["successful_targets"] == 0


def test_live_cutoff_is_after_fetch_but_historical_cutoff_is_strict(tmp_path):
    from datetime import UTC, datetime, timedelta
    from zoneinfo import ZoneInfo

    from scanner.stock_monitor import worker
    from scanner.stock_monitor.sec_receipts import record_sha256
    from scanner.stock_monitor.worker import SecTarget

    initial = datetime.now(UTC) - timedelta(seconds=30)
    retrieved = datetime.now(UTC) - timedelta(seconds=2)
    # Naive Eastern acceptance inside the live 72h window, but after the
    # historical cutoff so only live_mode journals it.
    accepted_ny = (
        (datetime.now(UTC) - timedelta(hours=1))
        .astimezone(ZoneInfo("America/New_York"))
        .replace(tzinfo=None)
    )
    payload = {
        "filings": {
            "recent": {
                "accessionNumber": ["0001234567-26-000001"],
                "acceptanceDateTime": [accepted_ny.isoformat(timespec="seconds")],
                "form": ["8-K"],
            }
        }
    }
    record = {
        "payload": payload,
        "retrieved_at": retrieved.isoformat(),
        "raw_sha256": record_sha256(payload),
    }
    kwargs = {
        "fetch_submissions": lambda cik: record,
        "targets": [SecTarget(1234567, "XYZ")],
        "code_version": "test",
        "cutoff": initial,
    }
    historic = worker.run_sec_monitor(
        **kwargs, journal_path=tmp_path / "historical.jsonl", run_id="historical"
    )
    live = worker.run_sec_monitor(
        **kwargs, journal_path=tmp_path / "live.jsonl", run_id="live", live_mode=True
    )
    assert historic["outcomes"][0]["event_count"] == 0
    assert historic["outcomes"][0]["excluded_after_cutoff"] == 1
    assert live["outcomes"][0]["event_count"] == 1
    assert live["outcomes"][0]["excluded_after_cutoff"] == 0
    assert live["outcomes"][0]["excluded_outside_lookback"] == 0
