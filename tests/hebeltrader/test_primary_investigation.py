"""Synthetic anti-anchoring regressions; never independent accuracy measurements."""

from datetime import UTC, datetime

from scanner.hebeltrader.detective.investigation import InvestigationRequest, Investigator

NOW = datetime(2026, 10, 28, 12, tzinfo=UTC)


def packet():
    docs = []
    for index in range(6):
        company = f"Company {index}"
        text = (
            f"{company} acquired AlphaPower and BetaLogic."
            if index == 5
            else (
                f"{company} develops chips and artificial intelligence, "
                "and discusses AlphaPower and BetaLogic."
            )
        )
        docs.append(
            {
                "company_name": company,
                "ticker": f"C{index}",
                "url": f"https://issuer{index}.example/release",
                "title": company + " company release",
                "text": text,
                "source_kind": "issuer",
                "published_at": "2026-10-25T12:00:00+00:00",
                "retrieved_at": NOW.isoformat(),
            }
        )
    return docs


def test_specific_acquisitions_outrank_generic_sector_and_compare_five_alternatives(tmp_path):
    request = InvestigationRequest(
        teaser_text="Chipkonzern mit Übernahmen von AlphaPower und BetaLogic.",
        publication_at=NOW,
        headline="Unbekannter Konzern",
        publisher="Synthetic fixture",
    )
    report = Investigator(tmp_path, clock=lambda: NOW).analyze(request, documents=packet())
    assert report["countercandidate_count"] == 5
    assert len(report["checked_candidates"]) == 6
    assert report["candidates"][0]["identity"]["name"] == "Company 5"
    assert report["identification"]["score_is_probability"] is False
    assert report["derivative_candidate"]["status"] == "not_identified"
    assert report["falsification"]["status"] == "not_performed_offline"
    assert report["identification"]["status"] == "not_identified"  # no active falsification yet


def test_post_teaser_evidence_cannot_confirm_claims(tmp_path):
    docs = packet()
    docs[-1]["published_at"] = "2026-10-29T00:00:00+00:00"
    request = InvestigationRequest(
        teaser_text="Übernahmen von AlphaPower und BetaLogic.", publication_at=NOW
    )
    report = Investigator(tmp_path, clock=lambda: NOW).analyze(request, documents=docs)
    assert report["identification"]["status"] == "not_identified"
    assert all(c["identity"]["name"] != "Company 5" for c in report["checked_candidates"])


def test_sparse_candidates_never_become_identified(tmp_path):
    report = Investigator(tmp_path, clock=lambda: NOW).analyze(
        InvestigationRequest(
            teaser_text="Übernahmen von AlphaPower und BetaLogic.", publication_at=NOW
        ),
        documents=packet()[-1:],
    )
    assert report["identification"]["status"] == "not_identified"
    assert report["countercandidate_count"] == 0
    assert "fewer_than_five_countercandidates" in report["limitations"]


def test_promotional_return_does_not_identify_stock_or_warrant(tmp_path):
    report = Investigator(tmp_path, clock=lambda: NOW).analyze(
        InvestigationRequest(
            teaser_text="Bis zu plus 1.191 Prozent Renditechance!", publication_at=NOW
        ),
        documents=packet(),
    )
    assert report["identification"]["status"] == "not_identified"
    assert not any(c["confirmed_specific_clues"] for c in report["checked_candidates"])
    assert report["derivative_candidate"]["status"] == "not_identified"


class PublicFixture:
    def __init__(self, docs):
        self.docs = docs
        self.queries = []

    def search(self, query, limit=10):
        self.queries.append(query)
        return [{"url": d["url"]} for d in self.docs]

    def fetch(self, url):
        return next(d for d in self.docs if d["url"] == url)


def test_active_comparison_can_identify_and_freeze_without_probabilities(tmp_path):
    web = PublicFixture(packet())
    report = Investigator(tmp_path, clock=lambda: NOW, web=web).analyze(
        InvestigationRequest(
            teaser_text="Übernahmen von AlphaPower und BetaLogic.", publication_at=NOW
        )
    )
    assert report["identification"]["status"] == "identified"
    assert report["countercandidate_count"] == 5
    assert report["falsification"]["queries"]
    assert any("cancelled" in query for query in web.queries)
    assert (tmp_path / "analyses" / report["run_id"] / "ranking.json").is_file()


def test_explicit_acquisition_denial_is_a_hard_counterargument(tmp_path):
    docs = packet()
    docs[-1]["text"] = "Company 5 did not acquire AlphaPower and never acquired BetaLogic."
    report = Investigator(tmp_path, clock=lambda: NOW, web=PublicFixture(docs)).analyze(
        InvestigationRequest(
            teaser_text="Übernahmen von AlphaPower und BetaLogic.", publication_at=NOW
        )
    )
    bad = next(c for c in report["checked_candidates"] if c["identity"]["name"] == "Company 5")
    assert bad["hard_contradictions"]
    assert report["identification"]["status"] == "not_identified"


def test_minority_investment_is_not_confirmed_as_a_takeover(tmp_path):
    docs = packet()
    docs[-1]["text"] = "Company 5 invested minority stakes in AlphaPower and BetaLogic."
    report = Investigator(tmp_path, clock=lambda: NOW, web=PublicFixture(docs)).analyze(
        InvestigationRequest(
            teaser_text="Übernahmen von AlphaPower und BetaLogic.", publication_at=NOW
        )
    )
    leader = next(c for c in report["checked_candidates"] if c["identity"]["name"] == "Company 5")
    assert not leader["confirmed_specific_clues"]
    assert report["identification"]["status"] == "not_identified"


def test_financial_comparison_requires_the_same_explicit_quarter(tmp_path):
    docs = packet()
    docs[-1]["text"] = "Q3 2026: Company 5 Umsatz 20 Prozent. Company 5 Gewinn 30 Prozent."
    request = InvestigationRequest(
        teaser_text="Q3 2026: Umsatz 20 Prozent. Gewinn 30 Prozent.", publication_at=NOW
    )
    report = Investigator(tmp_path, clock=lambda: NOW, web=PublicFixture(docs)).analyze(request)
    candidate = next(
        c for c in report["checked_candidates"] if c["identity"]["name"] == "Company 5"
    )
    assert len(candidate["confirmed_specific_clues"]) == 2
    docs[-1]["text"] = "Q2 2026: Company 5 Umsatz 20 Prozent. Company 5 Gewinn 30 Prozent."
    different = Investigator(tmp_path, clock=lambda: NOW, web=PublicFixture(docs)).analyze(request)
    candidate = next(
        c for c in different["checked_candidates"] if c["identity"]["name"] == "Company 5"
    )
    assert not candidate["confirmed_specific_clues"]


def test_issuer_page_about_a_competitors_deal_does_not_confirm_issuers_deal(tmp_path):
    docs = packet()
    docs[-1]["text"] = "Other Corporation acquired AlphaPower and BetaLogic."
    report = Investigator(tmp_path, clock=lambda: NOW, web=PublicFixture(docs)).analyze(
        InvestigationRequest(
            teaser_text="Übernahmen von AlphaPower und BetaLogic.", publication_at=NOW
        )
    )
    candidate = next(
        c for c in report["checked_candidates"] if c["identity"]["name"] == "Company 5"
    )
    assert not candidate["confirmed_specific_clues"]


def test_historical_blind_refuses_live_search_and_late_archive(tmp_path):
    import pytest

    request = InvestigationRequest(
        teaser_text="Übernahmen von AlphaPower und BetaLogic.", publication_at=NOW
    )
    with pytest.raises(ValueError, match="archived"):
        Investigator(tmp_path, clock=lambda: NOW, web=PublicFixture(packet())).analyze(
            request, historical_blind=True
        )
    docs = packet()
    for doc in docs:
        doc["retrieved_at"] = "2026-10-29T00:00:00+00:00"
    report = Investigator(tmp_path, clock=lambda: NOW).analyze(
        request, documents=docs, historical_blind=True
    )
    assert report["checked_candidates"] == []
    assert report["identification"]["status"] == "not_identified"


def test_distinctive_exclusivity_clue_outweighs_generic_growth_clue():
    from scanner.hebeltrader.detective.investigation import clue_specificity

    assert clue_specificity("Kunden haben kaum eine Wahl; einzige verfügbare Technologie") > (
        clue_specificity("Gewinne wachsen stark") * 2
    )


def test_equal_candidate_scores_are_labelled_as_tie():
    from scanner.hebeltrader.detective.investigation import apply_tie_labels

    rows = [{"evidence_score": 0}, {"evidence_score": 0}, {"evidence_score": -1}]
    assert apply_tie_labels(rows) is True
    assert [row.get("rank_label") for row in rows] == [
        "Gleichstand Rang 1",
        "Gleichstand Rang 1",
        None,
    ]


def test_current_hypothesis_can_rank_provider_evidence_without_claiming_historical_eligibility():
    from scanner.hebeltrader.detective.investigation import finding_timing

    document = {
        "url": "https://issuer.example/results",
        "source_class": "B",
        "source_kind": "tavily_extract",
        "published_at": None,
        "retrieved_at": NOW.isoformat(),
    }

    timing = finding_timing(document, NOW, current_hypothesis=True)
    assert timing == {
        "temporal_eligibility": "current_hypothesis_only",
        "usable_for_ranking": True,
    }
    assert finding_timing(document, NOW, current_hypothesis=False) == {
        "temporal_eligibility": "uncertain",
        "usable_for_ranking": False,
    }


def test_source_classes_distinguish_original_extract_and_search_snippet():
    from scanner.hebeltrader.detective.investigation import source_class

    assert source_class({"source_kind": "issuer"}) == "A"
    assert source_class({"source_kind": "regulatory"}) == "A"
    assert source_class({"source_kind": "tavily_extract"}) == "B"
    assert source_class({"source_kind": "search_snippet"}) == "C"
    assert source_class({"source_kind": "news"}) == "D"


def test_other_company_financials_never_confirm_page_owners_financials(tmp_path):
    docs = packet()
    docs[-1]["text"] = "Other Corporation Q3 2026: Umsatz 20 Prozent. Gewinn 30 Prozent."
    report = Investigator(tmp_path, clock=lambda: NOW, web=PublicFixture(docs)).analyze(
        InvestigationRequest(
            teaser_text="Q3 2026: Umsatz 20 Prozent. Gewinn 30 Prozent.", publication_at=NOW
        )
    )
    candidate = next(
        c for c in report["checked_candidates"] if c["identity"]["name"] == "Company 5"
    )
    assert not candidate["confirmed_specific_clues"]


def test_undated_empty_alternatives_cannot_fill_five_countercandidate_gate(tmp_path):
    docs = packet()
    for doc in docs[:-1]:
        doc["published_at"] = None
        doc["text"] = "Nothing relevant here."
    report = Investigator(tmp_path, clock=lambda: NOW, web=PublicFixture(docs)).analyze(
        InvestigationRequest(
            teaser_text="Übernahmen von AlphaPower und BetaLogic.", publication_at=NOW
        )
    )
    assert report["countercandidate_count"] == 0
    assert report["identification"]["status"] == "not_identified"


def test_comparison_sentence_does_not_attribute_other_company_numbers(tmp_path):
    docs = packet()
    for doc in docs[:-1]:
        doc["text"] += " Q3 2026: Umsatz 20 Prozent."
    docs[-1]["text"] = (
        "Q3 2026: Company 5 compares Other Corporation Umsatz 20 Prozent. "
        "Company 5 compares Other Corporation Gewinn 30 Prozent."
    )
    report = Investigator(tmp_path, clock=lambda: NOW, web=PublicFixture(docs)).analyze(
        InvestigationRequest(
            teaser_text="Q3 2026: Umsatz 20 Prozent. Gewinn 30 Prozent.", publication_at=NOW
        )
    )
    candidate = next(
        c for c in report["checked_candidates"] if c["identity"]["name"] == "Company 5"
    )
    assert not candidate["confirmed_specific_clues"]
    assert report["identification"]["status"] == "not_identified"


def test_online_search_failure_is_not_reported_as_offline(tmp_path):
    class Blocked:
        discovery_errors = [{"source": "bing_rss", "error": "robots denied or unavailable"}]
        attempts = []
        remaining = 37

        def search(self, query, limit=10):
            raise ValueError("robots denied or unavailable")

    report = Investigator(tmp_path, clock=lambda: NOW, web=Blocked()).analyze(
        InvestigationRequest(teaser_text="KI-Kühltechnik und wiederkehrende Digitalerlöse.")
    )
    assert report["research_mode"] == "public_web"
    assert report["falsification"]["status"] == "not_performed_no_candidates"
    assert report["decision"]["status"] == "research_unavailable"
    assert report["research_diagnostics"]["documents"] == 0
    assert report["research_diagnostics"]["documents_with_company_identity"] == 0
    assert report["research_diagnostics"]["source_errors"]
    assert report["identification"]["status"] == "not_identified"


def test_successful_empty_online_search_remains_distinct_from_source_failure(tmp_path):
    report = Investigator(tmp_path, clock=lambda: NOW, web=PublicFixture([])).analyze(
        InvestigationRequest(teaser_text="Unbekannter Technologiekonzern.")
    )
    assert report["falsification"]["status"] == "not_performed_no_candidates"
    assert report["decision"]["status"] == "insufficient_evidence"


def test_issuer_legal_abbrev_and_html_entities_still_confirm_named_acquisition(tmp_path):
    docs = packet()
    docs[-1]["company_name"] = "Thermo Fisher Scientific"
    docs[-1]["ticker"] = "TMO"
    docs[-1]["text"] = (
        "Thermo Fisher Scientific Inc. (&#8220;Thermo Fisher&#8221;) issued a press release "
        "announcing the completion of its acquisition of Clario Holdings, Inc."
    )
    report = Investigator(tmp_path, clock=lambda: NOW).analyze(
        InvestigationRequest(
            teaser_text="Mit der Übernahme von Clario baut der Konzern seine Position aus.",
            publication_at=NOW,
        ),
        documents=docs,
    )
    leader = next(c for c in report["checked_candidates"] if c["identity"]["ticker"] == "TMO")
    assert leader["confirmed_specific_clues"]
    assert any(
        cell.get("quote") == "Clario" and cell.get("status") == "confirmed"
        for cell in leader["evidence_matrix"]
    )


def test_sec_issuer_anaphora_confirms_second_named_acquisition(tmp_path):
    docs = packet()
    docs[-1]["company_name"] = "Thermo Fisher Scientific"
    docs[-1]["ticker"] = "TMO"
    docs[-1]["source_kind"] = "regulator"
    docs[-1]["text"] = (
        "On March 24, 2026, the company acquired Clario Holdings, Inc. "
        "On September 1, 2025, the company acquired, within the Life Sciences Solutions "
        "segment, our filtration and separation business from Solventum Corporation."
    )
    report = Investigator(tmp_path, clock=lambda: NOW).analyze(
        InvestigationRequest(
            teaser_text=(
                "Mit der Übernahme von Clario und der Übernahme von Solventum "
                "baut der Konzern seine Position aus."
            ),
            publication_at=NOW,
        ),
        documents=docs,
    )
    leader = next(c for c in report["checked_candidates"] if c["identity"]["ticker"] == "TMO")
    quotes = {
        cell.get("quote")
        for cell in leader["evidence_matrix"]
        if cell.get("status") == "confirmed" and cell.get("category") == "fact_claims"
    }
    assert quotes >= {"Clario", "Solventum"}
    assert len(leader["confirmed_specific_clues"]) >= 2
    # Offline packet scans stay not_identified (falsification/live gate), but the
    # two named primary clues already yield a ranked plausible hypothesis.
    assert report["decision"]["status"] == "plausible_hypothesis"
    assert report["identification"]["status"] == "not_identified"
