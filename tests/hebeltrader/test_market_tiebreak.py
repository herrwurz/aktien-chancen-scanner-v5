"""Market tie-break helpers (pad800) — unit coverage without full PIT file."""

from __future__ import annotations

import json
from pathlib import Path

from scanner.hebeltrader.detective.market_tiebreak import (
    _hit_rank,
    load_corpus_original_cases,
    original_packet_gap,
    packet_leader_confirmation,
)

FREEZE = Path("docs/examples/source-packets/corpus-v1/evidence-batch-corpus-v1.json")


def test_hit_rank_matches_bare_and_exchange_ticker():
    ranking = [{"ticker": "DBK.XETRA"}, {"ticker": "SAN"}, {"ticker": "COST"}]
    assert _hit_rank(ranking, "DBK.XETRA") == 1
    assert _hit_rank(ranking, "DBK") == 1
    assert _hit_rank(ranking, "COST") == 3
    assert _hit_rank(ranking, "MISSING") is None


def test_load_corpus_original_cases_has_expected_tickers():
    cases = load_corpus_original_cases()
    assert len(cases) == 26
    by_id = {c["case_id"]: c for c in cases}
    assert by_id["HT-001"]["expected_ticker"] == "ADI"
    assert by_id["HT-023"]["expected_ticker"] == "ABBV"
    assert "HT-016" not in by_id
    assert by_id["HT-001"]["publication_date"]


def test_original_packet_gap_and_leader_confirmation_from_freeze():
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    gap = original_packet_gap(freeze)
    assert gap["total"] == 26
    assert gap["identified"] == 0
    assert gap["by_packet_evidence_status"]["partial_evidence"]["count"] == 1
    assert gap["by_packet_evidence_status"]["partial_evidence"]["cases"][0]["case_id"] == "HT-023"

    market_rows = [
        {"case_id": "HT-001", "market_top8": ["ADI", "AVGO", "MU"]},
        {"case_id": "HT-023", "market_top8": ["LLY", "ABBV", "PFE"]},
    ]
    # Inject fake named identified rows via confirmation helper using real freeze.
    confirm = packet_leader_confirmation(freeze, market_rows)
    assert confirm["named_identified"] == 26
    assert confirm["market_confirms_in_top8"] >= 1
