from fastapi.testclient import TestClient


def web(tmp_path, monkeypatch):
    from scanner.web import create_web_app

    for name, value in [("password", "private-password"), ("token", "private-token")]:
        file = tmp_path / name
        file.write_text(value)
        monkeypatch.setenv("TEASER_" + name.upper() + "_FILE", str(file))
    monkeypatch.setenv("TEASER_STATE_DIR", str(tmp_path / "state"))
    return TestClient(create_web_app())


def test_web_requires_authentication_on_ui_and_api(tmp_path, monkeypatch):
    client = web(tmp_path, monkeypatch)
    for url in ["/", "/api/hebeltrader/cases", "/docs", "/api/health"]:
        assert client.get(url).status_code == 401
    assert client.get("/", auth=("admin", "wrong")).status_code == 401
    response = client.get("/", auth=("admin", "private-password"))
    assert response.status_code == 200
    assert "private-token" not in response.text
    assert response.headers["cache-control"] == "no-store"


def test_web_journal_does_not_require_browser_research_token(tmp_path, monkeypatch):
    client = web(tmp_path, monkeypatch)
    assert client.get("/api/hebeltrader/cases", auth=("admin", "private-password")).json() == []


def test_web_rejects_cross_origin_writes(tmp_path, monkeypatch):
    client = web(tmp_path, monkeypatch)
    response = client.post(
        "/api/hebeltrader/investigate",
        json={},
        auth=("admin", "private-password"),
        headers={"Origin": "https://attacker.example"},
    )
    assert response.status_code == 403


def test_web_missing_secrets_fails_closed(tmp_path, monkeypatch):
    import pytest

    from scanner.web import create_web_app

    monkeypatch.delenv("TEASER_PASSWORD_FILE", raising=False)
    with pytest.raises(ValueError, match="TEASER_PASSWORD_FILE"):
        create_web_app()


def test_browser_submission_persists_and_reopens_case(tmp_path, monkeypatch):
    client = web(tmp_path, monkeypatch)
    auth = ("admin", "private-password")
    response = client.post(
        "/api/hebeltrader/investigate",
        auth=auth,
        json={"headline": "Unbekannter Konzern", "teaser_text": "Ein Konzern mit neuen Produkten."},
        headers={"Origin": "http://testserver"},
    )
    assert response.status_code == 200
    case_id = response.json()["journal_case_id"]
    reopened = web(tmp_path, monkeypatch)
    rows = reopened.get("/api/hebeltrader/cases", auth=auth).json()
    assert len(rows) == 1
    assert rows[0]["case_id"] == case_id
    assert rows[0]["latest_prediction"] is not None
    assert reopened.get("/api/hebeltrader/cases/" + case_id, auth=auth).status_code == 200
