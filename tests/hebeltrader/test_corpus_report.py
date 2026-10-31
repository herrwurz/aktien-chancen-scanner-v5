"""corpus_report scorecard / recipe / originals CLI over corpus-v1 freeze."""

from __future__ import annotations

import json
from pathlib import Path

from scanner.hebeltrader.detective.corpus_report import (
    build_recipe,
    build_report,
    main,
)

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
    assert main(["report", "--freeze", str(FREEZE), "--manifest", str(MANIFEST)]) == 0
    out = capsys.readouterr().out
    assert "named identified: 26/26" in out
    assert "HT-016" in out


def test_corpus_report_bare_flags_still_work(capsys):
    assert main(["--freeze", str(FREEZE), "--manifest", str(MANIFEST)]) == 0
    assert "named identified: 26/26" in capsys.readouterr().out


def test_corpus_recipe_and_originals_cli(capsys):
    recipe = build_recipe()
    assert "evidence_batch" in recipe
    assert "pad800" in recipe["snapshots"]
    assert main(["recipe"]) == 0
    assert "evidence_batch:" in capsys.readouterr().out
    assert main(["originals", "--freeze", str(FREEZE)]) == 0
    out = capsys.readouterr().out
    assert "originals identified: 0/26" in out
    assert "HT-023" in out
