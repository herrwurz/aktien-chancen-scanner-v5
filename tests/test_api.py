from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from test_domain import START, candle

from scanner.config import Settings
from scanner.detector import VolumeDetector
from scanner.main import create_app
from scanner.models import Base
from scanner.service import ingest


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with sessionmaker(engine).begin() as session:
        ingest(
            session,
            [candle(0), candle(1, "40")],
            VolumeDetector(lookback=1),
            START + timedelta(hours=1),
        )
    with TestClient(create_app(Settings(_env_file=None), engine)) as client:
        yield client
    engine.dispose()


def test_dashboard_and_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}
    assert client.get("/api/ready").status_code == 200
    page = client.get("/")
    assert page.status_code == 200
    assert "BTCUSDT" in page.text
    assert "fixture" in page.text
    assert "Keine Handelsfreigabe" in page.text
    detective = client.get("/hebeltrader")
    assert detective.status_code == 200
    assert "HEBELTRADER analysieren" in detective.text


def test_signals_include_evidence_and_are_read_only(client):
    response = client.get("/api/signals")
    assert response.status_code == 200
    signal = response.json()[0]
    assert signal["symbol"] == "BTCUSDT"
    assert float(signal["ratio"]) == 4
    assert signal["reason"] == "volume_spike"
    assert signal["actionable"] is False
    assert signal["candle_close_time"] < signal["evaluated_at"]
    assert client.post("/api/signals", json={}).status_code == 405


def test_detective_text_api_returns_explained_unconfirmed_candidates(client):
    response = client.post(
        "/api/hebeltrader/detective/analyze",
        json={
            "teaser_text": (
                "US-Gesundheitskonzern mit Pharma und Medizintechnik. Call WKN HS5RMP."
            ),
            "publication_at": "2025-08-05T08:15:00+02:00",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    # Hypothesis mode does not crown a single WKN winner.
    assert payload["identification"]["status"] == "hypothesis_top3"
    assert payload["identification"]["selected_wkn"] is None
    assert any(
        row.get("wkn") == "853260" or (row.get("identity") or {}).get("wkn") == "853260"
        for row in payload["candidates"]
    )
    assert payload["derivative_candidate"]["candidates"][0]["confirmed"] is False
    assert payload["automatic_confirmation"] is False
    assert client.post("/api/hebeltrader/detective/analyze", json={}).status_code == 422


def test_filters_and_pagination(client):
    assert len(client.get("/api/candles?limit=1").json()) == 1
    assert len(client.get("/api/candles?limit=1&offset=1").json()) == 1
    assert client.get("/api/candles?symbol=ETHUSDT").json() == []
    assert len(client.get("/api/evaluations").json()) == 2
    assert client.get("/api/runs").json() == []
    for query in ("limit=0", "limit=501", "offset=-1", "interval=1m"):
        assert client.get(f"/api/candles?{query}").status_code == 422


def test_readiness_requires_migration():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    with TestClient(create_app(Settings(_env_file=None), engine)) as client:
        assert client.get("/api/health").status_code == 200
        assert client.get("/api/ready").status_code == 503
        assert client.get("/api/signals").status_code == 503
    engine.dispose()


@pytest.mark.parametrize(
    "values",
    [
        {"symbols": []},
        {"symbols": ["bad/usdt"]},
        {"intervals": []},
        {"intervals": ["1m"]},
        {"scan_seconds": 1},
        {"volume_lookback": 999},
        {"volume_threshold": "NaN"},
        {"min_quote_volume": "-1"},
        {"provider": "fake"},
    ],
)
def test_invalid_configuration_rejected(values):
    with pytest.raises(ValueError):
        Settings(_env_file=None, **values)
