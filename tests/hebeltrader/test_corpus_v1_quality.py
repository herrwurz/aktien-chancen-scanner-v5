"""Quality freeze for corpus-v1 unified evidence batch (26 named identified)."""

from __future__ import annotations

import json
from pathlib import Path

FREEZE = Path("docs/examples/source-packets/corpus-v1/evidence-batch-corpus-v1.json")
MANIFEST = Path("docs/examples/source-packets/corpus-v1/manifest.json")

PROVISIONAL: set[str] = set()


def test_corpus_v1_named_all_identified_from_packet():
    payload = json.loads(FREEZE.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    expected = {c["case_id"]: c["expected_ticker"] for c in manifest["cases"]}
    named = [row for row in payload["rows"] if "named" in row["inputs"]]
    assert len(named) == 26
    assert payload["counts"]["identified_from_packet"] == 26
    assert payload["counts"]["identified"] == 26
    for row in named:
        assert row["case_id"] in expected
        assert row["packet_evidence_ticker"] == expected[row["case_id"]]
        assert row["identification_status"] == "identified"
        assert row["identification_basis"] == "historical_source_packet"
        assert row["confirmed_specific_clues"] >= 2
        assert row["score_margin"] >= 35
        assert row["checked_candidates"] >= 5


def test_corpus_v1_originals_not_identified():
    payload = json.loads(FREEZE.read_text(encoding="utf-8"))
    originals = [row for row in payload["rows"] if "original" in row["inputs"]]
    assert len(originals) == 26
    for row in originals:
        assert row["identification_status"] != "identified"


def test_corpus_v1_manifest_marks_provisional_pdf_gaps():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    by_id = {c["case_id"]: c for c in manifest["cases"]}
    assert set(by_id) == {
        "HT-001",
        "HT-002",
        "HT-003",
        "HT-004",
        "HT-005",
        "HT-006",
        "HT-007",
        "HT-008",
        "HT-009",
        "HT-010",
        "HT-011",
        "HT-012",
        "HT-013",
        "HT-014",
        "HT-015",
        "HT-017",
        "HT-018",
        "HT-019",
        "HT-020",
        "HT-021",
        "HT-022",
        "HT-023",
        "HT-024",
        "HT-025",
        "HT-026",
        "HT-027",
    }
    # Costco/BASF Stand Uhr promoted 2026-10-31 — no provisional cutoffs left.
    assert PROVISIONAL == set()
    for case in by_id.values():
        assert case["provisional_publication_at"] is False


def test_corpus_v1_excludes_ht016():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert "HT-016" not in {c["case_id"] for c in manifest["cases"]}
