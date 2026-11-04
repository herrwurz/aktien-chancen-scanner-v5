import json

import httpx

from scanner.free_scan.scan import BROWSER_ONLY, run_free_scan

YAHOO = """
<table>
<tr><th>Symbol</th><th>Name</th><th>Price</th><th>Change %</th></tr>
<tr>
  <td>1</td>
  <td><a href="/quote/DUOL/">DUOL</a></td>
  <td>Duolingo, Inc.</td>
  <td>172.82</td>
  <td>+35.02%</td>
</tr>
<tr>
  <td>2</td>
  <td><a href="/quote/SAP.DE/">SAP.DE</a></td>
  <td>SAP SE</td>
  <td>210.00</td>
  <td>+4.10%</td>
</tr>
</table>
"""

WSO = """
<table>
<tr><th>Signal</th><th>Wertpapier</th><th>Uhrzeit</th>
<th>Kurs bei Signal</th><th>Strategie</th><th>3 Monate</th></tr>
<tr><td>MACD long bei SAP</td><td>SAP Chartsignale</td>
<td>18:00 Uhr</td><td>210,000€</td><td>long</td><td>+4,10 %</td></tr>
<tr><td>RSI überkauft bei Allianz</td><td>Allianz Chartsignale</td>
<td>18:00 Uhr</td><td>459,500€</td><td>short</td><td>+5,54 %</td></tr>
<tr><td>DAX</td><td>Index</td><td></td><td></td><td></td><td></td></tr>
</table>
"""

TV_STOCKS = {
    "data": [
        {"s": "NASDAQ:DUOL", "d": ["DUOL", 172.5, 4.2, 4_800_000, 61.0, "Technology Services"]},
        {"s": "XETR:SAP", "d": ["SAP", 210.0, 3.1, 1_200_000, 55.0, "Technology Services"]},
    ]
}
TV_CRYPTO = {
    "data": [
        {"s": "BINANCE:BEAMXTRY", "d": ["BEAMXTRY", 0.22, 7.1, 1_400_000_000, "BINANCE"]},
        {"s": "BINANCE:DOGEUSDT.P", "d": ["DOGEUSDT.P", 0.07, 3.1, 5_000_000_000, "BINANCE"]},
        {"s": "BINANCE:BTCUSDT", "d": ["BTCUSDT", 80000, 3.4, 2_000_000_000, "BINANCE"]},
        {"s": "BINANCE:BTCUSDT", "d": ["BTCUSDT", 80000, 3.4, 2_000_000_000, "BINANCE"]},
    ]
}
BINANCE = [
    {
        "symbol": "BTCUSDT",
        "priceChangePercent": "3.4",
        "quoteVolume": "2500000000",
        "lastPrice": "80000",
    },
    {
        "symbol": "ETHUPUSDT",
        "priceChangePercent": "20",
        "quoteVolume": "90000000",
        "lastPrice": "2",
    },
    {
        "symbol": "DOGEUSDT",
        "priceChangePercent": "1.2",
        "quoteVolume": "90000000",
        "lastPrice": "0.08",
    },
]


def _client(binance_status=200, binance_body=None):
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.endswith("/global/scan"):
            body = json.loads(request.content)
            payload = TV_CRYPTO if body["markets"] == ["crypto"] else TV_STOCKS
            return httpx.Response(200, json=payload)
        if "day_gainers" in url:
            return httpx.Response(200, text=YAHOO)
        if "signale/finder" in url:
            return httpx.Response(200, text=WSO)
        if url.endswith("/ticker/24hr"):
            body = BINANCE if binance_body is None else binance_body
            return httpx.Response(binance_status, json=body)
        raise AssertionError(url)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_scan_uses_only_allowed_urls_and_merges_shared_tickers():
    with _client() as client:
        report = run_free_scan(client)
    assert report["subscriptions_used"] == []
    by_id = {source["id"]: source for source in report["sources"]}
    assert by_id["tradingview_stocks"]["status"] == "delivered"
    assert by_id["yahoo"]["hits"][0]["label"] == "DUOL"
    assert by_id["yahoo"]["hits"][0]["name"] == "Duolingo, Inc."
    assert by_id["yahoo"]["hits"][0]["price"] == "172.82"
    crypto_labels = {hit["label"] for hit in by_id["tradingview_crypto"]["hits"]}
    assert "BEAMXTRY" not in crypto_labels
    assert by_id["wallstreet"]["hits"][0]["side"] == "long"
    assert by_id["wallstreet"]["hits"][0]["price"] == "210,000€"
    assert by_id["wallstreet"]["hits"][1]["side"] == "short"
    assert by_id["binance"]["hits"][0]["label"] == "BTC"
    assert all(hit["label"] != "ETHUP" for hit in by_id["binance"]["hits"])
    labels = {item["label"] for item in report["overlap"]}
    assert "DUOL" in labels
    assert "SAP" in labels
    assert "BTC" in labels
    for item in BROWSER_ONLY:
        assert by_id[item["id"]]["status"] == "browser_only"
        assert by_id[item["id"]]["hits"] == []


def test_binance_location_block_keeps_the_other_sources():
    with _client(binance_status=451, binance_body={"code": 0, "msg": "restricted"}) as client:
        report = run_free_scan(client)
    binance = next(source for source in report["sources"] if source["id"] == "binance")
    yahoo = next(source for source in report["sources"] if source["id"] == "yahoo")
    assert binance["status"] == "blocked"
    assert binance["hits"] == []
    assert "451" in binance["reason"]
    assert yahoo["status"] == "delivered"


def test_free_scan_page_renders_saved_report_without_a_live_call(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from scanner.config import Settings
    from scanner.main import create_app

    root = tmp_path / "detective"
    root.mkdir()
    (root / "free-scan.json").write_text(
        json.dumps(
            {
                "disclaimer": "Unverbindliche Beobachtung",
                "generated_at": "2026-11-04T20:00+01:00",
                "subscriptions_used": [],
                "sources": [],
                "overlap": [{"label": "DUOL", "sources": ["Yahoo", "TradingView"]}],
            }
        ),
        encoding="utf-8",
    )
    database = "sqlite:///" + str(tmp_path / "scan.db")
    monkeypatch.setenv("DATABASE_URL", database)
    app = create_app(Settings(_env_file=None, detective_public_root=root, database_url=database))
    client = TestClient(app)
    page = client.get("/free-scan")
    assert page.status_code == 200
    assert "DUOL" in page.text
    assert "Unverbindliche Beobachtung" in page.text

    saved = json.loads((root / "free-scan.json").read_text(encoding="utf-8"))
    monkeypatch.setattr("scanner.free_scan.scan.run_free_scan", lambda http: saved)
    response = client.post("/free-scan", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/free-scan"
