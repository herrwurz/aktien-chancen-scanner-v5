from scanner.hebeltrader.detective.call_search import search_calls_for_report
from scanner.hebeltrader.detective.investigation import InvestigationRequest, Investigator
from scanner.hebeltrader.detective.prose_briefing import call_search_prose, prose_briefing
from scanner.hebeltrader.detective.workflow import compact_report, run_case


def test_prose_briefing_reads_like_chat_ranking():
    report = {
        "competition_mode": "out_of_competition",
        "decision": {"label": "Plausible Hypothese"},
        "identification": {"status": "hypothesis_top3"},
        "candidates": [
            {
                "identity": {"name": "Santacruz Silver", "ticker": "SCZ"},
                "evidence_score": 22,
                "ranking_reason": "Silberförderer mit Portfolio-Kern-Story",
                "supporting_clues": ["silber"],
                "unknown_clues": [{"type": "unknown", "value": "unknown"}],
            },
            {
                "identity": {"name": "Energy Fuels", "ticker": "UUUU"},
                "evidence_score": 12,
                "ranking_reason": "REE mit Terbium-Milestone",
            },
            {
                "identity": {"name": "IperionX", "ticker": "IPX"},
                "evidence_score": 18,
                "ranking_reason": "Titanbefestigungselemente",
            },
        ],
        "checked_candidates": [{"identity": {"name": "X"}}, {"identity": {"name": "Y"}}] * 3,
        "limitations": ["Keine Primärquelle aus dem Report", "UNKNOWN_INTERNAL_CODE"],
    }
    prose = prose_briefing(report)
    assert "Außer Konkurrenz" in prose
    assert "Top-Auswahl" in prose
    assert "Santacruz Silver" in prose
    assert "SCZ" in prose
    assert "Silberförderer" in prose
    assert "Weitere geprüfte Kandidaten" in prose
    assert "Energy Fuels" in prose
    assert "Kaufempfehlung" in prose
    assert "Failure-Code" not in prose
    assert "Working hypothesis" not in prose
    assert "Evidenz 22" not in prose
    assert "offen:" not in prose
    assert "unknown" not in prose.casefold()
    assert "Bitte noch prüfen" in prose
    assert "Keine Primärquelle" in prose
    assert "UNKNOWN_INTERNAL_CODE" not in prose


def test_run_case_includes_prose_field(tmp_path):
    from pathlib import Path

    report = run_case(
        Investigator(tmp_path),
        InvestigationRequest(
            teaser_text="Unbekannter Konzern mit Chancen.",
            competition_mode="out_of_competition",
            headline="OOC Prosa",
        ),
        documents=[],
    )
    assert "prose" in report
    assert "Außer Konkurrenz" in report["prose"]
    assert "Top-Auswahl" in report["prose"] or "keine belastbaren" in report["prose"].casefold()
    assert "Außer Konkurrenz" in Path(report["artifact_directory"], "report.md").read_text()
    assert "Außer" in compact_report(report)


def test_call_search_offline_abstains_with_prose():
    report = {
        "identification": {"status": "hypothesis_top3"},
        "candidates": [
            {"identity": {"name": "Energy Fuels", "ticker": "UUUU"}},
            {"identity": {"name": "Santacruz Silver", "ticker": "SCZ"}},
        ],
    }
    out = search_calls_for_report(report, web=None, enabled=True)
    assert out["is_investment_recommendation"] is False
    assert out["actual_hebeltrader_call_identified"] is False
    assert out["status"] == "abstain"
    assert len(out["underlyings"]) == 2
    assert "Call-Suche" in out["prose"]
    assert "Energy Fuels" in out["prose"]
    assert "Kaufempfehlung" in out["prose"]


def test_call_search_ranks_supplied_classic_calls_via_web_stub():
    class StubWeb:
        def search(self, query, limit=6):
            return [{"url": "https://issuer.example/call", "title": "Call WKN ABC123"}]

        def fetch(self, url):
            return {
                "url": url,
                "text": (
                    "WKN: ABC123\nBasispreis: 10 USD\nFälligkeit: 19.03.2027\n"
                    "Omega: 10.2\nBrief: 0.28 €\nCall Optionsschein"
                ),
                "retrieved_at": "2026-11-02T12:00:00+00:00",
            }

    report = {
        "identification": {"status": "hypothesis_top3"},
        "candidates": [{"identity": {"name": "Energy Fuels", "ticker": "UUUU"}}],
    }
    out = search_calls_for_report(report, web=StubWeb(), enabled=True, as_of="2026-11-02")
    assert out["status"] == "partial"
    assert out["underlyings"][0]["proposals"][0]["wkn"] == "ABC123"
    assert "ABC123" in out["prose"]


def test_call_search_prose_helper_mentions_ht_band():
    text = call_search_prose(
        {"status": "abstain", "reason": "no_classic_calls_found", "underlyings": []}
    )
    assert "4–6 Monate" in text
    assert "Call-Suche" in text
