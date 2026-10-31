"""Quality freeze for Costco/BASF batch after PDF Stand promotion."""

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
PDF_BASIS = "publisher_pdf_stand_uhr"


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


def test_pending_pdf_manifest_uses_publisher_stand_basis():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert [c["case_id"] for c in manifest["cases"]] == list(EXPECTED)
    for case in manifest["cases"]:
        assert case["publication_at_basis"] == PDF_BASIS
        assert case["publication_at"].endswith("T08:15:00+01:00")


def test_pending_pdf_shared_reference_publication_at_promoted():
    """Shared 27er refs filled from PDF Stand after operator upload."""
    shared = json.loads(SHARED_REFS.read_text(encoding="utf-8"))
    cases = shared if isinstance(shared, list) else shared.get("cases") or shared.get("inputs")
    by_id = {c["case_id"]: c for c in cases}
    overlay = json.loads(REFS.read_text(encoding="utf-8"))
    for case in overlay["cases"]:
        assert case["publication_at_basis"] == PDF_BASIS
        assert case["publication_at"].endswith("T08:15:00+01:00")
        assert by_id[case["case_id"]].get("publication_at") == case["publication_at"]
