"""Quality freeze for provisional-cutoff Costco/BASF pending-PDF batch."""

from __future__ import annotations

import json
from pathlib import Path

FREEZE = Path("docs/examples/source-packets/batch-pending-pdf/evidence-batch-pending-pdf.json")
MANIFEST = Path("docs/examples/source-packets/batch-pending-pdf/manifest.json")
REFS = Path("docs/examples/source-packets/batch-pending-pdf/refs-provisional-publication-at.json")
SHARED_REFS = Path("docs/examples/reference-27-inputs-with-publication-at.json")

EXPECTED = {
    "HT-003": "COST",
    "HT-012": "BAS",
}


def test_pending_pdf_named_identified_with_gates():
    payload = json.loads(FREEZE.read_text(encoding="utf-8"))
    named = [row for row in payload["rows"] if "named" in row["inputs"]]
    assert len(named) == 2
    assert payload["counts"]["identified_from_packet"] == 2
    for row in named:
        assert row["packet_evidence_ticker"] == EXPECTED[row["case_id"]]
        assert row["identification_status"] == "identified"
        assert row["identification_basis"] == "historical_source_packet"
        assert row["confirmed_specific_clues"] >= 2
        assert row["score_margin"] >= 35
        assert row["checked_candidates"] >= 5


def test_pending_pdf_originals_not_identified():
    payload = json.loads(FREEZE.read_text(encoding="utf-8"))
    for row in payload["rows"]:
        if "original" in row["inputs"]:
            assert row["identification_status"] != "identified"


def test_pending_pdf_manifest_and_provisional_basis():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert [c["case_id"] for c in manifest["cases"]] == list(EXPECTED)
    for case in manifest["cases"]:
        assert case["publication_at_basis"] == ("featured_date_plus_corpus_stand_0815_pdf_pending")


def test_pending_pdf_does_not_mutate_shared_reference_publication_at():
    """Shared 27er refs stay null until operator PDFs confirm Stand."""
    shared = json.loads(SHARED_REFS.read_text(encoding="utf-8"))
    cases = shared if isinstance(shared, list) else shared.get("cases") or shared.get("inputs")
    by_id = {c["case_id"]: c for c in cases}
    for case_id in EXPECTED:
        assert by_id[case_id].get("publication_at") is None
    overlay = json.loads(REFS.read_text(encoding="utf-8"))
    for case in overlay["cases"]:
        assert case["publication_at_basis"] == ("featured_date_plus_corpus_stand_0815_pdf_pending")
        assert case["publication_at"].endswith("T08:15:00+01:00")
