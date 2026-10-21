import asyncio
from datetime import timedelta

import httpx
import pytest
from test_domain import START

from scanner.providers.binance import BinanceSpotProvider, ProviderError
from scanner.providers.fixture import FixtureProvider


def row(index=0, volume="10"):
    start = int((START + timedelta(minutes=index * 5)).timestamp() * 1000)
    return [start, "100", "110", "90", "105", volume, start + 299999, "100000", 10, "0", "0", "0"]


def fetch(handler, now=None):
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await BinanceSpotProvider(client, retry_delay=0).fetch_candles(
                "BTCUSDT", "5m", limit=21, now=now or START + timedelta(minutes=5)
            )

    return asyncio.run(run())


def test_binance_parses_decimals_and_excludes_open_candle():
    def handler(request):
        assert request.url.path == "/api/v3/klines"
        assert request.url.params["interval"] == "5m"
        assert request.url.params["limit"] == "21"
        assert "X-MBX-APIKEY" not in request.headers
        return httpx.Response(200, json=[row(0, "10.12345678"), row(1)])

    candles = fetch(handler)
    assert len(candles) == 1
    assert str(candles[0].volume) == "10.12345678"
    assert candles[0].close_time == START + timedelta(minutes=5)
    assert candles[0].provider == "binance_spot"


def test_rate_limit_has_bounded_retries():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(429, headers={"Retry-After": "0"})

    with pytest.raises(ProviderError):
        fetch(handler)
    assert len(requests) == 3


def test_transient_failure_recovers():
    attempts = []

    def handler(request):
        attempts.append(request)
        return httpx.Response(503) if len(attempts) == 1 else httpx.Response(200, json=[row()])

    assert len(fetch(handler)) == 1


@pytest.mark.parametrize("payload", [{"code": -1}, [[1, 2]], [row(0, "-10")], [row(), row()]])
def test_malformed_payload_is_provider_error(payload):
    with pytest.raises(ProviderError):
        fetch(lambda request: httpx.Response(200, json=payload))


def test_client_error_not_retried():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(400)

    with pytest.raises(ProviderError):
        fetch(handler)
    assert len(requests) == 1


def test_fixture_is_closed_deterministic_and_has_spike():
    provider = FixtureProvider()
    now = START + timedelta(hours=6)
    a = asyncio.run(provider.fetch_candles("BTCUSDT", "15m", limit=21, now=now))
    b = asyncio.run(provider.fetch_candles("BTCUSDT", "15m", limit=21, now=now))
    assert a == b
    assert len(a) == 21
    assert a[-1].volume == a[-2].volume * 4
    assert all(c.close_time <= now for c in a)
