import csv
import hashlib
import json
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from scanner.research import AssetIdentity

NOW = datetime(2026, 10, 24, 12, tzinfo=UTC)


def asset(index, *, country="US", instrument_type="unknown", exchange="NYSE"):
    return AssetIdentity(
        asset_type="stock",
        name=f"Independent Company {index}",
        ticker=f"C{index}",
        cik="9999999999" if index == 0 else str(index),
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
    delisted = asset(92).model_copy(update={"valid_to": date(2026, 1, 1)})
    assets += [asset(90, country="DE"), asset(91, instrument_type="fund"), delisted]
    first = select_us_pilot(build_index(tmp_path / "a", assets), as_of=NOW, count=10)
    second = select_us_pilot(
        build_index(tmp_path / "b", list(reversed(assets))), as_of=NOW, count=10
    )

    assert [row.cik for row in first] == [row.cik for row in second]
    assert len(first) == 10
    assert all(row.country == "US" and row.instrument_type != "fund" for row in first)
    assert all(row.cik != "0000000092" for row in first)
    expected = sorted(
        (
            row
            for row in assets
            if row.country == "US"
            and row.instrument_type != "fund"
            and (row.valid_to is None or row.valid_to >= NOW.date())
        ),
        key=lambda row: hashlib.sha256(
            f"market-pilot-v1:cik:{str(row.cik).zfill(10)}".encode()
        ).hexdigest(),
    )[:10]
    assert [row.cik for row in first] == [str(row.cik).zfill(10) for row in expected]


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

    assert report["status"] == "blocked"
    assert report["blocker_code"] == "blocked_missing_credentials"
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

    assert report["status"] == "blocked"
    assert report["blocker_code"] == "synthetic_fixture_not_real_acceptance"
    assert report["successful_instruments"] == 10
    assert all(row["session_count"] == 250 for row in report["instruments"])
    assert all(isinstance(row["data_age_seconds"], int) for row in report["instruments"])
    assert all(
        row["calendar_status"] == "unavailable_not_inferred" for row in report["instruments"]
    )
    assert all(row["missing_sessions"] is None for row in report["instruments"])
    assert report["real_provider_coverage_measured"] is False
    assert report["coverage_kind"] == "synthetic_fixture"


def test_calendar_audit_reports_missing_sessions_and_action_types(tmp_path):
    from scanner.market_data.models import ExchangeCalendar
    from scanner.market_data.pilot import audit_batch
    from scanner.market_data.providers import normalize_tiingo

    record = tiingo_record("C1", sessions=250)
    record["payload"][0]["divCash"] = 0.25
    record["payload"][1]["splitFactor"] = 2
    provider_dates = [row["date"][:10] for row in record["payload"]]
    missing = "2025-12-31"
    calendar = ExchangeCalendar(
        supported_mics={"XNYS"},
        timezone="America/New_York",
        source_reference="https://exchange.example/official-calendar",
        raw_sha256="e" * 64,
        retrieved_at=NOW,
        sessions={
            **{
                day: datetime.combine(
                    date.fromisoformat(day), time(16), ZoneInfo("America/New_York")
                )
                for day in provider_dates
            },
            missing: datetime.combine(
                date.fromisoformat(missing), time(16), ZoneInfo("America/New_York")
            ),
        },
    )
    from scanner.market_data.pilot import _listing

    normalized = normalize_tiingo(record, _listing(asset(1)), calendar=calendar)
    audit = audit_batch(
        normalized,
        calendar=calendar,
        start="2025-01-01",
        end="2025-12-31",
        as_of=NOW,
    )
    assert audit["calendar_status"] == "verified_missing_sessions"
    assert audit["missing_sessions"] == [missing]
    assert audit["split_count"] == 1
    assert audit["dividend_count"] == 1


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
    assert result["sha256_file"].read_text().split()[0] == result["sha256"]
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


def test_calendar_csv_is_hash_bound_and_preserves_early_close(tmp_path):
    from scanner.market_data.pilot import load_calendar_csv

    path = tmp_path / "calendar.csv"
    path.write_text(
        "session_date,close_at\n"
        "2025-01-02,2025-01-02T16:00:00-05:00\n"
        "2025-11-28,2025-11-28T13:00:00-05:00\n"
    )
    calendar = load_calendar_csv(
        path,
        supported_mics="XNAS,XNYS,XASE",
        timezone="America/New_York",
        source_reference="https://exchange.example/official-calendar",
        retrieved_at=NOW,
    )
    assert calendar.sessions[date(2025, 11, 28)].hour == 13
    assert calendar.raw_sha256 == hashlib.sha256(path.read_bytes()).hexdigest()


def test_provider_failures_report_retries_per_instrument_and_block_acceptance(tmp_path):
    from scanner.market_data.archive import MarketDataArchive
    from scanner.market_data.pilot import run_tiingo_pilot

    class FailingClient:
        attempted_requests = 0

        def fetch(self, symbol, *, start, end):
            self.attempted_requests += 3
            raise ValueError("Tiingo request failed; bounded retries exhausted")

    report = run_tiingo_pilot(
        index=build_index(tmp_path, [asset(index) for index in range(10)]),
        market_archive=MarketDataArchive(tmp_path / "market.db"),
        raw_cache=tmp_path / "raw",
        start="2025-01-01",
        end="2025-12-31",
        as_of=NOW,
        max_requests=30,
        client=FailingClient(),
    )
    assert report["status"] == "blocked"
    assert report["blocker_code"] == "all_provider_requests_failed"
    assert report["requests_attempted"] == 30
    assert all(row["api_requests"] == 3 for row in report["instruments"])


def test_sec_pilot_index_excludes_ambiguous_multiple_listings_with_audit(tmp_path):
    from scanner.hebeltrader.eodhd import canonical, sha
    from scanner.market_data.pilot import build_sec_pilot_index
    from scanner.research_index.repository import ResearchIndex

    cache = tmp_path / "sec-cache"
    raw = canonical(
        {
            "fields": ["cik", "name", "ticker", "exchange"],
            "data": [
                [320193, "Apple Inc.", "AAPL", "Nasdaq"],
                [42, "Dual Corp", "DUAL.A", "NYSE"],
                [42, "Dual Corp", "DUAL.B", "NYSE"],
            ],
        }
    )
    raw_path = cache / "raw" / f"{sha(raw)}.json"
    raw_path.parent.mkdir(parents=True)
    raw_path.write_bytes(raw)
    request = cache / "requests" / "universe.json"
    request.parent.mkdir(parents=True)
    request.write_bytes(
        canonical(
            {
                "raw_file": f"raw/{sha(raw)}.json",
                "raw_sha256": sha(raw),
                "retrieved_at": "2026-10-24T00:00:00+00:00",
                "source_reference": "https://www.sec.gov/files/company_tickers_exchange.json",
                "vendor": "SEC_EDGAR",
            }
        )
    )

    audit = build_sec_pilot_index(request, tmp_path / "pilot.db")

    assert audit["included_issuers"] == 1
    assert audit["excluded_ambiguous_issuers"] == [
        {"cik": "0000000042", "tickers": ["DUAL.A", "DUAL.B"]}
    ]
    assert ResearchIndex(tmp_path / "pilot.db").coverage(NOW)["indexed_assets"] == 1
