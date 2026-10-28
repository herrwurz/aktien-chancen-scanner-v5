from test_primary_investigation import NOW, PublicFixture, packet

from scanner.hebeltrader.detective.investigation import (
    InvestigationRequest,
    Investigator,
    _clues,
    _queries,
)


def queries(text):
    return _queries(text, _clues(text, []), [])


def test_concrete_events_and_financial_business_model_receive_targeted_queries():
    rows = queries(
        "Landmaschinenkonzern mit strategischer Partnerschaft und Großauftrag. "
        "Die Prognose wurde angehoben. Wiederkehrende Softwareerlöse steigen. "
        "Der Gewinn je Aktie übertraf die Analystenerwartungen."
    )
    assert any("partnership" in q and "agricultural" in q for q in rows)
    assert any("contract" in q for q in rows)
    assert any("guidance" in q for q in rows)
    assert any("recurring revenue" in q for q in rows)
    assert any("earnings per share" in q and "expectations" in q for q in rows)
    assert len(rows) <= 8
    assert all(name not in " ".join(rows) for name in ["Deere", "CNH", "AGCO", "Caterpillar"])


def test_rumours_are_not_searched_as_completed_acquisitions():
    rows = queries("Übernahmespekulationen um einen Halbleiterkonzern.")
    assert "rumor" in rows[0]
    assert "completed" not in " ".join(rows)


def test_chart_context_is_searched_only_when_present():
    assert not any("200 day" in q for q in queries("Neue Produkte und Umsatzwachstum."))
    rows = queries("Landmaschinenkonzern mit Softwareerlösen. Aktie verteidigt die 200-Tage-Linie.")
    assert any("200 day" in q for q in rows)


def test_peer_discovery_can_find_previously_missing_countercandidates(tmp_path):
    docs = packet()

    class Peers(PublicFixture):
        def search(self, query, limit=10):
            self.queries.append(query)
            selected = self.docs if "peer group" in query else self.docs[:1]
            return [{"url": d["url"]} for d in selected]

    report = Investigator(tmp_path, clock=lambda: NOW, web=Peers(docs)).analyze(
        InvestigationRequest(
            teaser_text="Übernahmen von AlphaPower und BetaLogic.", publication_at=NOW
        )
    )
    assert report["peer_comparison"]["queries"]
    assert len(report["checked_candidates"]) == 6
    assert report["countercandidate_count"] == 5
    assert report["candidates"][0]["identity"]["name"] == "Company 5"
    assert all("Company 5" in q or "Company" in q for q in report["falsification"]["queries"])


def test_offline_analysis_never_claims_active_peer_discovery(tmp_path):
    report = Investigator(tmp_path, clock=lambda: NOW).analyze(
        InvestigationRequest(
            teaser_text="Übernahmen von AlphaPower und BetaLogic.", publication_at=NOW
        ),
        documents=packet()[:1],
    )
    assert report["peer_comparison"]["status"] == "not_performed_offline"
    assert report["peer_comparison"]["queries"] == []
    assert report["countercandidate_count"] == 0
    assert report["identification"]["status"] == "not_identified"


def test_operating_cash_flow_is_not_relabelled_as_free_cash_flow():
    rows = queries("Landmaschinenbauer mit Milliarden an operativem Cashflow.")
    assert any("operating cash flow" in q for q in rows)
    assert not any("free cash flow" in q for q in rows)


def test_analyst_ratings_without_numeric_results_still_receive_targeted_query():
    assert any(
        "analyst rating" in q for q in queries("Softwarekonzern mit neuen Analystenbewertungen.")
    )
