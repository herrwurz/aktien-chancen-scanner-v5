"""Primary-evidence hardening: utility theme facts, ESA fingerprint, GC nuance, gaps."""

from scanner.hebeltrader.detective.investigation import (
    _apply_chart_signal_matrix,
    _apply_utility_clue_matrix,
    _clues,
    _leader_evidence_ready,
    _refresh_confirmed_specific_clues,
    has_material_research_source_gaps,
)
from scanner.hebeltrader.detective.schemas import SourceSpan
from scanner.hebeltrader.detective.utility_fingerprint import extract_utility_fingerprint

TEASER = (
    "Der Strom-Gigant: Diese Aktie profitiert vom unstillbaren KI-Hunger! "
    "Starke Quartalszahlen, eine milliardenschwere Investitionsoffensive und "
    "langfristige Abnahmeverträge mit Rechenzentrumsbetreibern. "
    "Charttechnisch hat sich zudem ein kraftvolles Golden Cross gebildet."
)


def test_utility_theme_nouns_become_fact_claims():
    clues = _clues(TEASER, [SourceSpan(source_id="teaser_text", start=0, end=len(TEASER))])
    fact_values = {c.value for c in clues if c.category == "fact_claims"}
    assert any("abnahmevertr" in (v or "") for v in fact_values)
    assert any("investitionsoffensive" in (v or "") for v in fact_values)
    assert any("rechenzentrum" in (v or "") for v in fact_values)


def test_chip_teaser_rechenzentren_does_not_spawn_utility_theme_facts():
    chip = (
        "Halbleiter-Schwergewicht bei KI-Rechenzentren und Robotik. Mit der Übernahme von Empower."
    )
    from scanner.hebeltrader.detective.investigation import _utility_theme_fact_clues

    assert _utility_theme_fact_clues(chip) == []


def test_fingerprint_matrix_confirms_multiple_specific_fact_claims():
    clues = _clues(TEASER, [SourceSpan(source_id="teaser_text", start=0, end=len(TEASER))])
    fact_clues = [c for c in clues if c.category == "fact_claims"]
    ranked = [
        {
            "hard_contradictions": [],
            "utility_fingerprint": {
                "has_offtake": True,
                "has_data_center_link": True,
                "capex_billions": 100.0,
                "components": 3,
                "bonus": 70,
            },
            "chart": {
                "status": "ok",
                "golden_cross": True,
                "golden_cross_sma": False,
                "golden_cross_ema": True,
            },
            "evidence_matrix": [
                {
                    "clue_id": c.clue_id,
                    "status": "unknown",
                    "quote": c.quote,
                    "category": c.category,
                    "evidence_cluster_ids": [],
                }
                for c in fact_clues
            ]
            + [
                {
                    "clue_id": "ai:gc",
                    "status": "unknown",
                    "quote": "Charttechnisch hat sich zudem ein kraftvolles Golden Cross gebildet",
                    "category": "semantic_fact",
                    "evidence_cluster_ids": [],
                }
            ],
            "confirmed_specific_clues": [],
            "counterarguments": [],
        }
    ]
    _apply_utility_clue_matrix(ranked, TEASER)
    _apply_chart_signal_matrix(ranked, TEASER)
    _refresh_confirmed_specific_clues(ranked, clues)
    assert len(ranked[0]["confirmed_specific_clues"]) >= 2
    assert _leader_evidence_ready(ranked[0], clues)
    assert any("EMA" in note for note in ranked[0]["counterarguments"])
    gc = next(c for c in ranked[0]["evidence_matrix"] if c["clue_id"] == "ai:gc")
    assert gc["reason"] == "eod_golden_cross_ema_only_within_20d_pit"


def test_esa_and_contracted_load_count_as_offtake():
    text = (
        "Dominion Energy Virginia now has 12.2 GW under electric service agreements "
        "and 54.9 GW of data center capacity in various stages of contracting. "
        "Incremental contracted load supports the $65 billion capital investment plan."
    )
    fp = extract_utility_fingerprint(text)
    assert fp.has_offtake
    assert fp.has_data_center_link
    assert fp.capex_billions == 65


def test_ema_only_golden_cross_scores_less_than_sma():
    from scanner.hebeltrader.detective.chart_check import chart_score
    from scanner.hebeltrader.detective.market_screen import match_score

    base = {
        "above_gd50": True,
        "above_gd200": True,
        "gd200_rising": True,
        "return_1y_pct": 10,
        "near_high_pct": -2,
        "breakout": False,
        "golden_cross": True,
        "golden_cross_sma": False,
        "golden_cross_ema": True,
    }
    sma = {**base, "golden_cross_sma": True, "golden_cross_ema": False}
    assert chart_score(sma) > chart_score(base)
    assert match_score(sma, ["golden_cross"]) > match_score(base, ["golden_cross"])


def test_fingerprint_prefers_issuer_primary_over_secondary_news():
    from scanner.hebeltrader.detective.utility_fingerprint import (
        apply_utility_fingerprints,
        fingerprint_from_documents,
    )

    secondary_only = [
        {
            "source_kind": "news",
            "title": "Wire",
            "text": "Utility signed offtake with data center; $40 billion capital plan.",
        }
    ]
    with_primary = secondary_only + [
        {
            "source_kind": "issuer",
            "title": "IR",
            "text": "We executed take-or-pay ESAs with hyperscale data centers.",
        }
    ]
    fp = fingerprint_from_documents(with_primary)
    assert fp.has_offtake and fp.has_data_center_link
    # Capex only on secondary must not override a stronger primary combo preference
    # when primary already has 2+ components — capex may still come from all-docs
    # fallback only when primary is thin.
    ranked = [
        {"asset_id": "sec", "evidence_score": 0, "hard_contradictions": []},
        {"asset_id": "pri", "evidence_score": 0, "hard_contradictions": []},
    ]
    apply_utility_fingerprints(
        ranked,
        {"sec": secondary_only, "pri": with_primary},
        teaser_text="US-Versorger Abnahmeverträge Rechenzentren",
    )
    by_id = {r["asset_id"]: r for r in ranked}
    assert by_id["pri"]["utility_fingerprint"]["provenance"] == "primary"
    assert by_id["sec"]["utility_fingerprint"]["provenance"] == "secondary_only"
    assert (
        by_id["pri"]["utility_fingerprint"]["bonus"] > by_id["sec"]["utility_fingerprint"]["bonus"]
    )


def test_peer_budget_exhaustion_is_not_material_source_gap_with_primary_docs():
    errors = [
        {"query": "peer falsification", "error": "network disabled or request budget exhausted"},
        {"query": "earnings date", "error": "request budget exhausted"},
    ]
    assert (
        has_material_research_source_gaps(errors, primary_documents=0, offline=False, documents=87)
        is False
    )
    assert (
        has_material_research_source_gaps(errors, primary_documents=0, offline=False, documents=0)
        is True
    )
    assert (
        has_material_research_source_gaps(
            [{"url": "x", "error": "HTTP 500"}],
            primary_documents=2,
            offline=False,
            documents=10,
        )
        is True
    )
