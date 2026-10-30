"""Quality freeze for EU/FPI SEC 6-K batch (SAP, BP, Eni)."""

from __future__ import annotations

import json
from pathlib import Path

FREEZE = Path("docs/examples/source-packets/batch-eu-sec/evidence-batch-eu-sec.json")
MANIFEST = Path("docs/examples/source-packets/batch-eu-sec/manifest.json")

EXPECTED = {
    "HT-014": "SAP",
    "HT-021": "BP",
    "HT-024": "E",
}


def test_eu_sec_named_identified_with_gates():
    payload = json.loads(FREEZE.read_text(encoding="utf-8"))
    named = [row for row in payload["rows"] if "named" in row["inputs"]]
    assert len(named) == 3
    assert payload["counts"]["identified_from_packet"] == 3
    for row in named:
        assert row["packet_evidence_ticker"] == EXPECTED[row["case_id"]]
        assert row["identification_status"] == "identified"
        assert row["identification_basis"] == "historical_source_packet"
        assert row["confirmed_specific_clues"] >= 2
        assert row["score_margin"] >= 35
        assert row["checked_candidates"] >= 5


def test_eu_sec_originals_not_identified():
    payload = json.loads(FREEZE.read_text(encoding="utf-8"))
    for row in payload["rows"]:
        if "original" in row["inputs"]:
            assert row["identification_status"] != "identified"


def test_eu_sec_manifest_matches_expected():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert [c["case_id"] for c in manifest["cases"]] == list(EXPECTED)
