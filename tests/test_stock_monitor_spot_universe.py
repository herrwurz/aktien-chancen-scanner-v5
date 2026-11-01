"""Offline coverage for market-wide screening and bounded detail budget."""

import asyncio

import httpx

from scanner.stock_monitor.spot_universe import discover_spot_symbols


def test_discovery_screens_all_and_ranks_movers():
    def handler(request):
        return httpx.Response(200, json=[
            {"symbol": "SMALLUSDT", "quoteVolume": "200000", "priceChangePercent": "45"},
            {"symbol": "BIGUSDT", "quoteVolume": "9000000", "priceChangePercent": "2"},
            {"symbol": "DUSTUSDT", "quoteVolume": "10", "priceChangePercent": "500"},
            {"symbol": "OTHERBTC", "quoteVolume": "100000000", "priceChangePercent": "100"},
        ])

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await discover_spot_symbols(client, max_symbols=2)

    result = asyncio.run(run())
    assert result["status"] == "complete"
    assert result["screened_symbols"] == 4
    assert result["eligible_symbols"] == 2
    assert result["symbols"] == ["SMALLUSDT", "BIGUSDT"]


def test_discovery_reports_unavailable_on_http_error():
    def handler(request):
        return httpx.Response(503)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await discover_spot_symbols(client)

    result = asyncio.run(run())
    assert result["status"] == "unavailable"
    assert result["symbols"] == []
