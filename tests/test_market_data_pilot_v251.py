import csv
import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from scanner.research import AssetIdentity

NOW = datetime(2026, 10, 24, 12, tzinfo=UTC)


def asset(index, *, country="US", instrument_type="unknown", exchange="NYSE"):
    return AssetIdentity(
        asset_type="stock",
        name=f"Independent Company {index}",
        ticker=f"C{index}",
        cik=str(index),
        exchange=exchange,
        country=country,
        instrument_type=instrument_type,
        retrieved_at=datetime(2025, 1, 1, tzinfo=UTC),
        source_available_at=datetime(2025, 1, 1, tzinfo=UTC),
    )


def build_index(tmp_path, assets):
    from scanner.research_index.builder import build_index
    from scanner.research_index.repository import ResearchIndex

    path = tmp_path / "research.db"
    build_index(path, assets=assets, events=[], facts=[], news=[])
    return ResearchIndex(path)


def test_pilot_selection_is_stable_independent_and_excludes_known_funds(tmp_path):
    from scanner.market_data.pilot import select_us_pilot

    assets = [asset(index) for index in range(15)]
    assets += [asset(90, country="DE"), asset(91, instrument_type="fund")]
    first = select_us_pilot(build_index(tmp_path / "a", assets), as_of=NOW, count=10)
    second = select_us_pilot(
        build_index(tmp_path / "b", list(reversed(assets))), as_of=NOW, count=10
    )

    assert [row.cik for row in first] == [row.cik for row in second]
    assert len(first) == 10
    assert all(row.country == "US" and row.instrument_type != "fund" for row in first)
    expected = sorted(
        (row for row in assets if row.country == "US" and row.instrument_type != "fund"),
        key=lambda row: hashlib.sha256(f"market-pilot-v1:cik:{row.cik}".encode()).hexdigest(),
    )[:10]
    assert [row.cik for row in first] == [row.cik for row in expected]


def test_pilot_reports_missing_credentials_without_claiming_real_coverage(tmp_path, monkeypatch):
    from scanner.market_data.archive import MarketDataArchive
    from scanner.market_data.pilot import run_tiingo_pilot

    monkeypatch.delenv("TIINGO_API_TOKEN", raising=False)
    index = build_index(tmp_path, [asset(index) for index in range(12)])
    report = run_tiingo_pilot(
        index=index,
        market_archive=MarketDataArchive(tmp_path / "market.db"),
        raw_cache=tmp_path / "raw",
        start="2025-01-01",
        end="2025-12-31",
        as_of=NOW,
        allow_network=True,
        authorize_usage=True,
        max_requests=10,
        monthly_cost_eur="0",
    )

    assert report["status"] == "blocked_missing_credentials"
    assert report["selected_count"] == 10
    assert report["successful_instruments"] == 0
    assert report["real_provider_coverage_measured"] is False
    assert report["available_sources"] == ["Tiingo"]
    assert report["successful_sources"] == []
    assert report["requests_attempted"] == 0
    assert report["cost_eur"] == "0"


def tiingo_record(symbol, *, sessions=250):
    start = date(2025, 1, 2)
    rows = []
    current = start
    while len(rows) < sessions:
        if current.weekday() < 5:
            rows.append(
                {
                    "date": current.isoformat() + "T00:00:00Z",
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
            )
        current += timedelta(days=1)
    return {
        "vendor": "Tiingo",
        "request": {
            "dataset": "daily_prices",
            "symbol": symbol,
            "start": "2025-01-01",
            "end": "2025-12-31",
        },
        "payload": rows,
        "retrieved_at": NOW.isoformat(),
        "manifest_sha256": hashlib.sha256(symbol.encode()).hexdigest(),
        "raw_sha256": hashlib.sha256((symbol + "raw").encode()).hexdigest(),
        "source_reference": f"https://api.tiingo.com/tiingo/daily/{symbol}/prices",
        "license": "https://www.tiingo.com/documentation/general/overview",
    }


def test_pilot_measures_sessions_but_does_not_infer_exchange_calendar_gaps(tmp_path):
    from scanner.market_data.archive import MarketDataArchive
    from scanner.market_data.pilot import run_tiingo_pilot

    index = build_index(tmp_path, [asset(index) for index in range(10)])

    class OfflineClient:
        attempted_requests = 0

        def fetch(self, symbol, *, start, end):
            assert (start, end) == ("2025-01-01", "2025-12-31")
            return tiingo_record(symbol)

    report = run_tiingo_pilot(
        index=index,
        market_archive=MarketDataArchive(tmp_path / "market.db"),
        raw_cache=tmp_path / "unused",
        start="2025-01-01",
        end="2025-12-31",
        as_of=NOW,
        allow_network=False,
        authorize_usage=False,
        max_requests=10,
        monthly_cost_eur="0",
        client=OfflineClient(),
        coverage_kind="synthetic_fixture",
    )

    assert report["status"] == "ok"
    assert report["successful_instruments"] == 10
    assert all(row["session_count"] == 250 for row in report["instruments"])
    assert all(isinstance(row["data_age_seconds"], int) for row in report["instruments"])
    assert all(
        row["calendar_status"] == "unavailable_not_inferred" for row in report["instruments"]
    )
    assert all(row["missing_sessions"] is None for row in report["instruments"])
    assert report["real_provider_coverage_measured"] is False
    assert report["coverage_kind"] == "synthetic_fixture"


def test_reports_are_canonical_and_csv_has_one_row_per_selected_instrument(tmp_path):
    from scanner.market_data.pilot import write_pilot_report

    report = {
        "schema_version": "1.0",
        "status": "blocked_missing_credentials",
        "instruments": [
            {"asset_id": "cik:1", "ticker": "AAA", "status": "blocked"},
            {"asset_id": "cik:2", "ticker": "BBB", "status": "blocked"},
        ],
    }
    result = write_pilot_report(report, tmp_path / "coverage")
    raw = result["json"].read_bytes()
    assert hashlib.sha256(raw).hexdigest() == result["sha256"]
    assert raw == (json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n").encode()
    with result["csv"].open(newline="") as handle:
        assert len(list(csv.DictReader(handle))) == 2


def test_cli_requires_both_explicit_network_and_usage_flags():
    from scanner.market_data.cli import parser

    defaults = parser().parse_args(
        [
            "pilot",
            "--index",
            "research.db",
            "--market-db",
            "market.db",
            "--raw-cache",
            "raw",
            "--output",
            "coverage",
            "--start",
            "2025-01-01",
            "--end",
            "2025-12-31",
            "--as-of",
            "2026-01-01T00:00:00+00:00",
        ]
    )
    assert defaults.allow_network is False
    assert defaults.authorize_usage is False
    assert defaults.max_requests == 0


def test_pilot_enforces_project_budget_and_runtime_ceiling(tmp_path):
    from scanner.market_data.archive import MarketDataArchive
    from scanner.market_data.pilot import run_tiingo_pilot

    index = build_index(tmp_path, [asset(index) for index in range(10)])
    arguments = {
        "index": index,
        "market_archive": MarketDataArchive(tmp_path / "market.db"),
        "raw_cache": tmp_path / "raw",
        "start": "2025-01-01",
        "end": "2025-12-31",
        "as_of": NOW,
        "max_requests": 10,
    }
    with pytest.raises(ValueError, match="EUR20"):
        run_tiingo_pilot(**arguments, monthly_cost_eur=Decimal("20.01"))
    with pytest.raises(ValueError, match="duration"):
        run_tiingo_pilot(**arguments, monthly_cost_eur="0", max_duration_seconds=0)
