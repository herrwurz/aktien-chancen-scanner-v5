"""Quality freeze for EU IR Wayback hybrid batch (Zurich, Thales, Leonardo, Adidas)."""

from __future__ import annotations

import json
from pathlib import Path

FREEZE = Path("docs/examples/source-packets/batch-eu-ir-wayback/evidence-batch-eu-ir-wayback.json")
MANIFEST = Path("docs/examples/source-packets/batch-eu-ir-wayback/manifest.json")

EXPECTED = {
    "HT-002": "ZURN",
    "HT-011": "HO",
    "HT-015": "LDO",
    "HT-025": "ADS",
}


def test_eu_ir_wayback_named_identified_with_gates():
    payload = json.loads(FREEZE.read_text(encoding="utf-8"))
    named = [row for row in payload["rows"] if "named" in row["inputs"]]
    assert len(named) == 4
    assert payload["counts"]["identified_from_packet"] == 4
    for row in named:
        assert row["packet_evidence_ticker"] == EXPECTED[row["case_id"]]
        assert row["identification_status"] == "identified"
        assert row["identification_basis"] == "historical_source_packet"
        assert row["confirmed_specific_clues"] >= 2
        assert row["score_margin"] >= 35
        assert row["checked_candidates"] >= 5


def test_eu_ir_wayback_originals_not_identified():
    payload = json.loads(FREEZE.read_text(encoding="utf-8"))
    for row in payload["rows"]:
        if "original" in row["inputs"]:
            assert row["identification_status"] != "identified"


def test_eu_ir_wayback_manifest_matches_expected():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert [c["case_id"] for c in manifest["cases"]] == list(EXPECTED)


def test_eu_ir_wayback_packets_use_archived_snapshot_lead():
    packets = Path("docs/examples/source-packets/batch-eu-ir-wayback/packets")
    for case_id, ticker in EXPECTED.items():
        docs = json.loads((packets / f"{case_id}.json").read_text(encoding="utf-8"))
        assert len(docs) >= 6
        lead = docs[0]
        assert lead["ticker"] == ticker
        evidence = lead["availability_evidence"]
        assert evidence["basis"] == "archived_snapshot"
        assert evidence["observed_at"] == lead["source_available_at"]
        assert "web.archive.org" in lead["url"]
