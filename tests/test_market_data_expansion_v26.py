import json
from datetime import UTC, date, datetime, timedelta

import pytest

from scanner.research import AssetIdentity

NOW = datetime(2026, 10, 25, 12, tzinfo=UTC)


def _asset(index):
    return AssetIdentity(
        asset_type="stock",
        name=f"Company {index}",
        ticker=f"C{index}",
        cik=str(index),
        exchange="NYSE",
        country="US",
        instrument_type="operating_company",
        retrieved_at=datetime(2025, 1, 1, tzinfo=UTC),
        source_available_at=datetime(2025, 1, 1, tzinfo=UTC),
    )


def _index(tmp_path, size=140):
    from scanner.research_index.builder import build_index
    from scanner.research_index.repository import ResearchIndex

    path = tmp_path / "index.db"
    build_index(
        path, assets=[_asset(value) for value in range(1, size + 1)], events=[], facts=[], news=[]
    )
    return ResearchIndex(path)


def test_deterministic_pages_cover_100_distinct_companies_and_report_universe_size(tmp_path):
    from scanner.market_data.pilot import select_us_pilot

    index = _index(tmp_path)
    first, first_meta = select_us_pilot(index, as_of=NOW, count=50, offset=0, with_metadata=True)
    second, second_meta = select_us_pilot(index, as_of=NOW, count=50, offset=50, with_metadata=True)

    assert len(first) == len(second) == 50
    assert not ({row.cik for row in first} & {row.cik for row in second})
    assert first_meta == {"eligible_universe": 140, "selection_offset": 0}
    assert second_meta == {"eligible_universe": 140, "selection_offset": 50}


def test_page_beyond_universe_is_explicitly_empty(tmp_path):
    from scanner.market_data.pilot import select_us_pilot

    selected, metadata = select_us_pilot(
        _index(tmp_path, 10), as_of=NOW, count=25, offset=25, with_metadata=True
    )
    assert selected == []
    assert metadata == {"eligible_universe": 10, "selection_offset": 25}


def test_quota_ledger_reserves_conservatively_and_detects_tampering(tmp_path):
    from scanner.market_data.quota import TiingoQuotaLedger

    path = tmp_path / "quota.jsonl"
    ledger = TiingoQuotaLedger(path, hourly_limit=50, daily_limit=1000, monthly_symbol_limit=500)
    reservation = ledger.reserve(symbols=[f"C{i}" for i in range(40)], max_requests=40, at=NOW)
    assert reservation["reserved_requests"] == 40
    assert ledger.snapshot(NOW)["hour_reserved_requests"] == 40
    with pytest.raises(ValueError, match="hourly"):
        ledger.reserve(symbols=["EXTRA"], max_requests=11, at=NOW + timedelta(minutes=1))

    raw = path.read_bytes()
    path.write_bytes(raw.replace(b'"reserved_requests":40', b'"reserved_requests":4'))
    with pytest.raises(ValueError, match="integrity"):
        ledger.snapshot(NOW)


def test_quota_ledger_counts_unique_symbols_per_calendar_month(tmp_path):
    from scanner.market_data.quota import TiingoQuotaLedger

    ledger = TiingoQuotaLedger(tmp_path / "quota.jsonl", monthly_symbol_limit=3)
    ledger.reserve(symbols=["A", "B"], max_requests=2, at=NOW)
    ledger.reserve(symbols=["B"], max_requests=1, at=NOW + timedelta(hours=2))
    with pytest.raises(ValueError, match="monthly symbol"):
        ledger.reserve(symbols=["C", "D"], max_requests=2, at=NOW + timedelta(hours=4))


def test_incremental_correction_window_overlaps_latest_archived_session():
    from scanner.market_data.pilot import correction_window_start

    assert correction_window_start("2025-01-01", None, 10) == "2025-01-01"
    assert correction_window_start("2025-01-01", "2025-12-31", 10) == "2025-12-21"
    assert correction_window_start("2025-01-01", "2025-12-31", 0) == "2026-01-01"
    assert correction_window_start("2026-01-01", "2025-12-31", 10) == "2026-01-01"
    with pytest.raises(ValueError, match="correction"):
        correction_window_start("2025-01-01", "2025-12-31", -1)


def test_archive_coverage_reports_distinct_sessions_actions_and_revisions(tmp_path):
    from scanner.market_data.archive import MarketDataArchive
    from scanner.market_data.pilot import _listing
    from scanner.market_data.providers import normalize_tiingo
    from tests.test_market_data_pilot_v251 import tiingo_record

    archive = MarketDataArchive(tmp_path / "market.db", now=lambda: NOW + timedelta(hours=1))
    record = tiingo_record("C1", sessions=3)
    record["payload"][0]["divCash"] = 0.2
    batch = normalize_tiingo(record, _listing(_asset(1)))
    archive.import_batch(batch)
    corrected = json.loads(json.dumps(record))
    corrected["payload"][0]["close"] = 100.5
    corrected["raw_sha256"] = "a" * 64
    corrected["manifest_sha256"] = "b" * 64
    archive.import_batch(normalize_tiingo(corrected, _listing(_asset(1))))

    coverage = archive.instrument_coverage("cik:0000000001", "Tiingo")
    assert coverage == {
        "session_count": 3,
        "revision_count": 4,
        "revised_session_count": 1,
        "corporate_action_count": 1,
        "first_session": date(2025, 1, 2),
        "latest_session": date(2025, 1, 6),
    }


def test_benchmark_selection_is_separate_from_company_page(tmp_path):
    from scanner.market_data.pilot import benchmark_listing

    listing = benchmark_listing("SPY")
    assert listing.asset_id == "benchmark:SPY"
    assert listing.provider_symbol == "SPY"
    assert listing.cik is None
    assert listing.mic == "ARCX"


def test_benchmark_import_is_archived_under_non_candidate_identity(tmp_path):
    from scanner.market_data.archive import MarketDataArchive
    from scanner.market_data.pilot import run_tiingo_benchmark

    class OfflineClient:
        attempted_requests = 0

        def fetch(self, symbol, *, start, end):
            assert symbol == "SPY"
            return {
                "vendor": "Tiingo",
                "request": {
                    "dataset": "daily_prices",
                    "symbol": symbol,
                    "start": start,
                    "end": end,
                },
                "payload": [
                    {
                        "date": "2025-01-02T00:00:00Z",
                        "open": 100,
                        "high": 102,
                        "low": 99,
                        "close": 101,
                        "volume": 1000,
                        "adjOpen": 100,
                        "adjHigh": 102,
                        "adjLow": 99,
                        "adjClose": 101,
                        "adjVolume": 1000,
                        "divCash": 0,
                        "splitFactor": 1,
                    }
                ],
                "retrieved_at": NOW.isoformat(),
                "manifest_sha256": "a" * 64,
                "raw_sha256": "b" * 64,
                "source_reference": "https://api.tiingo.com/tiingo/daily/SPY/prices",
                "license": "https://www.tiingo.com/documentation/general/overview",
            }

    archive = MarketDataArchive(tmp_path / "market.db", now=lambda: NOW + timedelta(hours=1))
    report = run_tiingo_benchmark(
        market_archive=archive,
        raw_cache=tmp_path / "raw",
        start="2025-01-01",
        end="2025-12-31",
        as_of=NOW,
        allow_network=True,
        authorize_usage=True,
        max_requests=1,
        client=OfflineClient(),
    )
    assert report["role"] == "benchmark_only_not_candidate"
    assert report["asset_id"] == "benchmark:SPY"
    assert archive.list_instruments()[0]["asset_id"] == "benchmark:SPY"


def test_expansion_aggregate_rejects_synthetic_and_verifies_each_batch(tmp_path):
    from scanner.market_data.expansion import aggregate_batch_reports
    from scanner.market_data.pilot import write_pilot_report

    first = {
        "coverage_kind": "real_provider_archive",
        "status": "partial",
        "instruments": [
            {
                "asset_id": "cik:0000000001",
                "ticker": "ONE",
                "status": "imported",
                "archive_session_count": 250,
                "calendar_status": "verified_complete",
            }
        ],
    }
    second = {
        "coverage_kind": "real_provider_archive",
        "status": "partial",
        "instruments": [
            {
                "asset_id": "cik:0000000002",
                "ticker": "TWO",
                "status": "imported",
                "archive_session_count": 250,
                "calendar_status": "verified_complete",
            }
        ],
    }
    first_path = write_pilot_report(first, tmp_path / "batch-0000")["json"]
    second_path = write_pilot_report(second, tmp_path / "batch-0001")["json"]

    report, artifacts = aggregate_batch_reports(
        [second_path, first_path],
        output_prefix=tmp_path / "coverage",
        archive_sha256="a" * 64,
        target_count=2,
    )
    assert report["status"] == "accepted"
    assert report["distinct_instruments"] == 2
    assert report["minimum_250_sessions_met"] == 2
    assert report["calendar_verified_complete"] == 2
    assert artifacts["sha256_file"].is_file()

    synthetic = dict(first, coverage_kind="synthetic_fixture")
    synthetic_path = write_pilot_report(synthetic, tmp_path / "synthetic")["json"]
    with pytest.raises(ValueError, match="synthetic"):
        aggregate_batch_reports(
            [synthetic_path],
            output_prefix=tmp_path / "invalid",
            archive_sha256="b" * 64,
        )


def test_live_cli_requires_persistent_quota_ledger_when_token_exists(monkeypatch):
    from scanner.market_data.cli import _reserve_live_quota, parser

    args = parser().parse_args(
        [
            "pilot",
            "--index",
            "index.db",
            "--market-db",
            "market.db",
            "--raw-cache",
            "raw",
            "--output",
            "report",
            "--start",
            "2025-01-01",
            "--end",
            "2025-12-31",
            "--as-of",
            NOW.isoformat(),
            "--max-requests",
            "10",
            "--allow-network",
            "--authorize-provider-usage",
        ]
    )
    monkeypatch.setenv("TIINGO_API_TOKEN", "test-only-never-written")
    with pytest.raises(SystemExit, match="quota-ledger"):
        _reserve_live_quota(args, ["AAPL"], NOW)
