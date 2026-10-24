import sqlite3
from datetime import UTC, datetime

import pytest

from scanner.market_data.models import InstrumentListing
from scanner.market_data.providers import normalize_tiingo


def batch(*, close=105, retrieved_at="2025-01-06T12:00:00+00:00", mic="XNAS"):
    listing = InstrumentListing(
        asset_id="cik:0000320193",
        cik="0000320193",
        ticker="AAPL",
        exchange="NASDAQ",
        mic=mic,
        currency="USD",
        timezone="America/New_York",
        provider_symbol="AAPL",
    )
    record = {
        "vendor": "Tiingo",
        "request": {
            "dataset": "daily_prices",
            "symbol": "AAPL",
            "start": "2025-01-02",
            "end": "2025-01-02",
        },
        "payload": [
            {
                "date": "2025-01-02T00:00:00Z",
                "open": 100,
                "high": 110,
                "low": 90,
                "close": close,
                "volume": 1000,
                "adjOpen": 100,
                "adjHigh": 110,
                "adjLow": 90,
                "adjClose": close,
                "adjVolume": 1000,
                "divCash": 0,
                "splitFactor": 1,
            }
        ],
        "retrieved_at": retrieved_at,
        "manifest_sha256": "a" * 64,
        "raw_sha256": ("b" if close == 105 else "c") * 64,
        "source_reference": "https://api.tiingo.com/tiingo/daily/AAPL/prices",
        "license": "https://www.tiingo.com/documentation/general/overview",
    }
    return normalize_tiingo(record, listing)


def test_replay_is_idempotent_and_correction_appends_revision(tmp_path):
    from scanner.market_data.archive import MarketDataArchive

    archive = MarketDataArchive(
        tmp_path / "market.sqlite", now=lambda: datetime(2025, 1, 6, 12, tzinfo=UTC)
    )
    assert archive.import_batch(batch()) == {"inserted": 1, "unchanged": 0, "revised": 0}
    assert archive.import_batch(batch()) == {"inserted": 0, "unchanged": 1, "revised": 0}
    assert archive.import_batch(batch(close=106)) == {
        "inserted": 0,
        "unchanged": 0,
        "revised": 1,
    }

    history = archive.revision_history("cik:0000320193", "Tiingo", "2025-01-02")
    assert [row["revision"] for row in history] == [1, 2]
    assert [row["bar"]["raw"]["close"] for row in history] == ["105", "106"]


def test_archive_rejects_listing_change_for_same_asset(tmp_path):
    from scanner.market_data.archive import MarketDataArchive

    archive = MarketDataArchive(
        tmp_path / "market.sqlite", now=lambda: datetime(2025, 1, 6, 13, tzinfo=UTC)
    )
    archive.import_batch(batch())
    with pytest.raises(ValueError, match="listing identity conflict"):
        archive.import_batch(batch(mic="XNYS"))


def test_replaying_an_older_revision_does_not_revert_latest_value(tmp_path):
    from scanner.market_data.archive import MarketDataArchive

    archive = MarketDataArchive(tmp_path / "market.sqlite")
    archive.import_batch(batch())
    archive.import_batch(batch(close=106))

    assert archive.import_batch(batch()) == {"inserted": 0, "unchanged": 1, "revised": 0}
    history = archive.revision_history("cik:0000320193", "Tiingo", "2025-01-02")
    assert [row["bar"]["raw"]["close"] for row in history] == ["105", "106"]


def test_logical_digest_is_reproducible_across_archives(tmp_path):
    from scanner.market_data.archive import MarketDataArchive

    def clock():
        return datetime(2025, 1, 6, 13, tzinfo=UTC)

    left = MarketDataArchive(tmp_path / "left.sqlite", now=clock)
    right = MarketDataArchive(tmp_path / "right.sqlite", now=clock)
    left.import_batch(batch())
    right.import_batch(batch())
    assert left.logical_sha256() == right.logical_sha256()
    assert len(left.logical_sha256()) == 64


def test_strict_query_excludes_rows_not_retrieved_by_as_of(tmp_path):
    from scanner.market_data.archive import MarketDataArchive

    archive = MarketDataArchive(
        tmp_path / "market.sqlite", now=lambda: datetime(2025, 1, 6, 13, tzinfo=UTC)
    )
    archive.import_batch(batch())

    strict = archive.prices(
        "cik:0000320193",
        start="2025-01-02",
        end="2025-01-02",
        as_of=datetime(2025, 1, 3, tzinfo=UTC),
        availability_mode="strict",
    )
    assert strict["prices"] == []
    assert strict["status"] == "unavailable_at_as_of"
    assert strict["training_eligible"] is False


def test_modeled_query_is_hypothetical_and_never_uses_pre_close_data(tmp_path):
    from scanner.market_data.archive import MarketDataArchive

    archive = MarketDataArchive(
        tmp_path / "market.sqlite", now=lambda: datetime(2025, 1, 6, 13, tzinfo=UTC)
    )
    archive.import_batch(batch())
    before_close = archive.prices(
        "cik:0000320193",
        start="2025-01-02",
        end="2025-01-02",
        as_of=datetime(2025, 1, 2, 20, 59, tzinfo=UTC),
        availability_mode="modeled",
    )
    after_close = archive.prices(
        "cik:0000320193",
        start="2025-01-02",
        end="2025-01-02",
        as_of=datetime(2025, 1, 2, 21, 1, tzinfo=UTC),
        availability_mode="modeled",
    )
    assert before_close["prices"] == []
    assert len(after_close["prices"]) == 1
    assert after_close["availability"] == "hypothetical_modeled_session_close"
    assert after_close["historical_availability_verified"] is False
    assert after_close["training_eligible"] is False


def test_strict_query_compares_retrieval_instants_across_timezone_offsets(tmp_path):
    from scanner.market_data.archive import MarketDataArchive

    archive = MarketDataArchive(
        tmp_path / "market.sqlite", now=lambda: datetime(2025, 1, 6, 10, 15, tzinfo=UTC)
    )
    archive.import_batch(batch(retrieved_at="2025-01-06T12:00:00+02:00"))
    result = archive.prices(
        "cik:0000320193",
        start="2025-01-02",
        end="2025-01-02",
        as_of=datetime(2025, 1, 6, 10, 30, tzinfo=UTC),
        availability_mode="strict",
    )
    assert len(result["prices"]) == 1


def test_strict_query_waits_for_first_local_storage_not_only_provider_retrieval(tmp_path):
    from scanner.market_data.archive import MarketDataArchive

    archive = MarketDataArchive(
        tmp_path / "market.sqlite",
        now=lambda: datetime(2025, 1, 10, 12, tzinfo=UTC),
    )
    archive.import_batch(batch(retrieved_at="2025-01-06T12:00:00+00:00"))

    before_storage = archive.prices(
        "cik:0000320193",
        start="2025-01-02",
        end="2025-01-02",
        as_of=datetime(2025, 1, 7, tzinfo=UTC),
        availability_mode="strict",
    )
    after_storage = archive.prices(
        "cik:0000320193",
        start="2025-01-02",
        end="2025-01-02",
        as_of=datetime(2025, 1, 11, tzinfo=UTC),
        availability_mode="strict",
    )
    assert before_storage["prices"] == []
    assert after_storage["prices"][0]["first_stored_at"] == "2025-01-10T12:00:00+00:00"


def test_strict_query_exposes_correction_only_after_correction_storage(tmp_path):
    from scanner.market_data.archive import MarketDataArchive

    clocks = iter(
        [
            datetime(2025, 1, 7, tzinfo=UTC),
            datetime(2025, 1, 10, tzinfo=UTC),
        ]
    )
    archive = MarketDataArchive(tmp_path / "market.sqlite", now=lambda: next(clocks))
    archive.import_batch(batch())
    archive.import_batch(batch(close=106, retrieved_at="2025-01-08T12:00:00+00:00"))

    original = archive.prices(
        "cik:0000320193",
        start="2025-01-02",
        end="2025-01-02",
        as_of=datetime(2025, 1, 9, tzinfo=UTC),
        availability_mode="strict",
    )
    corrected = archive.prices(
        "cik:0000320193",
        start="2025-01-02",
        end="2025-01-02",
        as_of=datetime(2025, 1, 11, tzinfo=UTC),
        availability_mode="strict",
    )
    assert original["prices"][0]["raw"]["close"] == "105"
    assert corrected["prices"][0]["raw"]["close"] == "106"


def test_legacy_archive_without_storage_timestamp_fails_closed(tmp_path):
    from scanner.market_data.archive import MarketDataArchive

    path = tmp_path / "legacy.sqlite"
    with sqlite3.connect(path) as connection:
        connection.execute(
            """CREATE TABLE bar_revision (
                asset_id TEXT, provider TEXT, session_date TEXT, revision INTEGER,
                value_sha256 TEXT, bar_json TEXT, manifest_sha256 TEXT,
                raw_sha256 TEXT, retrieved_at TEXT
            )"""
        )

    with pytest.raises(ValueError, match="cannot prove first local storage time"):
        MarketDataArchive(path)
