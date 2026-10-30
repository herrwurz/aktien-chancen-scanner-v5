"""Quality freeze for remaining US SEC batch (after batch-10)."""

from __future__ import annotations

import json
from pathlib import Path

FREEZE = Path("docs/examples/source-packets/batch-us-rest/evidence-batch-us-rest.json")
MANIFEST = Path("docs/examples/source-packets/batch-us-rest/manifest.json")

EXPECTED = {
    "HT-008": "KKR",
    "HT-017": "JPM",
    "HT-018": "JNJ",
    "HT-019": "SLB",
    "HT-020": "SNPS",
    "HT-022": "CEG",
    "HT-027": "TMO",
}


def test_us_rest_named_identified_with_gates():
    payload = json.loads(FREEZE.read_text(encoding="utf-8"))
    named = [row for row in payload["rows"] if "named" in row["inputs"]]
    assert len(named) == 7
    assert payload["counts"]["identified_from_packet"] == 7
    for row in named:
        assert row["packet_evidence_ticker"] == EXPECTED[row["case_id"]]
        assert row["identification_status"] == "identified"
        assert row["identification_basis"] == "historical_source_packet"
        assert row["confirmed_specific_clues"] >= 2
        assert row["score_margin"] >= 35
        assert row["checked_candidates"] >= 5


def test_us_rest_originals_not_identified():
    payload = json.loads(FREEZE.read_text(encoding="utf-8"))
    for row in payload["rows"]:
        if "original" in row["inputs"]:
            assert row["identification_status"] != "identified"


def test_us_rest_manifest_matches_expected():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert [c["case_id"] for c in manifest["cases"]] == list(EXPECTED)
