"""Search planning and discovery breadth for vague German teasers (synthetic stubs)."""

from datetime import UTC, datetime
from types import SimpleNamespace

from scanner.hebeltrader.detective.investigation import (
    InvestigationRequest,
    Investigator,
    _entities,
)
from scanner.hebeltrader.detective.research_plan import build_queries

NOW = datetime(2026, 10, 29, 12, tzinfo=UTC)
TEASER = (
    "Der heimliche Herrscher über die globale Chipindustrie! Stellen Sie sich vor, ein "
    "Unternehmen wird in der Branche so unverzichtbar, dass seine Kunden kaum noch eine "
    "Wahl haben. Die Gewinne wachsen im Eiltempo. Mit dem passenden Optionsschein Call "
    "warten bis zu 1.269 Prozent."
)


def test_dominance_teaser_gets_specific_english_queries_without_raw_headline():
    queries = build_queries(TEASER, [], [])
    assert any("semiconductor" in q and "no alternative" in q for q in queries)
    assert any("sole" in q for q in queries)
    assert not any("Herrscher" in q for q in queries)


def test_chip_dominance_teaser_covers_design_software_and_other_layers():
    queries = build_queries(TEASER, [], [])
    assert any("chip design software" in q for q in queries)
    assert any("equipment" in q for q in queries)
    assert any("foundry" in q for q in queries)
    assert len(queries) <= 10


def test_generic_headline_without_sector_keeps_raw_fallback():
    assert build_queries("Hier steckt eine irrwitzige Turnaround-Chance drin!", [], []) == [
        "Hier steckt eine irrwitzige Turnaround-Chance drin! company investor relations"
    ]


def test_german_common_noun_after_preposition_is_not_a_company():
    assert "System" not in _entities("Hier arbeitet jemand mit System.")
    assert "Hier" not in _entities(TEASER)
    assert "AlphaPower" in _entities("Übernahme von AlphaPower")


class StubWeb:
    phase = "input"

    def __init__(self):
        self.apis = SimpleNamespace(
            ai_key="k",
            search_calls=0,
            ai_calls=0,
            budget=SimpleNamespace(summary=lambda: {}),
            plan=lambda text: {
                "clues": [],
                "candidate_hypotheses": ["Foo Litho"],
                "queries": ["semiconductor sole supplier"],
            },
            review_candidates=lambda rows: {
                "status": "ok",
                "changes_deterministic_ranking": False,
            },
        )
        self.hits = {}
        self.snippets = 0

    def set_phase(self, phase):
        self.phase = phase

    def search(self, query, limit=10):
        rows = [
            {"url": f"https://news{i}.example/a", "title": f"Foo Litho item {i}", "content": "x"}
            for i in range(6)
        ]
        self.hits = {row["url"]: row for row in rows}
        return rows

    def fetch_many(self, urls):
        return [self._doc(url, "page") for url in urls], []

    def snippet_document(self, url):
        self.snippets += 1
        return self._doc(url, "Foo Litho is the sole supplier of lithography systems.")

    def _doc(self, url, text):
        return {
            "url": url,
            "title": "Foo Litho",
            "text": text,
            "source_kind": "search_snippet",
            "retrieved_at": NOW.isoformat(),
            "raw_sha256": "0" * 64,
        }


def test_discovery_uses_snippets_planner_names_and_undated_documents(tmp_path):
    web = StubWeb()
    report = Investigator(tmp_path, web=web, clock=lambda: NOW).analyze(
        InvestigationRequest(teaser_text=TEASER)
    )
    assert web.snippets > 0
    assert report["research_diagnostics"]["documents"] > 3
    assert report["checked_candidates"][0]["identity"]["name"] == "Foo Litho"
    assert any(
        s["facts"]["published_at_assumed_retrieval"]
        for s in report["checked_candidates"][0]["sources"]
    )
    assert report["identification"]["status"] == "not_identified"


def test_planner_uses_english_search_terms_for_hypothesis_verification(tmp_path):
    import json

    import httpx

    from scanner.hebeltrader.detective.api_budget import ApiBudget
    from scanner.hebeltrader.detective.external_research import ResearchApis

    reply = {
        "clues": [
            {
                "quote": "Kunden kaum noch eine Wahl",
                "description": "Kunden haben keine Alternative",
                "search_terms": "sole supplier market share monopoly",
            }
        ],
        "candidate_hypotheses": [{"company_name": "Example Litho", "reason": "bottleneck"}],
        "queries": [],
    }
    api = ResearchApis(
        root=tmp_path,
        budget=ApiBudget(tmp_path / "budget.db"),
        approved=True,
        ai_key="k",
        client=httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    200, json={"choices": [{"message": {"content": json.dumps(reply)}}]}
                )
            )
        ),
    )
    plan = api.plan("Unternehmen, dessen Kunden kaum noch eine Wahl haben.")
    assert plan["queries"] == ['"Example Litho" sole supplier market share monopoly']


def test_company_name_variants_merge():
    from scanner.hebeltrader.detective.investigation import canonical_company

    assert canonical_company("ASML Holding N.V.") == canonical_company("ASML")
    assert canonical_company("ASML Holding NV") == canonical_company("ASML")
    assert canonical_company("TSMC") == canonical_company(
        "Taiwan Semiconductor Manufacturing Company (TSMC)"
    )


def test_planner_prompt_requests_value_chain_spread_and_accepts_six_seeds(tmp_path):
    import json

    import httpx

    from scanner.hebeltrader.detective.api_budget import ApiBudget
    from scanner.hebeltrader.detective.external_research import ResearchApis

    seen = []
    reply = {
        "clues": [],
        "candidate_hypotheses": [{"company_name": f"Layer Co {i}"} for i in range(8)],
        "queries": [],
    }

    def handler(request):
        seen.append(json.loads(request.content)["messages"][0]["content"])
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(reply)}}]})

    api = ResearchApis(
        root=tmp_path,
        budget=ApiBudget(tmp_path / "budget.db"),
        approved=True,
        ai_key="k",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    plan = api.plan("Herrscher der Chipindustrie")
    assert "DIFFERENT layers" in seen[0]
    assert len(plan["candidate_hypotheses"]) == 6
