from datetime import UTC, datetime

import httpx
import pytest

from scanner.hebeltrader.eodhd import EodhdClient
from scanner.hebeltrader.eodhd_adapter import prepare_snapshot
from scanner.hebeltrader.market_snapshot import SnapshotStockProvider

CLOCK = datetime(2026, 10, 22, tzinfo=UTC)


def inputs(tmp_path, monkeypatch, actions=False):
    monkeypatch.setenv("EODHD_API_TOKEN", "private-token-value")
    bars = [
        dict(date="2025-01-02", open=10, high=12, low=9, close=11, adjusted_close=3, volume=100)
    ]
    payloads = {
        "eod": bars,
        "splits": [dict(date="2025-01-02", split="2/1")] if actions else [],
        "div": [],
    }
    http = httpx.Client(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(200, json=payloads[r.url.path.split("/")[2]])
        )
    )
    provider = EodhdClient(
        tmp_path / "raw-cache",
        client=http,
        allow_network=True,
        authorize_usage=True,
        max_requests=3,
        now=lambda: CLOCK,
        sleeper=lambda _: None,
    )
    records = {
        endpoint: provider.fetch(endpoint, "ABC.US", start="2024-12-31", end="2025-01-03")[
            "manifest_sha256"
        ]
        for endpoint in payloads
    }
    calendar = tmp_path / "sessions.csv"
    calendar.write_text(
        "timestamp,end_timestamp\n2025-01-02T09:30:00-05:00,2025-01-02T13:00:00-05:00\n"
    )
    spec = dict(
        wkn="AB1234",
        isin="US0378331005",
        symbol="ABC.US",
        venue="XNYS",
        timezone="America/New_York",
        currency="USD",
        identity_reference="synthetic-identity",
        identity_valid_from="2025-01-01T00:00:00+00:00",
        identity_valid_until="2025-01-03T23:59:00+00:00",
        calendar_reference="synthetic historical half-day calendar",
        coverage_start="2025-01-01T00:00:00+00:00",
        coverage_end="2025-01-03T23:59:00+00:00",
    )
    return records, calendar, spec


def test_raw_prices_explicit_half_day_and_offline_compatible_snapshot(tmp_path, monkeypatch):
    records, calendar, spec = inputs(tmp_path, monkeypatch)
    bundle = prepare_snapshot(
        tmp_path / "raw-cache",
        tmp_path / "data",
        records=records,
        spec=spec,
        calendar_path=calendar,
        run_at=CLOCK,
    )
    assert bundle["audit"]["volume_adjustment"] == "split_adjusted_vendor"
    result = SnapshotStockProvider(tmp_path / "data").load(
        bundle["spec"],
        instrument={"wkn": "AB1234", "currency": "USD"},
        available_at=datetime(2025, 1, 1, tzinfo=UTC),
        as_of=datetime(2025, 1, 3, tzinfo=UTC),
    )
    assert not result.issues
    assert str(result.bars[0].close) == "11"
    assert result.bars[0].end_at.hour == 13
    assert not (tmp_path / "data" / "raw-cache").exists()


def test_splits_block_backtesting_until_reconciled(tmp_path, monkeypatch):
    records, calendar, spec = inputs(tmp_path, monkeypatch, actions=True)
    bundle = prepare_snapshot(
        tmp_path / "raw-cache",
        tmp_path / "data",
        records=records,
        spec=spec,
        calendar_path=calendar,
        run_at=CLOCK,
    )
    history = SnapshotStockProvider(tmp_path / "data").load(
        bundle["spec"],
        instrument={"wkn": "AB1234", "currency": "USD"},
        available_at=datetime(2025, 1, 1, tzinfo=UTC),
        as_of=datetime(2025, 1, 3, tzinfo=UTC),
    )
    assert "corporate_action_requires_reconciliation" in history.issues


def test_no_calendar_inference_or_composite_exchange_as_mic(tmp_path, monkeypatch):
    records, calendar, spec = inputs(tmp_path, monkeypatch)
    calendar.write_text("timestamp,end_timestamp\n")
    with pytest.raises(ValueError):
        prepare_snapshot(
            tmp_path / "raw-cache",
            tmp_path / "data",
            records=records,
            spec=spec,
            calendar_path=calendar,
            run_at=CLOCK,
        )
    spec["venue"] = "US"
    with pytest.raises(ValueError):
        prepare_snapshot(
            tmp_path / "raw-cache",
            tmp_path / "data",
            records=records,
            spec=spec,
            calendar_path=calendar,
            run_at=CLOCK,
        )


def test_vendor_provider_rechecks_raw_integrity_and_retains_volume_scope(tmp_path, monkeypatch):
    from scanner.hebeltrader.eodhd import read_record
    from scanner.hebeltrader.eodhd_adapter import EodhdStockProvider

    records, calendar, spec = inputs(tmp_path, monkeypatch)
    bundle = prepare_snapshot(
        tmp_path / "raw-cache",
        tmp_path / "data",
        records=records,
        spec=spec,
        calendar_path=calendar,
        run_at=CLOCK,
    )
    provider = EodhdStockProvider(tmp_path / "data", tmp_path / "raw-cache", [bundle])
    kwargs = dict(
        instrument={"wkn": "AB1234", "currency": "USD"},
        available_at=datetime(2025, 1, 1, tzinfo=UTC),
        as_of=datetime(2025, 1, 3, tzinfo=UTC),
    )
    history = provider.load(bundle["spec"], **kwargs)
    assert not history.issues
    assert history.source["vendor_provenance"]["volume_adjustment"] == "split_adjusted_vendor"
    record = read_record(tmp_path / "raw-cache", records["eod"])
    (tmp_path / "raw-cache" / record["raw_file"]).write_text("[]")
    assert provider.load(bundle["spec"], **kwargs).issues == ["vendor_snapshot_integrity_error"]


def test_wrong_dst_offset_and_future_coverage_are_rejected(tmp_path, monkeypatch):
    records, calendar, spec = inputs(tmp_path, monkeypatch)
    calendar.write_text(
        "timestamp,end_timestamp\n2025-01-02T09:30:00-04:00,2025-01-02T16:00:00-04:00\n"
    )
    with pytest.raises(ValueError):
        prepare_snapshot(
            tmp_path / "raw-cache",
            tmp_path / "data",
            records=records,
            spec=spec,
            calendar_path=calendar,
            run_at=CLOCK,
        )
    spec["coverage_end"] = "2027-01-01T00:00:00+00:00"
    with pytest.raises(ValueError):
        prepare_snapshot(
            tmp_path / "raw-cache",
            tmp_path / "data",
            records=records,
            spec=spec,
            calendar_path=calendar,
            run_at=CLOCK,
        )


def test_delisting_is_a_blocker_without_assumed_exit(tmp_path, monkeypatch):
    records, calendar, spec = inputs(tmp_path, monkeypatch)
    spec["delisted_at"] = "2025-01-02T23:00:00+00:00"
    bundle = prepare_snapshot(
        tmp_path / "raw-cache",
        tmp_path / "data",
        records=records,
        spec=spec,
        calendar_path=calendar,
        run_at=CLOCK,
    )
    result = SnapshotStockProvider(tmp_path / "data").load(
        bundle["spec"],
        instrument={"wkn": "AB1234", "currency": "USD"},
        available_at=datetime(2025, 1, 1, tzinfo=UTC),
        as_of=datetime(2025, 1, 3, tzinfo=UTC),
    )
    assert "delisted_without_exit" in result.issues


def test_normalized_snapshots_are_reproducible_and_cannot_invent_missing_sessions(
    tmp_path, monkeypatch
):
    records, calendar, spec = inputs(tmp_path, monkeypatch)
    calendar.write_text(
        calendar.read_text() + "2025-01-03T09:30:00-05:00,2025-01-03T16:00:00-05:00\n"
    )
    kwargs = dict(records=records, spec=spec, calendar_path=calendar, run_at=CLOCK)
    a = prepare_snapshot(tmp_path / "raw-cache", tmp_path / "data", **kwargs)
    b = prepare_snapshot(tmp_path / "raw-cache", tmp_path / "data", **kwargs)
    assert a == b
    history = SnapshotStockProvider(tmp_path / "data").load(
        a["spec"],
        instrument={"wkn": "AB1234", "currency": "USD"},
        available_at=datetime(2025, 1, 1, tzinfo=UTC),
        as_of=datetime(2025, 1, 4, tzinfo=UTC),
    )
    assert "missing_sessions" in history.issues
