"""Live publisher-dated recall unlocks Stage-B without weakening offline packets."""

from datetime import UTC, datetime

from scanner.hebeltrader.detective.investigation import (
    InvestigationRequest,
    Investigator,
    _apply_utility_clue_matrix,
    _evidence,
    _leader_evidence_ready,
    _refresh_confirmed_specific_clues,
)
from scanner.hebeltrader.detective.schemas import AtomicClue
from scanner.hebeltrader.detective.temporal import assess_document

CUT = datetime(2026, 11, 2, 8, tzinfo=UTC)


def test_live_recall_makes_precutoff_article_eligible_despite_late_retrieval():
    doc = {
        "url": "https://news.example/aep-deal",
        "published_at": "2026-08-19T10:14:07+00:00",
        "retrieved_at": "2026-11-02T11:40:00+00:00",
    }
    strict = assess_document(doc, CUT)
    assert strict["eligibility"] == "uncertain"
    live = assess_document(doc, CUT, live_publisher_recall=True)
    assert live["eligibility"] == "eligible"
    assert live["availability_basis"] == "publisher_dated_live_recall"
    assert live["source_available_at"].startswith("2026-08-19")


def test_offline_packet_still_rejects_publication_only_availability(tmp_path):
    # retrieved_at after publication_at/cutoff → uncertain without archive binding.
    doc = {
        "company_name": "Example AG",
        "ticker": "EX",
        "url": "https://issuer.example/release",
        "title": "Release",
        "text": "Example AG acquired AlphaPower and BetaLogic.",
        "source_kind": "issuer",
        "published_at": "2026-10-25T12:00:00+00:00",
        "retrieved_at": "2026-11-02T12:00:00+00:00",
        "raw_sha256": "a" * 64,
    }
    report = Investigator(tmp_path, clock=lambda: CUT).analyze(
        InvestigationRequest(
            teaser_text="Übernahmen von AlphaPower und BetaLogic.",
            publication_at=CUT,
        ),
        documents=[doc],
    )
    assert not report["candidates"][0]["confirmed_specific_clues"]
    assert report["source_timing"][0]["availability_status"] == "uncertain"
    assert report["source_timing"][0]["availability_basis"] != "publisher_dated_live_recall"


def test_evidence_confirms_data_center_deal_headline_with_live_recall():
    clue = AtomicClue(
        clue_id="rz",
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
        "url": "https://finance.example/deal",
        "title": (
            "How Massive Ohio AI Data Center Power Deal Will Impact "
            "American Electric Power Company (AEP) Investors"
        ),
        "text": "Short body.",
        "company_name": "American Electric Power Company",
        "source_kind": "news",
        "published_at": "2026-08-19T10:14:07+00:00",
        "retrieved_at": "2026-11-02T11:40:00+00:00",
        "raw_sha256": "b" * 64,
    }
    record = _evidence(doc, [clue], CUT, live_publisher_recall=True)
    assert record is not None
    assert record.source_available_at is not None
    assert "investment|rechenzentrumsbetreibern" in record.facts["fact_claims"]


def test_utility_fingerprint_confirms_fact_cell_and_evidence_ready():
    text = "US-Versorger mit Abnahmeverträgen für Rechenzentrumsbetreiber und Golden Cross"
    ranked = [
        {
            "hard_contradictions": [],
            "utility_fingerprint": {
                "has_offtake": True,
                "has_data_center_link": True,
                "capex_billions": 10,
                "components": 3,
            },
            "evidence_matrix": [
                {
                    "clue_id": "rz",
                    "category": "fact_claims",
                    "status": "unknown",
                    "quote": "Rechenzentrumsbetreibern",
                    "evidence_cluster_ids": [],
                },
                {
                    "clue_id": "gc",
                    "category": "semantic_fact",
                    "status": "confirmed",
                    "reason": "eod_golden_cross_sma_or_ema_within_20d_pit",
                    "quote": "Golden Cross",
                    "evidence_cluster_ids": ["chart:eodhd_ma50_ma200"],
                },
            ],
            "confirmed_specific_clues": [],
        }
    ]
    clues = [
        AtomicClue(
            clue_id="rz",
            category="fact_claims",
            normalized="investment|rechenzentrumsbetreibern",
            value="investment|rechenzentrumsbetreibern",
            quote="Rechenzentrumsbetreibern",
            start=0,
            end=1,
            source_id="teaser_text",
            instrument_scope="stock",
            extraction_method="t",
        ),
        AtomicClue(
            clue_id="gc",
            category="semantic_fact",
            normalized="gc",
            value="gc",
            quote="Golden Cross",
            start=0,
            end=1,
            source_id="teaser_text",
            instrument_scope="stock",
            extraction_method="t",
        ),
    ]
    _apply_utility_clue_matrix(ranked, text)
    _refresh_confirmed_specific_clues(ranked, clues)
    assert ranked[0]["evidence_matrix"][0]["status"] == "confirmed"
    assert ranked[0]["confirmed_specific_clues"] == ["rz"]
    assert _leader_evidence_ready(ranked[0], clues) is True
