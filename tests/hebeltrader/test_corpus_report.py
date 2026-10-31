"""corpus_report scorecard over corpus-v1 freeze."""

from __future__ import annotations

import json
from pathlib import Path

from scanner.hebeltrader.detective.corpus_report import build_report, main

FREEZE = Path("docs/examples/source-packets/corpus-v1/evidence-batch-corpus-v1.json")
MANIFEST = Path("docs/examples/source-packets/corpus-v1/manifest.json")


def test_corpus_report_scorecard_matches_freeze():
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    report = build_report(freeze, manifest)
    assert report["manifest_cases"] == 26
    assert report["named"]["identified"] == 26
    assert report["named"]["total"] == 26
    assert report["original"]["identified"] == 0
    assert report["provisional_publication_at"] == ["HT-003", "HT-012"]
    assert report["blocked_out_of_corpus"] == ["HT-016"]
    assert report["gates"]["named_all_meet_gates"] is True


def test_corpus_report_cli_exit_zero(capsys):
    assert main(["--freeze", str(FREEZE), "--manifest", str(MANIFEST)]) == 0
    out = capsys.readouterr().out
    assert "named identified: 26/26" in out
    assert "HT-016" in out
