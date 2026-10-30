"""Quality freeze for Blind 202/26 SEC 6-K developmental packet.

Does not mutate the prospective-blind ranking freeze.
"""

from __future__ import annotations

import json
from pathlib import Path

FREEZE = Path("docs/examples/source-packets/blind-202-26-sec6k/evidence-batch-blind-202-26.json")
BLIND_RANKING = Path("docs/examples/blind-202-26-freeze-pit-excl/rankings.json")
EXPECTED_BLIND_SHA = "3fff83e1387325ccf8c1fc47d49940c5d9385244fd00518c1ea0c4722a331b0f"


def test_blind_freeze_sha_untouched():
    payload = json.loads(BLIND_RANKING.read_text(encoding="utf-8"))
    assert payload["sha256"] == EXPECTED_BLIND_SHA


def test_blind_named_identified_via_sec_6k_packet():
    payload = json.loads(FREEZE.read_text(encoding="utf-8"))
    named = [row for row in payload["rows"] if "named" in row["inputs"]]
    assert len(named) == 1
    row = named[0]
    assert row["packet_evidence_ticker"] == "DB"
    assert row["identification_status"] == "identified"
    assert row["identification_basis"] == "historical_source_packet"
    assert row["confirmed_specific_clues"] >= 2
    assert row["score_margin"] >= 35
    assert row["checked_candidates"] >= 5
    assert payload["counts"]["identified_from_packet"] == 1


def test_blind_original_not_identified():
    payload = json.loads(FREEZE.read_text(encoding="utf-8"))
    for row in payload["rows"]:
        if "original" in row["inputs"]:
            assert row["identification_status"] != "identified"
            assert row["packet_evidence_status"] == "insufficient_evidence"
