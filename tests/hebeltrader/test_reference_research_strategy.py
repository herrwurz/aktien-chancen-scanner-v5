import json
from pathlib import Path

from test_primary_investigation import NOW, PublicFixture, packet

from scanner.hebeltrader.detective.investigation import (
    InvestigationRequest,
    Investigator,
    _clues,
    _queries,
)


def test_unnamed_acquisitions_and_financial_combination_precede_marketing_queries():
    data = json.loads(
        (Path(__file__).parents[2] / "data/hebeltrader/teaser-cases.json").read_text()
    )
    text = next(c["teaser_text"] for c in data["cases"] if c["case_id"] == "HT-001")
    queries = _queries(text, _clues(text, []), [])
    assert "acquisition" in queries[0].lower()
    assert "data center" in queries[0].lower() and "robotics" in queries[0].lower()
    assert any("gross margin" in q.lower() and "free cash flow" in q.lower() for q in queries)
    assert all(
        name not in " ".join(queries)
        for name in ["Analog Devices", "Lattice", "Empower", "Alif", "MN84GA"]
    )


def test_call_wkn_and_promotional_return_never_form_stock_search_query():
    text = (
        "Halbleiterkonzern mit Zukäufen für Robotik und Rechenzentren. "
        "Call WKN MN84GA mit 1.191 Prozent."
    )
    queries = _queries(text, _clues(text, []), [])
    assert queries
    assert "MN84GA" not in " ".join(queries)
    assert "1.191" not in " ".join(queries)


def test_all_initial_top3_get_explicit_counterevidence_queries(tmp_path):
    web = PublicFixture(packet())
    report = Investigator(tmp_path, clock=lambda: NOW, web=web).analyze(
        InvestigationRequest(
            teaser_text="Übernahmen von AlphaPower und BetaLogic.", publication_at=NOW
        )
    )
    questions = report["falsification"]["queries"]
    for row in report["candidates"]:
        assert any(row["identity"]["name"] in query and "cancelled" in query for query in questions)


def test_eight_unverified_names_do_not_end_discovery_before_remaining_queries(tmp_path):
    docs = packet()
    for index in (6, 7):
        docs.append(
            dict(
                docs[0],
                company_name=f"Company {index}",
                ticker=f"C{index}",
                url=f"https://issuer{index}.example/news",
                published_at=None,
            )
        )
    web = PublicFixture(docs)
    report = Investigator(tmp_path, clock=lambda: NOW, web=web).analyze(
        InvestigationRequest(
            teaser_text="Übernahmen von AlphaPower und BetaLogic.", publication_at=NOW
        )
    )
    assert len(report["search_queries"]) >= 2
    assert all(query in web.queries for query in report["search_queries"])
