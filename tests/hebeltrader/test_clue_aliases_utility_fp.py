"""DE→EN clue aliases and utility offtake/capex fingerprints."""

from scanner.hebeltrader.detective.clue_aliases import clue_search_terms, term_pattern
from scanner.hebeltrader.detective.investigation import _evidence, _mark_chart_comparison_evidence
from scanner.hebeltrader.detective.schemas import AtomicClue
from scanner.hebeltrader.detective.utility_fingerprint import (
    apply_utility_fingerprints,
    extract_utility_fingerprint,
    teaser_wants_utility_fingerprint,
    utility_fingerprint_score,
)


def test_rechenzentrum_aliases_match_english_data_center():
    terms = clue_search_terms("rechenzentrumsbetreibern")
    assert "data center" in terms
    assert term_pattern("rechenzentrumsbetreibern").search(
        "We signed a long-term contract with a hyperscale data center operator."
    )


def test_evidence_confirms_german_investment_clue_on_english_ir():
    clue = AtomicClue(
        clue_id="c1",
        category="fact_claims",
        normalized="investment|rechenzentrumsbetreibern",
        value="investment|rechenzentrumsbetreibern",
        quote="Rechenzentrumsbetreibern",
        start=0,
        end=24,
        source_id="teaser_text",
        instrument_scope="stock",
        extraction_method="test",
    )
    doc = {
        "url": "https://example.com/ir",
        "title": "IR update",
        "company_name": "Example Utility",
        "published_at": "2026-10-01T12:00:00+00:00",
        "retrieved_at": "2026-11-02T08:00:00+00:00",
        "source_kind": "issuer",
        "text": (
            "Example Utility announced a new investment supporting multi-year power "
            "supply agreements with data center customers in the Midwest."
        ),
        "raw_sha256": "abc",
    }
    from datetime import UTC, datetime

    record = _evidence(doc, [clue], datetime(2026, 11, 2, 8, tzinfo=UTC))
    assert record is not None
    assert "investment|rechenzentrumsbetreibern" in record.facts["fact_claims"]


def test_utility_fingerprint_scores_offtake_and_capex():
    text = (
        "The company entered a power purchase agreement with a hyperscale data center "
        "campus and approved a $12 billion capital investment plan through 2030."
    )
    fp = extract_utility_fingerprint(text)
    assert fp.has_offtake and fp.has_data_center_link
    assert fp.capex_billions == 12
    assert utility_fingerprint_score(fp) >= 40


def test_apply_utility_fingerprints_boosts_matching_row():
    teaser = "US-Versorger mit Abnahmeverträgen und Investitionsoffensive für Rechenzentren"
    assert teaser_wants_utility_fingerprint(teaser)
    ranked = [
        {
            "asset_id": "a",
            "evidence_score": 10,
            "hard_contradictions": [],
        },
        {
            "asset_id": "b",
            "evidence_score": 10,
            "hard_contradictions": [],
        },
    ]
    docs = {
        "a": [
            {
                "title": "IR",
                "text": "Signed offtake with data center customer; $8 billion capex plan.",
            }
        ],
        "b": [{"title": "IR", "text": "Dividend unchanged; mild weather."}],
    }
    summary = apply_utility_fingerprints(ranked, docs, teaser_text=teaser)
    assert summary["status"] == "applied"
    assert ranked[0]["asset_id"] == "a"
    assert ranked[0]["evidence_score"] > ranked[1]["evidence_score"]


def test_chart_comparison_evidence_marks_gc_and_positive_match_peers():
    text = "Charttechnisch hat sich zudem ein kraftvolles Golden Cross gebildet."
    ranked = [
        {
            "chart": {
                "status": "ok",
                "golden_cross": True,
                "above_gd50": True,
                "above_gd200": True,
                "gd200_rising": True,
                "return_1y_pct": 10,
                "near_high_pct": -2,
                "breakout": False,
            },
            "hard_contradictions": [],
            "comparison_evidence_available": False,
            "counterarguments": [],
        },
        {
            "chart": {
                "status": "ok",
                "golden_cross": False,
                "above_gd50": True,
                "above_gd200": True,
                "gd200_rising": True,
                "return_1y_pct": 5,
                "near_high_pct": -5,
                "breakout": False,
            },
            "hard_contradictions": [],
            "comparison_evidence_available": False,
            "counterarguments": [],
        },
        {
            "chart": {
                "status": "ok",
                "golden_cross": False,
                "above_gd50": False,
                "above_gd200": False,
                "gd200_rising": False,
                "return_1y_pct": -20,
                "near_high_pct": -40,
                "breakout": False,
            },
            "hard_contradictions": [],
            "comparison_evidence_available": False,
            "counterarguments": [],
        },
    ]
    _mark_chart_comparison_evidence(ranked, text)
    assert ranked[0]["comparison_evidence_available"] is True
    assert ranked[1]["comparison_evidence_available"] is True
    assert ranked[2]["comparison_evidence_available"] is False
