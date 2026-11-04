from pathlib import Path

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


def test_out_of_competition_analyze_without_official_listing(tmp_path, monkeypatch):
    import base64

    client = web(tmp_path, monkeypatch)
    auth = ("admin", "private-password")
    origin = {"Origin": "http://testserver"}
    response = client.post(
        "/api/hebeltrader/investigate",
        auth=auth,
        headers=origin,
        json={
            "headline": "Midterms außer Konkurrenz",
            "teaser_text": "Silberförderer und Seltene Erden außer Konkurrenz.",
            "competition_mode": "out_of_competition",
        },
    )
    assert response.status_code == 200
    body = response.json()
    case_id = body["journal_case_id"]
    assert body["competition_mode"] == "out_of_competition"
    assert client.get("/api/hebeltrader/cases", auth=auth).json() == []
    ooc = client.get("/api/hebeltrader/cases?listing=out_of_competition", auth=auth).json()
    assert len(ooc) == 1 and ooc[0]["case_id"] == case_id
    quality = client.get("/api/hebeltrader/quality", auth=auth).json()
    assert quality["cases"] == []
    # Prefer a readable fixture — glob order can put broken.pdf first on CI.
    pdf_path = Path("tests/fixtures/hebeltrader/complete.pdf")
    assert pdf_path.is_file()
    pdf_b64 = base64.b64encode(pdf_path.read_bytes()).decode()
    stored = client.post(
        "/api/hebeltrader/cases/solution-pdf",
        auth=auth,
        headers=origin,
        json={"pdf_base64": pdf_b64, "case_id": case_id, "persist": True},
    )
    assert stored.status_code == 200
    assert stored.json()["persisted"] is True
    assert stored.json()["listed_as_official"] is True
    assert stored.json()["competition_mode"] == "official"
    listed = client.get("/api/hebeltrader/cases", auth=auth).json()
    assert len(listed) == 1 and listed[0]["case_id"] == case_id
    assert client.get("/api/hebeltrader/cases?listing=out_of_competition", auth=auth).json() == []
    resolved = client.post(
        f"/api/hebeltrader/cases/{case_id}/resolution",
        auth=auth,
        headers=origin,
        json={
            "name": "Test Company",
            "source": "purchased report",
            "error_analysis": "ooc dataset path",
            "basis": "user",
        },
    )
    assert resolved.status_code == 200
    promoted = client.post(
        f"/api/hebeltrader/cases/{case_id}/dataset-promotion",
        auth=auth,
        headers=origin,
        json={"name": "Test Company", "source": "purchased report", "ticker": "TEST"},
    )
    assert promoted.status_code == 200
    assert promoted.json()["export_relative_path"].endswith(f"{case_id}.json")
    assert client.get("/api/hebeltrader/cases", auth=auth).json()[0]["case_id"] == case_id
    page = client.get("/", auth=auth)
    assert "Außer Konkurrenz" in page.text
    assert "out-of-competition" in page.text
    assert (
        "ins Listing" in page.text
        or "Meine Fälle aufgenommen" in page.text
        or "Nicht mehr außer Konkurrenz" in page.text
        or "Fall im Listing" in page.text
    )


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
    assert len(data["cases"]) == 26
    assert data["summary"]["correct"] == 10
    assert data["summary"]["wrong"] == 7
    assert data["summary"]["unresolved"] == 0
    assert "HT-016" not in {c["case_id"] for c in data["cases"]}
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
        "exhausted": False,
        "max_cap_cents": 200_000,
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
    assert 'id="budget-form"' in response.text
    assert "Neues Monatsbudget speichern" in response.text


def test_analysis_status_and_result_are_directly_after_submit_form(tmp_path, monkeypatch):
    response = web(tmp_path, monkeypatch).get("/", auth=("admin", "private-password"))

    assert response.status_code == 200
    html = response.text
    button = html.index("Hinweise analysieren")
    status = html.index('id="analysis-status"')
    result = html.index('id="result"')
    cases = html.index('id="cases-panel"')
    assert button < status < result < cases
    assert "result.scrollIntoView" in html


def test_runtime_reports_tavily_credits_and_openai_estimate(tmp_path, monkeypatch):
    from scanner.hebeltrader.detective import provider_usage

    monkeypatch.setenv("DETECTIVE_SEARCH_API_KEY", "tvly-test-key")
    monkeypatch.setenv("EODHD_API_TOKEN", "eodhd-test-token")
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
        provider_usage.EodhdUsageMonitor,
        "snapshot",
        lambda self, key: {
            "status": "available",
            "subscription_type": "monthly",
            "subscription_mode": "paid",
            "api_requests": 128,
            "api_requests_date": "2026-10-30",
            "daily_rate_limit": 100000,
            "extra_limit": 0,
            "remaining": 99872,
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
    assert data["eodhd_key_configured"] is True
    assert data["provider_credits"]["eodhd"]["remaining"] == 99872
    assert "eodhd-test-token" not in str(data)


def test_web_page_explains_openai_balance_is_not_available(tmp_path, monkeypatch):
    response = web(tmp_path, monkeypatch).get("/", auth=("admin", "private-password"))

    assert "Verbleibende Anbieter-Credits" in response.text
    assert "OpenAI Billing-Dashboard" in response.text
    assert "authentication_failed" in response.text
    assert "invalid_response" in response.text
    assert 'id="eodhd-usage"' in response.text
    assert "EODHD-Tarife" in response.text
    assert "daily_limit_exceeded" in response.text


def test_cases_use_compact_single_case_selector():
    html = Path("scanner/templates/detective.html").read_text()
    assert 'id="cases-panel"' in html
    assert 'id="case-scope"' in html
    assert 'id="case-result"' in html
    assert 'id="cases-pie"' in html
    assert 'id="cases-legend"' in html
    assert 'id="case-select"' in html
    assert 'id="case-list"' in html
    assert "renderCaseList" in html
    assert "Fälle werden geladen …" in html
    assert "Noch keine Fälle" not in html
    assert "Alle aktiven Fälle anzeigen" in html
    assert "const repairTask=fetch('/api/hebeltrader/cases/reconcile'" in html
    assert 'id="active-case"' in html
    assert 'class="field-grid"' in html
    assert 'id="case-view"' not in html
    assert 'value="blind"' not in html
    assert 'value="reference"' not in html
    assert 'value="official"' not in html
    assert 'id="include-archived"' not in html
    assert 'id="ooc-case-select"' not in html
    assert 'id="prospective-references"' not in html
    assert 'id="import-references"' not in html
    assert 'id="load-cases"' not in html
    assert "Aktualisieren" not in html
    assert "18 Referenzfälle laden" not in html
    assert "Historische Referenzfälle" not in html
    assert "Prospektive Referenzfälle" not in html
    assert "loadProspectiveReferences" not in html
    assert "/api/hebeltrader/references" not in html
    assert "listing=all" in html
    assert "renderCasesPie" in html
    assert "selectCase" in html
    assert "resetResolutionToCase" in html
    assert "resultBucket(row)==='open'?'all':resultBucket(row)" not in html
    assert "innerHTML" not in html


def test_resolution_entry_is_prominent_and_can_be_opened_from_case():
    html = Path("scanner/templates/detective.html").read_text()
    assert 'id="resolution-panel"' in html
    assert 'class="resolution-callout"' in html
    assert "Originalauflösung eintragen" in html
    assert "openResolution" in html
    assert "draftErrorAnalysis" in html
    assert "fillErrorDraft" in html
    assert "Automatisch aus Top-Auswahl" in html
    assert 'textarea id="resolved-error" required' not in html
    assert "Nicht mehr außer Konkurrenz" in html
    assert "persist:false" in html
    assert "persist:Boolean(caseId)" not in html
    assert 'id="new-case"' in html
    assert "Neuen Fall eingeben" in html
    assert "startNewCase" in html
    assert "case-error" in html
    assert "error_briefing" in html
    assert "pendingSolutionFile" in html
    assert "syncResolution:true" in html
    assert "syncResolutionPanel" in html
    assert "panel.hidden=!row||Boolean(row.solution_pdf)" in html
    assert 'id="resolution-panel" class="resolution-callout" hidden' in html
    assert "!row.resolution" in html
    assert "Fall erneut eingegeben" not in html


def test_analysis_status_has_visible_states_and_safe_error_details():
    html = Path("scanner/templates/detective.html").read_text()
    assert ".analysis-status.running" in html
    assert "setAnalysisStatus" in html
    assert "readResponseError" in html
    assert "HTTP ${response.status}" in html


def test_candidate_resolution_shortcut_prefills_candidate_identity():
    html = Path("scanner/templates/detective.html").read_text()

    assert "makeResolutionButton" in html
    assert "Calls suchen" in html
    assert 'id="search-calls"' in html
    assert 'id="call-search-panel"' in html
    assert "identity.asset_id||candidate?.asset_id||''" in html
    assert "if(identity.name)document.querySelector('#resolved-name').value=identity.name;" in html
    assert "renderProse" in html
    assert "readerProse" in html
    assert "renderProse(readerProse(data),result)" in html
    assert "data.prose||fallbackProse" not in html
    assert "Working hypothesis" not in html
    assert "/api/hebeltrader/calls/search" in html
    assert "innerHTML" not in html


def test_case_actions_report_failures_and_preserve_archive_filter():
    html = Path("scanner/templates/detective.html").read_text()

    assert "showCaseActionError" in html
    assert "Archivierung fehlgeschlagen" in html
    assert "Wiederherstellung fehlgeschlagen" in html
    assert "Löschen fehlgeschlagen" in html
    assert "Blindtest-Markierung nicht möglich" in html
    assert "Referenzfreigabe nicht möglich" in html
    assert "refreshCaseSelect({reset:true})" in html
    assert "/api/hebeltrader/cases/${encodeURIComponent(row.case_id)}/delete" in html
    assert "Auflösung bearbeiten" in html
    assert "Fall endgültig löschen" in html
    assert "Weitere Aktionen" in html
    assert "renderCaseHints" in html
    assert "case-hint" in html
    assert "Nächster Schritt" in html
    assert "Fall im Listing" in html or "Fall ins Listing aufgenommen" in html
    assert "Nicht mehr außer Konkurrenz" in html
    assert "Prüfklasse" in html


def test_exhausted_budget_accepts_a_higher_monthly_ceiling(tmp_path, monkeypatch):
    from scanner.hebeltrader.detective.api_budget import ApiBudget

    client = web(tmp_path, monkeypatch)
    auth = ("admin", "private-password")
    assert (
        client.post("/api/hebeltrader/runtime/budget", json={"budget_eur": "30"}).status_code == 401
    )
    opened = client.get("/api/hebeltrader/runtime", auth=auth)
    assert opened.status_code == 200
    ledger = tmp_path / "state" / "detective" / "api-budget.db"
    budget = ApiBudget(ledger, cap_cents=opened.json()["api_costs"]["budget_cents"])
    cap = budget.summary()["cap_cents"]
    budget.reserve("search", cap)
    blocked = client.post(
        "/api/hebeltrader/runtime/budget",
        auth=auth,
        json={"budget_eur": f"{cap / 100:.2f}"},
    )
    assert blocked.status_code == 422
    assert "vorgemerkten" in blocked.json()["detail"]
    raised = client.post(
        "/api/hebeltrader/runtime/budget",
        auth=auth,
        json={"budget_eur": "30,50"},
    )
    assert raised.status_code == 200
    body = raised.json()
    assert body["budget_cents"] == 3050
    assert body["exhausted"] is False
    assert body["remaining_cents"] == 3050 - cap
    budget.reserve("search", 1)
