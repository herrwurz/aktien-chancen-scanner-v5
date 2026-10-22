from datetime import UTC, datetime

import httpx
import pytest

from scanner.hebeltrader.eodhd import EodhdClient

CLOCK = datetime(2026, 10, 22, tzinfo=UTC)


def test_no_network_or_paid_usage_without_explicit_authorization(tmp_path, monkeypatch):
    monkeypatch.setenv("EODHD_API_TOKEN", "private-token-value")

    def forbidden(request):
        raise AssertionError("unauthorized request")

    http = httpx.Client(transport=httpx.MockTransport(forbidden))
    for options in ({}, dict(allow_network=True), dict(allow_network=True, authorize_usage=True)):
        provider = EodhdClient(tmp_path, client=http, **options)
        with pytest.raises(ValueError):
            provider.fetch("eod", "ABC.US", start="2025-01-01", end="2025-01-03")


def test_immutable_cache_replay_and_raw_hash_tampering(tmp_path, monkeypatch):
    monkeypatch.setenv("EODHD_API_TOKEN", "private-token-value")
    calls = []

    def response(request):
        calls.append(request)
        assert request.url.params["api_token"] == "private-token-value"
        return httpx.Response(
            200, json=[dict(date="2025-01-02", open=10, high=12, low=9, close=11, volume=10)]
        )

    http = httpx.Client(transport=httpx.MockTransport(response))
    provider = EodhdClient(
        tmp_path,
        client=http,
        allow_network=True,
        authorize_usage=True,
        max_requests=3,
        monthly_cost_eur="19.99",
        now=lambda: CLOCK,
        sleeper=lambda _: None,
    )
    record = provider.fetch("eod", "ABC.US", start="2025-01-01", end="2025-01-03")
    offline = EodhdClient(tmp_path)
    assert offline.fetch("eod", "ABC.US", start="2025-01-01", end="2025-01-03") == record
    assert len(calls) == 1
    assert all(
        b"private-token-value" not in p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()
    )
    raw = tmp_path / record["raw_file"]
    raw.write_text("[]")
    with pytest.raises(ValueError):
        offline.fetch("eod", "ABC.US", start="2025-01-01", end="2025-01-03")


def test_rate_limit_bounded_budget_and_sanitized_error(tmp_path, monkeypatch):
    monkeypatch.setenv("EODHD_API_TOKEN", "private-token-value")
    calls = []

    def response(request):
        calls.append(request)
        return httpx.Response(429, text="private-token-value", headers={"Retry-After": "999999"})

    provider = EodhdClient(
        tmp_path,
        client=httpx.Client(transport=httpx.MockTransport(response)),
        allow_network=True,
        authorize_usage=True,
        max_requests=2,
        monthly_cost_eur="20",
        sleeper=lambda _: None,
    )
    with pytest.raises(ValueError) as exc:
        provider.fetch("eod", "ABC.US")
    assert "private-token-value" not in str(exc.value)
    assert len(calls) == 2
    with pytest.raises(ValueError):
        EodhdClient(tmp_path, monthly_cost_eur="100.01")


def test_secret_response_and_untrusted_endpoint_never_saved(tmp_path, monkeypatch):
    monkeypatch.setenv("EODHD_API_TOKEN", "private-token-value")
    provider = EodhdClient(
        tmp_path,
        client=httpx.Client(
            transport=httpx.MockTransport(
                lambda r: httpx.Response(200, json={"echo": "private-token-value"})
            )
        ),
        allow_network=True,
        authorize_usage=True,
        max_requests=2,
        monthly_cost_eur="0",
    )
    with pytest.raises(ValueError):
        provider.fetch("eod", "ABC.US")
    assert not list(tmp_path.rglob("*.json"))
    with pytest.raises(ValueError):
        provider.fetch("https://evil.invalid", "ABC.US")


def test_httpx_info_logs_do_not_expose_environment_key(tmp_path, monkeypatch, caplog):
    import logging

    monkeypatch.setenv("EODHD_API_TOKEN", "private-token-value")
    http = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=[])))
    provider = EodhdClient(
        tmp_path, client=http, allow_network=True, authorize_usage=True, max_requests=1
    )
    with caplog.at_level(logging.INFO, logger="httpx"):
        provider.fetch("splits", "ABC.US")
    assert "private-token-value" not in caplog.text


def test_weighted_fundamentals_quota_cannot_exceed_explicit_unit_allowance(tmp_path, monkeypatch):
    monkeypatch.setenv("EODHD_API_TOKEN", "private-token-value")
    calls = []

    def respond(request):
        calls.append(request)
        return httpx.Response(200, json={})

    http = httpx.Client(transport=httpx.MockTransport(respond))
    provider = EodhdClient(
        tmp_path, client=http, allow_network=True, authorize_usage=True, max_requests=1
    )
    with pytest.raises(ValueError):
        provider.fetch("fundamentals", "ABC.US")
    assert not calls
    provider = EodhdClient(
        tmp_path,
        client=http,
        allow_network=True,
        authorize_usage=True,
        max_requests=1,
        max_api_units=10,
    )
    provider.fetch("fundamentals", "ABC.US")
    assert provider.api_units_spent == 10 and len(calls) == 1
