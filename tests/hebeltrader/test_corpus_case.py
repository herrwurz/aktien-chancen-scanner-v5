"""corpus-v1 case loader + investigate_cli --corpus-case wiring."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scanner.hebeltrader.detective.corpus_case import load_corpus_case
from scanner.hebeltrader.detective.investigate_cli import main as investigate_main


def test_load_corpus_case_named_has_packet_and_pub_at():
    case = load_corpus_case("HT-001", variant="named")
    assert case["case_id"] == "HT-001"
    assert case["expected_ticker"] == "ADI"
    assert case["publication_at"] is not None
    assert case["historical_blind"] is True
    assert len(case["documents"]) >= 5
    assert "Analog Devices" in case["teaser_text"] or "Empower" in case["teaser_text"]


def test_load_corpus_case_blocks_ht016():
    with pytest.raises(ValueError, match="blocked"):
        load_corpus_case("HT-016")


def test_investigate_cli_corpus_case_identifies(tmp_path, capsys):
    root = tmp_path / "run"
    code = investigate_main(
        [
            "analyze",
            "--corpus-case",
            "HT-001",
            "--corpus-variant",
            "named",
            "--root",
            str(root),
        ]
    )
    assert code == 0
    report = json.loads(capsys.readouterr().out)
    assert report["identification"]["status"] == "identified"
    assert report["identification"]["basis"] == "historical_source_packet"
    assert report["packet_evidence"]["ticker"] == "ADI"
    assert report["corpus_case"]["case_id"] == "HT-001"
    assert Path(report["corpus_case"]["paths"]["packet"]).name == "HT-001.json"
