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


def test_web_archives_case_and_lists_it_only_when_requested(tmp_path, monkeypatch):
    from scanner.hebeltrader.detective.case_journal import CaseJournal

    client = web(tmp_path, monkeypatch)
    root = tmp_path / "state" / "detective" / "cases"
    case_id = CaseJournal(root).intake({"teaser_text": "obsolete test"})
    response = client.post(
        f"/api/hebeltrader/cases/{case_id}/archive",
        auth=("admin", "private-password"),
        json={"reason": "obsolete operator test"},
    )
    assert response.status_code == 200
    assert client.get("/api/hebeltrader/cases", auth=("admin", "private-password")).json() == []
    archived = client.get(
        "/api/hebeltrader/cases?include_archived=true", auth=("admin", "private-password")
    ).json()
    assert archived[0]["case_id"] == case_id
    assert archived[0]["archived"] is True


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


def test_reference_import_is_authenticated_and_separate_from_case_journal(tmp_path, monkeypatch):
    from pathlib import Path

    payload = Path("data/hebeltrader/teaser-cases.json").read_bytes()
    client = web(tmp_path, monkeypatch)
    assert client.post("/api/hebeltrader/references/import").status_code == 401
    assert (
        client.get("/api/hebeltrader/references", auth=("admin", "private-password")).status_code
        == 404
    )
    from scanner import reference_library

    monkeypatch.setattr(reference_library, "download", lambda: payload)
    response = client.post("/api/hebeltrader/references/import", auth=("admin", "private-password"))
    assert response.status_code == 200
    data = response.json()
    assert len(data["cases"]) == 18
    assert data["summary"]["correct"] == 10
    assert data["summary"]["wrong"] == 7
    assert data["summary"]["unresolved"] == 1
    williams = next(c for c in data["cases"] if c["case_id"] == "HT-016")
    assert williams["actual_company"] is None
    assert client.get("/api/hebeltrader/cases", auth=("admin", "private-password")).json() == []
    monkeypatch.setattr(
        reference_library, "download", lambda: (_ for _ in ()).throw(AssertionError())
    )
    assert (
        client.post(
            "/api/hebeltrader/references/import", auth=("admin", "private-password")
        ).status_code
        == 200
    )
    assert (
        web(tmp_path, monkeypatch)
        .get("/api/hebeltrader/references", auth=("admin", "private-password"))
        .json()
        == data
    )


def test_reference_import_rejects_changed_content(tmp_path, monkeypatch):
    from scanner import reference_library

    client = web(tmp_path, monkeypatch)
    monkeypatch.setattr(reference_library, "download", lambda: b'{"cases": []}')
    assert (
        client.post(
            "/api/hebeltrader/references/import", auth=("admin", "private-password")
        ).status_code
        == 503
    )
    assert not list((tmp_path / "state" / "references").glob("*.json"))


def test_runtime_diagnostics_are_private_and_report_effective_network_settings(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("DETECTIVE_PUBLIC_ALLOW_NETWORK", "true")
    client = web(tmp_path, monkeypatch)
    assert client.get("/api/hebeltrader/runtime").status_code == 401
    response = client.get("/api/hebeltrader/runtime", auth=("admin", "private-password"))
    assert response.status_code == 200
    data = response.json()
    assert data["public_research_enabled"] is True
    assert data["peer_research_supported"] is True
    assert "private-token" not in response.text
    assert "private-password" not in response.text


def test_runtime_reports_persistent_api_cost_reservations_by_provider(tmp_path, monkeypatch):
    from scanner.hebeltrader.detective.api_budget import ApiBudget

    monkeypatch.setenv("DETECTIVE_API_MONTHLY_BUDGET_EUR", "5")
    client = web(tmp_path, monkeypatch)
    ledger = tmp_path / "state" / "detective" / "api-budget.db"
    budget = ApiBudget(ledger, cap_cents=500)
    budget.reserve("search", 5)
    budget.reserve("search", 5)
    budget.reserve("ai", 10)

    response = client.get("/api/hebeltrader/runtime", auth=("admin", "private-password"))

    assert response.status_code == 200
    costs = response.json()["api_costs"]
    assert costs == {
        "month": costs["month"],
        "currency": "EUR",
        "budget_cents": 500,
        "reserved_cents": 20,
        "remaining_cents": 480,
        "usage_percent": 4.0,
        "providers": {
            "tavily": {"calls": 2, "reserved_cents": 10},
            "openai": {"calls": 1, "reserved_cents": 10},
        },
        "accounting": "conservative_call_ceiling_not_provider_invoice",
    }


def test_web_page_contains_api_cost_monitor(tmp_path, monkeypatch):
    response = web(tmp_path, monkeypatch).get("/", auth=("admin", "private-password"))

    assert response.status_code == 200
    assert 'id="api-cost-monitor"' in response.text
    assert "API-Kostenüberwachung" in response.text
    assert "/api/hebeltrader/runtime" in response.text


def test_analysis_status_and_result_are_directly_after_submit_form(tmp_path, monkeypatch):
    response = web(tmp_path, monkeypatch).get("/", auth=("admin", "private-password"))

    assert response.status_code == 200
    html = response.text
    button = html.index("Hinweise analysieren")
    status = html.index('id="analysis-status"')
    result = html.index('id="result"')
    cases = html.index("Meine Fälle")
    assert button < status < result < cases
    assert "result.scrollIntoView" in html


def test_runtime_reports_tavily_credits_and_openai_estimate(tmp_path, monkeypatch):
    from scanner.hebeltrader.detective import provider_usage

    monkeypatch.setenv("DETECTIVE_SEARCH_API_KEY", "tvly-test-key")
    monkeypatch.setattr(
        provider_usage.TavilyUsageMonitor,
        "snapshot",
        lambda self, key: {
            "status": "available",
            "plan": "Researcher",
            "plan_usage": 100,
            "plan_limit": 1000,
            "plan_remaining": 900,
            "key_usage": 100,
            "key_limit": 1000,
            "search_usage": 100,
            "paygo_usage": 0,
            "paygo_limit": 0,
        },
    )
    monkeypatch.setattr(
        provider_usage,
        "summarize_openai_usage",
        lambda root: {
            "status": "estimated",
            "model": "gpt-4.1-mini-2025-04-14",
            "input_tokens": 1000,
            "output_tokens": 200,
            "estimated_usd": 0.00072,
            "balance_available_via_project_key": False,
        },
    )

    data = (
        web(tmp_path, monkeypatch)
        .get("/api/hebeltrader/runtime", auth=("admin", "private-password"))
        .json()
    )

    assert data["provider_credits"]["tavily"]["plan_remaining"] == 900
    assert data["provider_credits"]["openai"]["estimated_usd"] == 0.00072


def test_web_page_explains_openai_balance_is_not_available(tmp_path, monkeypatch):
    response = web(tmp_path, monkeypatch).get("/", auth=("admin", "private-password"))

    assert "Verbleibende Anbieter-Credits" in response.text
    assert "OpenAI Billing-Dashboard" in response.text
    assert "authentication_failed" in response.text
    assert "invalid_response" in response.text
