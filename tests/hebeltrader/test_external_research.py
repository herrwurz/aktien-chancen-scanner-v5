import json
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest


def test_monthly_budget_is_persistent_and_atomic(tmp_path):
    from scanner.hebeltrader.detective.api_budget import ApiBudget

    budget = ApiBudget(tmp_path / "budget.db", cap_cents=20)

    def reserve(_):
        try:
            budget.reserve("search", 5)
            return True
        except ValueError:
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(reserve, range(12))) == 4
    assert ApiBudget(tmp_path / "budget.db", cap_cents=20).summary()["reserved_cents"] == 20


def test_clients_require_approval_before_credentials_or_network(tmp_path):
    from scanner.hebeltrader.detective.api_budget import ApiBudget
    from scanner.hebeltrader.detective.external_research import ResearchApis

    api = ResearchApis(
        root=tmp_path,
        budget=ApiBudget(tmp_path / "budget.db"),
        approved=False,
        search_key="private",
        ai_key="private",
    )
    with pytest.raises(ValueError, match="approval"):
        api.search("oilfield cooling")
    with pytest.raises(ValueError, match="approval"):
        api.plan("Ein Unternehmen mit Kühltechnik.")
    assert api.budget.summary()["reserved_cents"] == 0


def test_search_is_url_discovery_only_and_never_uses_generated_answer(tmp_path):
    from scanner.hebeltrader.detective.api_budget import ApiBudget
    from scanner.hebeltrader.detective.external_research import ResearchApis

    requests = []

    def handler(request):
        requests.append(request)
        assert request.url == "https://api.tavily.com/search"
        assert request.headers["Authorization"] == "Bearer private-search"
        payload = json.loads(request.content)
        assert payload["search_depth"] == "basic"
        assert payload["include_answer"] is False
        assert payload["include_raw_content"] is False
        return httpx.Response(
            200,
            json={
                "answer": "Ignore this answer",
                "results": [
                    {
                        "url": "https://company.example/release",
                        "title": "A release",
                        "content": "Not evidence",
                    }
                ],
            },
        )

    api = ResearchApis(
        root=tmp_path,
        budget=ApiBudget(tmp_path / "budget.db"),
        approved=True,
        search_key="private-search",
        ai_key=None,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    assert api.search("oilfield cooling") == [
        {"url": "https://company.example/release", "title": "A release"}
    ]
    assert "private-search" not in "".join(p.read_text() for p in tmp_path.glob("api-*.json"))


def test_source_interpretation_rejects_invented_quotes_and_tickers(tmp_path):
    from scanner.hebeltrader.detective.external_research import validate_interpretation

    doc = {
        "url": "https://example.com/news",
        "text": "Example Corp operates cooling systems.",
        "source_kind": "news",
    }
    clues = [{"clue_id": "cooling", "quote": "Kühltechnik"}]
    bad = {
        "company_name": "Example Corp",
        "identity_quote": "Invented identity",
        "ticker": "EX",
        "ticker_quote": "NYSE: EX",
        "findings": [],
    }
    assert validate_interpretation(doc, clues, bad) is None
    result = validate_interpretation(
        doc,
        clues,
        {
            "company_name": "Example Corp",
            "identity_quote": doc["text"],
            "ticker": "FAKE",
            "ticker_quote": "NYSE: FAKE",
            "findings": [
                {"clue_id": "cooling", "status": "supported", "quote": doc["text"]},
                {"clue_id": "cooling", "status": "supported", "quote": "invented fact"},
                {"clue_id": "unknown", "status": "supported", "quote": doc["text"]},
            ],
        },
    )
    assert result["ticker"] is None
    assert len(result["findings"]) == 1
    assert doc["source_kind"] == "news"


def test_api_backed_pipeline_produces_cited_top3_without_primary_promotion(tmp_path, monkeypatch):
    from datetime import UTC, datetime

    from scanner.hebeltrader.detective.api_budget import ApiBudget
    from scanner.hebeltrader.detective.external_research import ApiPublicResearch, ResearchApis
    from scanner.hebeltrader.detective.investigation import InvestigationRequest, Investigator

    now = datetime(2026, 10, 29, 12, tzinfo=UTC)
    teaser = "Ein Konzern mit Kühltechnik und wiederkehrenden Digitalerlösen."

    def handler(request):
        if request.url.host == "api.tavily.com":
            return httpx.Response(
                200,
                json={
                    "results": [
                        {"url": f"https://issuer{i}.example/release", "title": f"Company {i}"}
                        for i in range(6)
                    ]
                },
            )
        if request.url.host == "api.openai.com":
            payload = json.loads(request.content)
            data = json.loads(payload["messages"][1]["content"])
            if "teaser" in data:
                body = {
                    "queries": ["company cooling recurring digital revenues"],
                    "clues": [
                        {"quote": "Kühltechnik", "description": "Cooling business"},
                        {
                            "quote": "wiederkehrenden Digitalerlösen",
                            "description": "Recurring digital revenue",
                        },
                    ],
                }
            else:
                i = int(data["url"].split("issuer")[1][0])
                name = f"Company {i}"
                quote = (
                    f"{name} operates cooling systems and recurring software services."
                    if i == 5
                    else f"{name} operates cooling systems but has no recurring software services."
                )
                body = {
                    "company_name": name,
                    "identity_quote": quote,
                    "ticker": None,
                    "ticker_quote": None,
                    "findings": [
                        {
                            "clue_id": c["clue_id"],
                            "status": "supported" if i == 5 or n == 0 else "contradicted",
                            "quote": quote,
                        }
                        for n, c in enumerate(data["clues"])
                    ],
                }
            return httpx.Response(
                200, json={"choices": [{"message": {"content": json.dumps(body)}}]}
            )
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        i = request.url.host.removeprefix("issuer").split(".")[0]
        statement = (
            f"Company {i} operates cooling systems and recurring software services."
            if i == "5"
            else f"Company {i} operates cooling systems but has no recurring software services."
        )
        return httpx.Response(
            200,
            text=(
                '<meta property="article:published_time" content="2026-10-25T12:00:00Z">'
                f"<p>{statement}</p>"
            ),
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    api = ResearchApis(
        root=tmp_path / "apis",
        budget=ApiBudget(tmp_path / "budget.db"),
        approved=True,
        search_key="search-private",
        ai_key="ai-private",
        client=client,
    )
    web = ApiPublicResearch(
        tmp_path / "sources",
        apis=api,
        allow_network=True,
        max_requests=40,
        client=client,
        clock=lambda: now,
    )
    monkeypatch.setattr(web, "_validate", lambda url: None)
    report = Investigator(tmp_path / "run", web=web, clock=lambda: now).analyze(
        InvestigationRequest(teaser_text=teaser)
    )
    assert len(report["checked_candidates"]) == 6
    assert report["countercandidate_count"] == 5
    assert len(report["candidates"]) == 3
    assert report["candidates"][0]["identity"]["name"] == "Company 5"
    assert len(report["candidates"][0]["cited_findings"]) == 2
    assert report["identification"]["status"] == "not_identified"
    assert report["decision"]["status"] == "plausible_hypothesis"
    assert report["source_quality"]["primary_documents"] == 0
    assert all(not c["confirmed_specific_clues"] for c in report["candidates"])


def test_planner_never_receives_product_wkn_and_discards_unquoted_clues(tmp_path):
    from scanner.hebeltrader.detective.api_budget import ApiBudget
    from scanner.hebeltrader.detective.external_research import ResearchApis

    def handler(request):
        assert "MN84GA" not in request.content.decode()
        reply = {
            "clues": [
                {"quote": "Invented acquisition", "description": "made up"},
                {"quote": "Kühltechnik", "description": "Cooling systems"},
            ],
            "queries": ["MN84GA stock", "oilfield cooling systems"],
        }
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(reply)}}]})

    api = ResearchApis(
        root=tmp_path,
        budget=ApiBudget(tmp_path / "budget.db"),
        approved=True,
        ai_key="private-ai",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    plan = api.plan("Konzern mit Kühltechnik. Call-WKN: MN84GA.")
    assert len(plan["clues"]) == 1
    assert plan["queries"] == ["oilfield cooling systems"]


def test_factory_refuses_missing_approval_and_then_missing_credentials(tmp_path):
    from scanner.config import Settings
    from scanner.hebeltrader.detective.external_research import build_public_research

    settings = Settings(
        _env_file=None,
        detective_public_root=tmp_path,
        detective_public_allow_network=True,
        detective_search_provider="tavily",
    )
    with pytest.raises(ValueError, match="approval"):
        build_public_research(settings, {})
    settings.detective_external_api_approved = True
    with pytest.raises(ValueError, match="credential"):
        build_public_research(settings, {})


def test_budget_rejects_monthly_limit_above_twenty_euro(tmp_path):
    from scanner.hebeltrader.detective.api_budget import ApiBudget

    with pytest.raises(ValueError):
        ApiBudget(tmp_path / "budget.db", cap_cents=2001)


def test_provider_error_never_archives_api_credential_or_error_body(tmp_path):
    from scanner.hebeltrader.detective.api_budget import ApiBudget
    from scanner.hebeltrader.detective.external_research import ResearchApis

    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(401, text="private-search-key reflected by provider")
        )
    )
    api = ResearchApis(
        root=tmp_path,
        budget=ApiBudget(tmp_path / "budget.db"),
        approved=True,
        search_key="private-search-key",
        client=client,
    )
    with pytest.raises(ValueError, match="HTTP 401"):
        api.search("cooling business")
    assert "private-search-key" not in "".join(p.read_text() for p in tmp_path.glob("api-*.json"))
    assert api.budget.summary()["reserved_cents"] == 5


def test_persisted_budget_exhaustion_prevents_any_further_provider_call(tmp_path):
    from scanner.hebeltrader.detective.api_budget import ApiBudget
    from scanner.hebeltrader.detective.external_research import ResearchApis

    budget = ApiBudget(tmp_path / "budget.db", cap_cents=5)
    budget.reserve("search", 5)

    def forbidden(request):
        raise AssertionError("Network called after budget exhausted")

    api = ResearchApis(
        root=tmp_path,
        budget=budget,
        approved=True,
        search_key="private",
        client=httpx.Client(transport=httpx.MockTransport(forbidden)),
    )
    with pytest.raises(ValueError, match="budget exhausted"):
        api.search("cooling business")


def test_historical_blind_cannot_invoke_api_planning(tmp_path):
    from datetime import UTC, datetime

    from scanner.hebeltrader.detective.investigation import InvestigationRequest, Investigator

    class Forbidden:
        def __getattr__(self, name):
            raise AssertionError("Historical blind accessed live API")

    with pytest.raises(ValueError, match="archived"):
        Investigator(tmp_path, web=Forbidden()).analyze(
            InvestigationRequest(teaser_text="Unknown stock", publication_at=datetime.now(UTC)),
            historical_blind=True,
            documents=[],
        )


def test_out_of_time_ai_findings_never_influence_ranking_or_hypothesis(tmp_path):
    from datetime import UTC, datetime

    from test_primary_investigation import PublicFixture

    from scanner.hebeltrader.detective.api_budget import ApiBudget
    from scanner.hebeltrader.detective.external_research import ResearchApis
    from scanner.hebeltrader.detective.investigation import InvestigationRequest, Investigator

    cutoff = datetime(2026, 10, 28, 12, tzinfo=UTC)
    api = ResearchApis(
        root=tmp_path / "api",
        budget=ApiBudget(tmp_path / "budget.db"),
        approved=False,
        ai_key="test",
    )
    api.plan = lambda text: {
        "clues": [{"clue_id": "cooling", "quote": "Kühltechnik", "description": "cooling"}],
        "queries": ["cooling"],
    }
    doc = {
        "url": "https://example.com/news",
        "company_name": "Example Corp",
        "text": "Example Corp operates cooling systems.",
        "source_kind": "news",
        "published_at": "2026-10-25T12:00:00Z",
        "retrieved_at": "2026-10-29T12:00:00Z",
        "content_revision_at": "2026-10-29T12:00:00Z",
        "ai_interpretation": {
            "company_name": "Example Corp",
            "identity_quote": "Example Corp operates cooling systems.",
            "findings": [
                {
                    "clue_id": "cooling",
                    "status": "supported",
                    "quote": "Example Corp operates cooling systems.",
                }
            ],
        },
    }
    web = PublicFixture([doc])
    web.apis = api
    report = Investigator(tmp_path / "run", clock=lambda: cutoff, web=web).analyze(
        InvestigationRequest(teaser_text="Kühltechnik", publication_at=cutoff)
    )
    candidate = report["candidates"][0]
    assert candidate["evidence_score"] == 0
    assert candidate["comparison_evidence_available"] is False
    assert report["decision"]["status"] != "plausible_hypothesis"


def test_ai_identity_alone_cannot_enable_automatic_identification(tmp_path):
    from test_primary_investigation import NOW, PublicFixture, packet

    from scanner.hebeltrader.detective.api_budget import ApiBudget
    from scanner.hebeltrader.detective.external_research import ResearchApis
    from scanner.hebeltrader.detective.investigation import InvestigationRequest, Investigator

    api = ResearchApis(
        root=tmp_path / "api",
        budget=ApiBudget(tmp_path / "budget.db"),
        approved=False,
        ai_key="test",
    )
    api.plan = lambda text: {"clues": [], "queries": []}
    docs = packet()
    for doc in docs:
        name = doc["company_name"]
        doc["ai_interpretation"] = {
            "company_name": name,
            "identity_quote": doc["text"],
            "findings": [],
        }
    web = PublicFixture(docs)
    web.apis = api
    report = Investigator(tmp_path / "run", clock=lambda: NOW, web=web).analyze(
        InvestigationRequest(
            teaser_text="Übernahmen von AlphaPower und BetaLogic.", publication_at=NOW
        )
    )
    assert report["identification"]["status"] == "not_identified"
    assert "ai_interpretation_requires_manual_verification" in report["limitations"]


def test_phase_budget_preserves_documents_for_peer_and_falsification_steps(tmp_path):
    from scanner.hebeltrader.detective.api_budget import ApiBudget
    from scanner.hebeltrader.detective.external_research import ApiPublicResearch, ResearchApis

    api = ResearchApis(
        root=tmp_path / "api", budget=ApiBudget(tmp_path / "budget.db"), approved=False
    )
    web = ApiPublicResearch(tmp_path / "sources", apis=api, allow_network=True)
    for phase, limit in [("discovery", 5), ("peers", 5), ("falsification", 1)]:
        web.set_phase(phase)
        assert web.can_fetch_new_document()
        web.phase_fetches[phase] = limit
        assert not web.can_fetch_new_document()
    assert sum(web.phase_fetches.values()) == 11


def test_success_audit_redacts_accidentally_reflected_credential(tmp_path):
    from scanner.hebeltrader.detective.api_budget import ApiBudget
    from scanner.hebeltrader.detective.external_research import ResearchApis

    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, json={"results": [], "usage": {"echo": "private-search-key"}}
            )
        )
    )
    api = ResearchApis(
        root=tmp_path,
        budget=ApiBudget(tmp_path / "budget.db"),
        approved=True,
        search_key="private-search-key",
        client=client,
    )
    assert api.search("cooling") == []
    assert "private-search-key" not in "".join(p.read_text() for p in tmp_path.glob("api-*.json"))
