from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from scanner.config import Settings
from scanner.main import create_app
from scanner.models import Base


def test_v31_api_case_resolution_is_protected_and_preserves_first_prediction(tmp_path):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    settings = Settings(
        _env_file=None, detective_public_root=tmp_path, detective_live_api_token="local-test-only"
    )
    with TestClient(create_app(settings, engine)) as client:
        scan = client.post(
            "/api/hebeltrader/investigate",
            json={
                "teaser_text": "Unbekannter Konzern",
                "author": "Rudolf Wittmer",
                "issue": "1/26",
            },
        ).json()
        case_id = scan["case_id"]
        payload = {
            "asset_id": "company:verified",
            "name": "Verified company",
            "source": "User resolution",
            "basis": "user",
            "error_analysis": "Insufficient original clues",
            "call_wkn": "ABC123",
        }
        assert (
            client.post(f"/api/hebeltrader/cases/{case_id}/resolution", json=payload).status_code
            == 403
        )
        headers = {"X-Research-Authorization": "local-test-only"}
        response = client.post(
            f"/api/hebeltrader/cases/{case_id}/resolution", headers=headers, json=payload
        )
        assert response.status_code == 200
        assert response.json()["product_verification"] == "not_verified"
        case = client.get(f"/api/hebeltrader/cases/{case_id}", headers=headers).json()
        assert case["first_prediction"]["candidates"] == []
        assert (
            client.get("/api/hebeltrader/quality", headers=headers).json()["independent"][
                "top1_rate"
            ]
            is None
        )
        assert client.get("/api/hebeltrader/cases").status_code == 403
    engine.dispose()


def test_empty_case_journal_token_does_not_authorize_missing_header(tmp_path):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    settings = Settings(_env_file=None, detective_public_root=tmp_path, detective_live_api_token="")
    with TestClient(create_app(settings, engine)) as client:
        assert client.get("/api/hebeltrader/cases").status_code == 503
    engine.dispose()
