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
    assert report["provisional_publication_at"] == []
    assert report["blocked_out_of_corpus"] == []
    assert report["gates"]["named_all_meet_gates"] is True


def test_corpus_report_cli_exit_zero(capsys):
    assert main(["report", "--freeze", str(FREEZE), "--manifest", str(MANIFEST)]) == 0
    out = capsys.readouterr().out
    assert "named identified: 26/26" in out
    assert "blocked (out):" in out


def test_corpus_report_bare_flags_still_work(capsys):
    assert main(["--freeze", str(FREEZE), "--manifest", str(MANIFEST)]) == 0
    assert "named identified: 26/26" in capsys.readouterr().out


def test_corpus_recipe_and_originals_cli(capsys):
    recipe = build_recipe()
    assert "evidence_batch" in recipe
    assert "pad800" in recipe["snapshots"]
    assert "investigate_corpus_case" in recipe
    assert main(["recipe"]) == 0
    assert "evidence_batch:" in capsys.readouterr().out
    assert main(["originals", "--freeze", str(FREEZE)]) == 0
    out = capsys.readouterr().out
    assert "originals identified: 0/26" in out
    assert "HT-023" in out


def test_corpus_readiness_board(capsys):
    assert main(["readiness"]) == 0
    out = capsys.readouterr().out
    assert "operator readiness" in out
    assert "corpus named: 26/26" in out
    assert "dropped" in out
    assert main(["readiness", "--json"]) == 0
    board = json.loads(capsys.readouterr().out)
    assert board["kind"] == "hebeltrader-operator-readiness-v1"
    assert board["corpus"]["gates_ok"] is True
    assert board["corpus"]["provisional_publication_at"] == []
    assert board["ht016"]["status"] == "dropped"
    assert not any(b["id"] == "pending_pdfs_192_137" for b in board["blockers"])
    assert not any(b["id"] == "ht016_no_publication_at" for b in board["blockers"])
    assert board["api_keys_present"]["EODHD_API_TOKEN"] in {True, False}
