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


def test_prose_briefing_strips_legacy_hashes_scores_and_codes():
    """Loaded Lockheed/RTX-style reports must not dump hashes or tech jargon."""
    hash_a = "d4dcb0367842a2f0eeab900d63847bd31c8d6bd9e58a2c4e16f43ef29868ec1d"
    hash_b = "72dd5bf38c35532f08dbff3f84bea25e9b52a494b4c3b630c5db51084bfb58a8"
    hash_ai = "ai:1c5b5e313e1162ec4f5acf179c80753b2c85b63dd4f34e75fb1720c83aeefdde"
    report = {
        "competition_mode": "official",
        "decision": {"label": "Plausible Hypothese"},
        "identification": {"status": "hypothesis_top3"},
        "candidates": [
            {
                "identity": {"name": "Lockheed Martin", "ticker": "LMT"},
                "evidence_score": 56,
                "ranking_reason": (
                    f"Rang 1: 0 bestätigte Kernhinweise, 0 harte Widersprüche, Score 56; "
                    f"Widersprüche zuerst, danach spezifische Primärevidenz. "
                    f"6 vorläufige KI-Belegstellen; keine unabhängige Primärbestätigung; "
                    f"Gegenargument: Unbestätigte Hinweise in der Matrix prüfen; "
                    f"offen: {hash_a}, {hash_b}, {hash_ai}."
                ),
                "cited_findings": [{"status": "supported", "usable_for_ranking": True}] * 6,
                "unknown_clues": [hash_a, hash_b, hash_ai],
                "counterarguments": ["Unbestätigte Hinweise in der Matrix prüfen"],
                "hypothesis_reasons": [f"confirmed:{hash_a}", "category:defense"],
            },
            {
                "identity": {"name": "RTX", "ticker": "RTX"},
                "evidence_score": 46,
                "ranking_reason": (
                    f"Rang 2: 0 bestätigte Kernhinweise, 0 harte Widersprüche, Score 46; "
                    f"offen: {hash_a}."
                ),
                "cited_findings": [{"status": "supported", "usable_for_ranking": True}] * 2,
            },
            {
                "identity": {"name": "General Dynamics", "ticker": "GD"},
                "evidence_score": 24,
                "ranking_reason": "Rang 3: Score 24; offen: " + hash_b,
            },
        ],
        "limitations": [
            "ai_interpretation_requires_manual_verification",
            "fewer_than_five_countercandidates",
            "insufficient_specific_primary_evidence",
            "listed_underlying_identity_unverified",
        ],
        # Stale stored prose from the old Ranking / Working-hypothesis format.
        "prose": (
            "### Ranking\n1. Lockheed Martin — Confidence mittel–hoch, Evidenz 56.\n"
            "### Working hypothesis\n`RTX`.\n### Offene Punkte\n"
            "- ai_interpretation_requires_manual_verification\n"
        ),
    }
    prose = prose_briefing(report)
    assert "### Ranking" not in prose
    assert "Working hypothesis" not in prose
    assert "Offene Punkte" not in prose
    assert "Confidence" not in prose
    assert "Evidenz 56" not in prose
    assert "Score 56" not in prose
    assert "offen:" not in prose
    assert hash_a not in prose
    assert hash_b not in prose
    assert hash_ai not in prose
    assert "ai_interpretation_requires_manual_verification" not in prose
    assert "fewer_than_five_countercandidates" not in prose
    assert "Top-Auswahl" in prose
    assert "Lockheed Martin" in prose
    assert "Bitte noch prüfen" in prose
    assert "manuell geprüft" in prose
    assert "Primärbelege" in prose
    assert "Gegenkandidaten" in prose
    # Human counterargument may remain; machine confirmed:hash must not.
    assert f"confirmed:{hash_a}" not in prose
    assert "Unbestätigte Hinweise" in prose or "vorläufige Quellenhinweise" in prose


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
