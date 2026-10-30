"""Quality freeze for the parallel batch-10 evidence run.

Guards: correct leaders, margin gate, no original false-IDs, no peer hard-clue
ties. Does not relax identification thresholds.
"""

from __future__ import annotations

import json
from pathlib import Path

FREEZE = Path("docs/examples/source-packets/batch-10/evidence-batch-10.json")
MANIFEST = Path("docs/examples/source-packets/batch-10/manifest.json")

EXPECTED = {
    "HT-001": "ADI",
    "HT-004": "CRM",
    "HT-005": "MU",
    "HT-006": "UNH",
    "HT-007": "VRT",
    "HT-009": "PFE",
    "HT-010": "AVGO",
    "HT-013": "DHR",
    "HT-023": "ABBV",
    "HT-026": "CARR",
}


def test_batch_10_freeze_named_identified_with_margin_and_correct_ticker():
    assert FREEZE.is_file()
    payload = json.loads(FREEZE.read_text(encoding="utf-8"))
    named = [row for row in payload["rows"] if "named" in row["inputs"]]
    assert len(named) == 10
    assert payload["counts"]["identified_from_packet"] >= 10
    for row in named:
        expect = EXPECTED[row["case_id"]]
        assert row["identification_status"] == "identified"
        assert row["identification_basis"] == "historical_source_packet"
        assert row["packet_evidence_ticker"] == expect
        assert row["confirmed_specific_clues"] >= 2
        assert row["score_margin"] is not None and row["score_margin"] >= 35
        assert row["checked_candidates"] >= 5


def test_batch_10_freeze_originals_do_not_identify():
    payload = json.loads(FREEZE.read_text(encoding="utf-8"))
    originals = [row for row in payload["rows"] if "original" in row["inputs"]]
    assert len(originals) == 10
    for row in originals:
        assert row["identification_status"] != "identified"
        assert row["identification_basis"] is None


def test_batch_10_manifest_has_ten_us_sec_cases():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    case_ids = [c["case_id"] for c in manifest["cases"]]
    assert case_ids == list(EXPECTED)
