"""Synthetic Tiingo responses only; the Hetzner JNJ export is not in this checkout."""

import json
from datetime import UTC, datetime

import httpx
import pytest

CLOCK = datetime(2026, 2, 1, tzinfo=UTC)


def rows():
    return [
        {
            "date": "2025-08-05T00:00:00.000Z",
            "open": 170.54,
            "high": 172.0,
            "low": 169.0,
            "close": 171.0,
            "volume": 1000,
            "adjOpen": 169.54,
            "adjHigh": 171.0,
            "adjLow": 168.0,
            "adjClose": 170.0,
            "adjVolume": 1000,
            "divCash": 0.0,
            "splitFactor": 1.0,
        }
    ]


def test_tiingo_client_archives_and_replays_without_network(tmp_path, monkeypatch):
    from scanner.hebeltrader.tiingo import TiingoClient, read_tiingo_record

    monkeypatch.setenv("TIINGO_API_TOKEN", "synthetic-secret")
    seen = []

    def handler(request):
        seen.append(request)
        assert request.headers["Authorization"] == "Token synthetic-secret"
        return httpx.Response(200, content=json.dumps(rows()).encode())

    client = TiingoClient(
        tmp_path,
        allow_network=True,
        authorize_usage=True,
        max_requests=1,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        now=lambda: CLOCK,
    )
    first = client.fetch("JNJ", start="2025-08-05", end="2026-01-16")
    assert first["vendor"] == "Tiingo"
    assert first["request"]["dataset"] == "daily_prices"
    assert len(seen) == 1
    monkeypatch.delenv("TIINGO_API_TOKEN")
    replay = TiingoClient(tmp_path).fetch("JNJ", start="2025-08-05", end="2026-01-16")
    assert replay == first
    assert read_tiingo_record(tmp_path, first["manifest_sha256"])["payload"] == rows()


def test_tiingo_requires_all_explicit_network_gates_and_redacts_token(tmp_path, monkeypatch):
    from scanner.hebeltrader.tiingo import TiingoClient

    monkeypatch.setenv("TIINGO_API_TOKEN", "never-leak-this")
    with pytest.raises(ValueError, match="explicit network") as error:
        TiingoClient(tmp_path, max_requests=1).fetch("JNJ", start="2025-08-05", end="2026-01-16")
    assert "never-leak-this" not in str(error.value)


def test_tiingo_normalization_keeps_raw_and_adjusted_values_separate(tmp_path, monkeypatch):
    from scanner.hebeltrader.tiingo import TiingoClient
    from scanner.hebeltrader.tiingo_adapter import normalize_tiingo_record

    monkeypatch.setenv("TIINGO_API_TOKEN", "x")
    http = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=rows())))
    record = TiingoClient(
        tmp_path / "cache",
        allow_network=True,
        authorize_usage=True,
        max_requests=1,
        client=http,
        now=lambda: CLOCK,
    ).fetch("JNJ", start="2025-08-05", end="2026-01-16")
    normalized = normalize_tiingo_record(tmp_path / "cache", record["manifest_sha256"])
    assert normalized["bars"][0]["open"] == "170.54"
    assert normalized["bars"][0]["adjusted_open"] == "169.54"
    assert normalized["bars"][0]["split_factor"] == "1.0"
    assert normalized["provider"] == "Tiingo"
    assert normalized["instrument_type"] == "stock"
    assert normalized["derivative_quote_capable"] is False


def test_existing_tiingo_json_can_be_imported_fully_offline(tmp_path, monkeypatch):
    from scanner.hebeltrader.tiingo import import_tiingo_file
    from scanner.hebeltrader.tiingo_adapter import normalize_tiingo_record

    source = tmp_path / "jnj-historical.json"
    source.write_text(json.dumps(rows()))
    monkeypatch.setattr(httpx.Client, "get", lambda *a, **k: pytest.fail("network forbidden"))
    archive = import_tiingo_file(
        source,
        tmp_path / "cache",
        symbol="JNJ",
        start="2025-08-05",
        end="2026-01-16",
        retrieved_at=CLOCK,
    )
    normalized = normalize_tiingo_record(tmp_path / "cache", archive["manifest_sha256"])
    assert normalized["bars"][0]["close"] == "171.0"
    assert archive["import_mode"] == "offline_existing_file"


def test_provider_coverage_comparison_never_merges_series():
    from scanner.hebeltrader.market_provider import compare_daily_coverage

    report = compare_daily_coverage(
        {
            "Tiingo": [
                {"date": "2025-08-05", "open": "1"},
                {"date": "2025-08-06", "open": "2"},
            ],
            "EODHD": [
                {"date": "2025-08-06", "open": "2"},
                {"date": "2025-08-07", "open": "3"},
            ],
        }
    )
    assert report["shared_dates"] == ["2025-08-06"]
    assert report["providers"]["Tiingo"]["missing_vs_union"] == ["2025-08-07"]
    assert report["series_merged"] is False
