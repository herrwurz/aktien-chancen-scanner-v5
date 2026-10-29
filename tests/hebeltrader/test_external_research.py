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


def test_search_archives_bounded_source_snippet_and_never_uses_generated_answer(tmp_path):
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
                        "content": "Company Corp has the only commercially available machine.",
                        "score": 0.91,
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
        {
            "url": "https://company.example/release",
            "title": "A release",
            "content": "Company Corp has the only commercially available machine.",
            "score": 0.91,
        }
    ]
    assert "private-search" not in "".join(p.read_text() for p in tmp_path.glob("api-*.json"))


def test_tavily_extract_returns_bounded_content(tmp_path):
    from scanner.hebeltrader.detective.api_budget import ApiBudget
    from scanner.hebeltrader.detective.external_research import ResearchApis

    def handler(request):
        assert request.url == "https://api.tavily.com/extract"
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "url": "https://issuer.example/results",
                        "raw_content": "Issuer Corp is the exclusive supplier. " * 1000,
                    }
                ],
                "failed_results": [],
            },
        )

    api = ResearchApis(
        root=tmp_path,
        budget=ApiBudget(tmp_path / "budget.db"),
        approved=True,
        search_key="private-search",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    result = api.extract("https://issuer.example/results")
    assert result["url"] == "https://issuer.example/results"
    assert 100 < len(result["content"]) <= 20_000


def test_tavily_extract_batches_urls_in_one_provider_call(tmp_path):
    from scanner.hebeltrader.detective.api_budget import ApiBudget
    from scanner.hebeltrader.detective.external_research import ResearchApis

    calls = []

    def handler(request):
        calls.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "results": [
                    {"url": url, "raw_content": f"Evidence from {url}"} for url in calls[0]["urls"]
                ]
            },
        )

    api = ResearchApis(
        root=tmp_path,
        budget=ApiBudget(tmp_path / "budget.db"),
        approved=True,
        search_key="private-search",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    urls = ["https://a.example/results", "https://b.example/results"]

    assert set(api.extract_many(urls)) == set(urls)
    assert len(calls) == 1
    assert calls[0]["urls"] == urls


def test_extract_source_class_requires_approved_primary_domain():
    from scanner.hebeltrader.detective.external_research import provider_source_class

    approved = {"issuer.example": "Issuer"}
    assert provider_source_class("https://issuer.example/results", approved, extracted=True) == "B"
    assert provider_source_class("https://news.example/story", approved, extracted=True) == "D"
    assert provider_source_class("https://issuer.example/results", approved, extracted=False) == "C"


def test_search_discards_unparseable_provider_publication_date(tmp_path):
    from scanner.hebeltrader.detective.api_budget import ApiBudget
    from scanner.hebeltrader.detective.external_research import ResearchApis

    api = ResearchApis(
        root=tmp_path,
        budget=ApiBudget(tmp_path / "budget.db"),
        approved=True,
        search_key="private-search",
        client=httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    200,
                    json={
                        "results": [
                            {
                                "url": "https://issuer.example/results",
                                "published_date": "sometime last week",
                            }
                        ]
                    },
                )
            )
        ),
    )

    assert "published_at" not in api.search("issuer results")[0]


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
            elif "candidates" in data:
                body = {
                    "preferred_asset_id": data["candidates"][0]["asset_id"],
                    "reason": "Citations favor the leader.",
                    "counterarguments": [],
                    "missing_evidence": ["Primary confirmation"],
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
    assert report["researched_sources"]
    assert {
        "url",
        "title",
        "source_class",
        "source_kind",
        "raw_sha256",
        "retrieved_at",
        "provider_score",
        "text_excerpt",
    } <= set(report["researched_sources"][0])


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


def test_planner_turns_unverified_company_hypotheses_into_verification_queries(tmp_path):
    from scanner.hebeltrader.detective.api_budget import ApiBudget
    from scanner.hebeltrader.detective.external_research import ResearchApis

    def handler(request):
        reply = {
            "clues": [
                {
                    "quote": "Kunden kaum noch eine Wahl haben",
                    "description": "Customers have no practical alternative",
                },
                {
                    "quote": "Gewinne wachsen im Eiltempo",
                    "description": "Rapid earnings growth",
                },
            ],
            "candidate_hypotheses": [
                {"company_name": "Example Holdings", "reason": "Possible industry gatekeeper"},
                {"company_name": "MN84GA", "reason": "product code, not a company"},
            ],
            "queries": ["industry gatekeeper rapid earnings growth public company"],
        }
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(reply)}}]})

    api = ResearchApis(
        root=tmp_path,
        budget=ApiBudget(tmp_path / "budget.db"),
        approved=True,
        ai_key="private-ai",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    plan = api.plan(
        "Ein Unternehmen, bei dem Kunden kaum noch eine Wahl haben. "
        "Die Gewinne wachsen im Eiltempo."
    )

    assert plan["candidate_hypotheses"] == ["Example Holdings"]
    assert any(
        '"Example Holdings"' in query and "investor relations" in query for query in plan["queries"]
    )
    assert all("MN84GA" not in query for query in plan["queries"])


def test_two_stage_models_route_reasoning_and_extraction_separately(tmp_path):
    from scanner.hebeltrader.detective.api_budget import ApiBudget
    from scanner.hebeltrader.detective.external_research import ResearchApis

    models = []

    def handler(request):
        payload = json.loads(request.content)
        models.append(payload["model"])
        user = json.loads(payload["messages"][1]["content"])
        if "teaser" in user:
            result = {
                "clues": [{"quote": "Teaser clue", "description": "Teaser clue"}],
                "queries": [],
                "candidate_hypotheses": [],
            }
        elif "candidates" in user:
            result = {
                "preferred_asset_id": "company:one",
                "reason": "The cited exclusivity clue is more specific.",
                "counterarguments": ["Publication time is not proven."],
                "missing_evidence": ["Primary issuer confirmation"],
            }
        else:
            result = {
                "company_name": "Example Corp",
                "identity_quote": "Example Corp operates cooling systems.",
                "ticker": None,
                "ticker_quote": None,
                "findings": [],
            }
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": json.dumps(result)}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 20},
            },
        )

    api = ResearchApis(
        root=tmp_path,
        budget=ApiBudget(tmp_path / "budget.db"),
        approved=True,
        ai_key="private-ai",
        extraction_model="gpt-4.1-mini-2025-04-14",
        reasoning_model="gpt-4.1-2025-04-14",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    api.plan("Teaser clue")
    api.annotate(
        {
            "url": "https://example.com",
            "text": "Example Corp operates cooling systems.",
            "source_kind": "news",
        }
    )
    review = api.review_candidates(
        [{"asset_id": "company:one", "identity": {"name": "Example Corp"}}]
    )

    assert models == [
        "gpt-4.1-2025-04-14",
        "gpt-4.1-mini-2025-04-14",
        "gpt-4.1-2025-04-14",
    ]
    assert review["preferred_asset_id"] == "company:one"
    assert api.calls_by_model == {
        "gpt-4.1-2025-04-14": 2,
        "gpt-4.1-mini-2025-04-14": 1,
    }
    assert api.usage_summary()["models"] == {
        "gpt-4.1-2025-04-14": {
            "input_tokens": 200,
            "output_tokens": 40,
            "estimated_usd": 0.00072,
        },
        "gpt-4.1-mini-2025-04-14": {
            "input_tokens": 100,
            "output_tokens": 20,
            "estimated_usd": 7.2e-05,
        },
    }


def test_unknown_model_is_rejected_before_network_or_budget(tmp_path):
    from scanner.hebeltrader.detective.api_budget import ApiBudget
    from scanner.hebeltrader.detective.external_research import ResearchApis

    budget = ApiBudget(tmp_path / "budget.db")
    with pytest.raises(ValueError, match="supported model"):
        ResearchApis(
            root=tmp_path,
            budget=budget,
            approved=True,
            ai_key="private",
            reasoning_model="unknown-expensive-model",
        )
    assert budget.summary()["reserved_cents"] == 0


def test_advisory_review_discards_non_string_preferred_asset_id(tmp_path):
    from scanner.hebeltrader.detective.api_budget import ApiBudget
    from scanner.hebeltrader.detective.external_research import ResearchApis

    api = ResearchApis(
        root=tmp_path,
        budget=ApiBudget(tmp_path / "budget.db"),
        approved=True,
        ai_key="private",
        client=httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    200,
                    json={
                        "choices": [
                            {
                                "message": {
                                    "content": json.dumps(
                                        {
                                            "preferred_asset_id": ["company:one"],
                                            "reason": "Malformed preference",
                                            "counterarguments": [],
                                            "missing_evidence": [],
                                        }
                                    )
                                }
                            }
                        ]
                    },
                )
            )
        ),
    )
    result = api.review_candidates([{"asset_id": "company:one", "identity": {"name": "Example"}}])
    assert result["preferred_asset_id"] is None


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
    assert api.budget.summary()["reserved_cents"] == 1


def test_legacy_fictional_per_call_reservations_are_repriced_once(tmp_path):
    import sqlite3

    from scanner.hebeltrader.detective.api_budget import ApiBudget

    path = tmp_path / "budget.db"
    with sqlite3.connect(path) as db:
        db.execute(
            "CREATE TABLE reservations "
            "(id INTEGER PRIMARY KEY, month TEXT, provider TEXT, cents INTEGER, at TEXT)"
        )
        db.execute(
            "INSERT INTO reservations(month,provider,cents,at) VALUES"
            "(strftime('%Y-%m','now'),'search',5,'x'),"
            "(strftime('%Y-%m','now'),'ai',10,'y')"
        )

    budget = ApiBudget(path, cap_cents=500)

    assert budget.summary()["reserved_cents"] == 2
    assert ApiBudget(path, cap_cents=500).summary()["reserved_cents"] == 2


def test_openai_429_exposes_only_whitelisted_safe_error_code(tmp_path):
    from scanner.hebeltrader.detective.api_budget import ApiBudget
    from scanner.hebeltrader.detective.external_research import ResearchApis

    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                429,
                json={
                    "error": {
                        "code": "insufficient_quota",
                        "type": "insufficient_quota",
                        "message": "private-ai-key and account details must not escape",
                    }
                },
            )
        )
    )
    api = ResearchApis(
        root=tmp_path,
        budget=ApiBudget(tmp_path / "budget.db"),
        approved=True,
        ai_key="private-ai-key",
        client=client,
    )

    with pytest.raises(ValueError, match="insufficient_quota"):
        api._json("Return an object.", {"teaser": "example"})

    archived = "".join(p.read_text() for p in tmp_path.glob("api-*.json"))
    assert '"provider_error_code": "insufficient_quota"' in archived
    assert "private-ai-key" not in archived
    assert "account details" not in archived


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


def test_ai_named_entity_without_ticker_or_clue_finding_is_not_a_stock_candidate(tmp_path):
    from datetime import UTC, datetime

    from test_primary_investigation import PublicFixture

    from scanner.hebeltrader.detective.api_budget import ApiBudget
    from scanner.hebeltrader.detective.external_research import ResearchApis
    from scanner.hebeltrader.detective.investigation import InvestigationRequest, Investigator

    now = datetime(2026, 10, 29, 12, tzinfo=UTC)
    api = ResearchApis(
        root=tmp_path / "api",
        budget=ApiBudget(tmp_path / "budget.db"),
        approved=False,
        ai_key="test",
    )
    api.plan = lambda text: {"clues": [], "candidate_hypotheses": [], "queries": []}
    doc = {
        "url": "https://example.com/article",
        "company_name": "Research Platform GmbH",
        "text": "Research Platform GmbH publishes a generic market article.",
        "source_kind": "news",
        "published_at": "2026-10-28T12:00:00Z",
        "retrieved_at": now.isoformat(),
        "ai_interpretation": {
            "company_name": "Research Platform GmbH",
            "identity_quote": "Research Platform GmbH publishes a generic market article.",
            "ticker": None,
            "findings": [],
        },
    }
    web = PublicFixture([doc])
    web.apis = api

    report = Investigator(tmp_path / "run", web=web, clock=lambda: now).analyze(
        InvestigationRequest(teaser_text="Ein unbekannter Branchenführer")
    )

    assert report["checked_candidates"] == []


def test_phase_budget_preserves_documents_for_peer_and_falsification_steps(tmp_path):
    from scanner.hebeltrader.detective.api_budget import ApiBudget
    from scanner.hebeltrader.detective.external_research import ApiPublicResearch, ResearchApis

    api = ResearchApis(
        root=tmp_path / "api", budget=ApiBudget(tmp_path / "budget.db"), approved=False
    )
    web = ApiPublicResearch(tmp_path / "sources", apis=api, allow_network=True)
    for phase, limit in [("discovery", 12), ("peers", 6), ("falsification", 3)]:
        web.set_phase(phase)
        assert web.can_fetch_new_document()
        web.phase_fetches[phase] = limit
        assert not web.can_fetch_new_document()
    assert sum(web.phase_fetches.values()) == 21


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
