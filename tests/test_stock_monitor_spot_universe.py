"""Offline coverage for spot-universe ranking and provider failure."""

import asyncio

import httpx

from scanner.stock_monitor.spot_universe import discover_spot_symbols


def test_discovery_ranks_liquid_spot_symbols():
    def handler(request):
        return httpx.Response(200, json=[
            {"symbol": "SMALLUSDT", "quoteVolume": "2000000"},
            {"symbol": "BIGUSDT", "quoteVolume": "9000000"},
            {"symbol": "DUSTUSDT", "quoteVolume": "10"},
            {"symbol": "OTHERBTC", "quoteVolume": "100000000"},
        ])
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await discover_spot_symbols(client, max_symbols=2)
    result = asyncio.run(run())
    assert result["status"] == "complete"
    assert result["symbols"] == ["BIGUSDT", "SMALLUSDT"]


def test_discovery_reports_unavailable_on_http_error():
    def handler(request):
        return httpx.Response(503)
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await discover_spot_symbols(client)
    result = asyncio.run(run())
    assert result["status"] == "unavailable"
    assert result["symbols"] == []
