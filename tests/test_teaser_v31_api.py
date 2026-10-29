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


def test_solution_pdf_prefills_resolution_and_requires_token(tmp_path):
    import base64
    import glob

    pdfs = glob.glob("tests/fixtures/**/*.pdf", recursive=True)
    assert pdfs
    body = {"pdf_base64": base64.b64encode(open(pdfs[0], "rb").read()).decode()}
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    settings = Settings(
        _env_file=None, detective_public_root=tmp_path, detective_live_api_token="local-test-only"
    )
    with TestClient(create_app(settings, engine)) as client:
        assert client.post("/api/hebeltrader/cases/solution-pdf", json=body).status_code == 403
        headers = {"X-Research-Authorization": "local-test-only"}
        ok = client.post("/api/hebeltrader/cases/solution-pdf", headers=headers, json=body)
        assert ok.status_code == 200
        assert len(ok.json()["pdf_sha256"]) == 64
        bad = client.post(
            "/api/hebeltrader/cases/solution-pdf", headers=headers, json={"pdf_base64": "!!"}
        )
        assert bad.status_code == 422


def test_resolution_without_asset_id_can_be_saved_as_reference(tmp_path):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    settings = Settings(
        _env_file=None, detective_public_root=tmp_path, detective_live_api_token="local-test-only"
    )
    headers = {"X-Research-Authorization": "local-test-only"}
    with TestClient(create_app(settings, engine)) as client:
        case_id = client.post(
            "/api/hebeltrader/investigate",
            json={
                "teaser_text": "Unbekannter Konzern",
                "author": "Rudolf Wittmer",
                "issue": "1/26",
            },
        ).json()["case_id"]
        base = f"/api/hebeltrader/cases/{case_id}"
        assert (
            client.post(
                base + "/prospective", headers=headers, json={"basis": "unbekannt bei Erstprognose"}
            ).status_code
            == 200
        )
        resolved = client.post(
            base + "/resolution",
            headers=headers,
            json={
                "name": "Synopsys Inc.",
                "source": "Hebeltrader 201/2026",
                "error_analysis": "EDA statt Anlagenbau",
            },
        )
        assert resolved.status_code == 200
        assert resolved.json()["prediction_outcome"] in ("not_identified", "refuted")
        promoted = client.post(
            base + "/reference-promotion", headers=headers, json={"source": "Hebeltrader 201/2026"}
        )
        assert promoted.json() == {"reference_status": "prospective_reference"}
