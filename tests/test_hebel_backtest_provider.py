from datetime import datetime

import pytest

from scanner.hebeltrader.backtest_provider import CsvStockProvider


def dt(value):
    return datetime.fromisoformat(value)


@pytest.fixture
def history(tmp_path):
    (tmp_path / "bars.csv").write_text(
        "timestamp,end_timestamp,open,high,low,close,volume\n2026-01-05T09:00:00+01:00,2026-01-05T17:30:00+01:00,10,12,9,11,100\n"
    )
    (tmp_path / "calendar.csv").write_text(
        "timestamp,end_timestamp\n2026-01-05T09:00:00+01:00,2026-01-05T17:30:00+01:00\n"
    )
    (tmp_path / "actions.csv").write_text("timestamp,type\n")
    spec = dict(
        file="bars.csv",
        identity_reference="historical exchange security master",
        identity_valid_from="2025-01-01T00:00:00+00:00",
        identity_valid_until="2027-01-01T00:00:00+00:00",
        wkn="ABC123",
        symbol="TEST",
        venue="XETR",
        timezone="Europe/Berlin",
        currency="EUR",
        adjustment="raw",
        source_reference="vendor export 1",
        license="internal",
        retrieved_at="2026-01-06T00:00:00+00:00",
        calendar_file="calendar.csv",
        calendar_reference="exchange calendar",
        corporate_actions_file="actions.csv",
        corporate_actions_reference="vendor actions",
        coverage_start="2026-01-01T00:00:00+00:00",
        coverage_end="2026-01-06T00:00:00+00:00",
    )

    def load():
        return CsvStockProvider(tmp_path).load(
            spec,
            instrument={"wkn": "ABC123", "currency": "EUR"},
            available_at=dt("2026-01-02T00:00:00+00:00"),
            as_of=dt("2026-01-05T20:00:00+00:00"),
        )

    return tmp_path, spec, load


def test_explicit_calendar_allows_holiday_gap_and_hashes(history):
    _, _, load = history
    result = load()
    assert result.issues == []
    assert len(result.bars) == 1
    assert len(result.source["sha256"]["file"]) == 64


@pytest.mark.parametrize(
    ("key", "value", "issue"),
    [
        ("currency", "USD", "currency_mismatch"),
        ("adjustment", "split", "corporate_action_requires_reconciliation"),
        ("wkn", "WRONG", "instrument_mismatch"),
        ("license", "", "missing_metadata"),
        ("file", "../escape.csv", "data_unavailable"),
    ],
)
def test_fail_closed_metadata(history, key, value, issue):
    _, spec, load = history
    spec[key] = value
    assert issue in load().issues


def test_missing_expected_session(history):
    root, _, load = history
    (root / "calendar.csv").write_text(
        (root / "calendar.csv").read_text()
        + "2026-01-02T09:00:00+01:00,2026-01-02T17:30:00+01:00\n"
    )
    assert "missing_sessions" in load().issues


def test_split_requires_reconciliation(history):
    root, _, load = history
    (root / "actions.csv").write_text("timestamp,type\n2026-01-05T12:00:00+01:00,split\n")
    assert "corporate_action_requires_reconciliation" in load().issues


def test_nonfinite_prices(history):
    root, _, load = history
    path = root / "bars.csv"
    path.write_text(path.read_text().replace(",12,", ",NaN,"))
    assert "invalid_ohlc" in load().issues


def test_future_invalid_prices_and_actions_do_not_leak(history):
    root, _, load = history
    path = root / "bars.csv"
    path.write_text(
        path.read_text()
        + "2026-01-06T09:00:00+01:00,2026-01-06T17:30:00+01:00,NaN,NaN,NaN,NaN,bad\n"
    )
    (root / "actions.csv").write_text("timestamp,type\n2026-01-06T12:00:00+01:00,split\n")
    assert load().issues == []


def test_symlink_escape(history, tmp_path_factory):
    root, spec, load = history
    outside = tmp_path_factory.mktemp("outside") / "bars.csv"
    outside.write_text("secret")
    (root / "link.csv").symlink_to(outside)
    spec["file"] = "link.csv"
    assert "data_unavailable" in load().issues


@pytest.mark.parametrize(
    "replacement",
    [
        "2026-01-05T09:00:00+01:00,2026-01-05T16:30:00+01:00,10,12,9,11,100\n",
        "2026-01-05T09:00:00+00:00,2026-01-05T17:30:00+00:00,10,12,9,11,100\n",
    ],
)
def test_close_must_match_calendar_and_offset(history, replacement):
    root, _, load = history
    (root / "bars.csv").write_text(
        "timestamp,end_timestamp,open,high,low,close,volume\n" + replacement
    )
    assert load().issues


def test_duplicate_bar_fails(history):
    root, _, load = history
    path = root / "bars.csv"
    text = path.read_text()
    path.write_text(text + text.splitlines(keepends=True)[1])
    assert "invalid_ohlc" in load().issues


@pytest.mark.parametrize("field", ["calendar_file", "corporate_actions_file", "file"])
def test_missing_files_fail_closed(history, field):
    _, spec, load = history
    spec[field] = "absent.csv"
    assert load().issues


def test_coverage_bounds_and_delisting(history):
    _, spec, load = history
    spec["coverage_end"] = "2026-01-03T00:00:00+00:00"
    spec["delisted_at"] = "2026-01-05T18:00:00+00:00"
    assert {"stale_metadata", "delisted_without_exit"} <= set(load().issues)


def test_naive_manifest_timestamp_fails_closed(history):
    _, spec, load = history
    spec["retrieved_at"] = "2026-01-06T00:00:00"
    assert "missing_metadata" in load().issues


def test_corporate_action_before_entry_invalidates_published_targets(history):
    root, _, load = history
    (root / "actions.csv").write_text("timestamp,type\n2026-01-05T08:00:00+01:00,split\n")
    assert "corporate_action_requires_reconciliation" in load().issues


def test_source_does_not_echo_unapproved_manifest_fields(history):
    _, spec, load = history
    spec["archive_category"] = "winning-picks"
    assert "archive_category" not in load().source


def test_only_one_matching_identity_required(history):
    root, spec, _ = history
    result = CsvStockProvider(root).load(
        spec,
        instrument={"wkn": "ABC123", "isin": "DE000ABC1234", "currency": "EUR"},
        available_at=dt("2026-01-02T00:00:00+00:00"),
        as_of=dt("2026-01-05T20:00:00+00:00"),
    )
    assert result.issues == []


def test_conflicting_provided_counterpart_fails(history):
    _, spec, load = history
    spec["instrument_wkn"] = "WRONG"
    assert "instrument_mismatch" in load().issues


def test_retrieval_cannot_precede_evaluation_horizon(history):
    _, spec, load = history
    spec["retrieved_at"] = "2026-01-04T00:00:00+00:00"
    assert "stale_metadata" in load().issues


def anchored_load(history, **updates):
    root, spec, _ = history
    instrument = {
        "wkn": "ABC123",
        "currency": "EUR",
        "levels_as_of": dt("2026-01-01T00:00:00+00:00"),
    }
    instrument.update(updates)
    return CsvStockProvider(root).load(
        spec,
        instrument=instrument,
        available_at=dt("2026-01-02T00:00:00+00:00"),
        as_of=dt("2026-01-05T20:00:00+00:00"),
    )


def test_split_before_availability_invalidates_original_levels(history):
    root, _, _ = history
    (root / "actions.csv").write_text("timestamp,type\n2026-01-01T12:00:00+01:00,split\n")
    assert "corporate_action_requires_reconciliation" in anchored_load(history).issues


def test_coverage_must_include_level_baseline(history):
    _, spec, _ = history
    spec["coverage_start"] = "2026-01-01T12:00:00+00:00"
    assert "stale_metadata" in anchored_load(history).issues


@pytest.mark.parametrize(
    "field", ["identity_reference", "identity_valid_from", "identity_valid_until"]
)
def test_mapping_provenance_required(history, field):
    _, spec, load = history
    spec.pop(field, None)
    assert "missing_metadata" in load().issues


def test_mapping_validity_must_span_evaluation(history):
    _, spec, load = history
    spec["identity_valid_until"] = "2026-01-04T00:00:00+00:00"
    assert "instrument_mismatch" in load().issues
