"""Scorecard CLI over the corpus-v1 evidence freeze.

Reads the committed freeze + manifest and prints a compact named/original
summary. Does not re-run scans or touch Blind 202/26.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

DEFAULT_FREEZE = Path("docs/examples/source-packets/corpus-v1/evidence-batch-corpus-v1.json")
DEFAULT_MANIFEST = Path("docs/examples/source-packets/corpus-v1/manifest.json")
BLOCKED_OUT = ("HT-016",)


def build_report(freeze: dict, manifest: dict) -> dict:
    cases = {c["case_id"]: c for c in manifest.get("cases") or []}
    named = [r for r in freeze.get("rows") or [] if "named" in Path(r.get("inputs") or "").name]
    originals = [
        r for r in freeze.get("rows") or [] if "original" in Path(r.get("inputs") or "").name
    ]
    provisional = sorted(cid for cid, c in cases.items() if c.get("provisional_publication_at"))
    named_ok = [r for r in named if r.get("identification_status") == "identified"]
    named_fail = [r for r in named if r.get("identification_status") != "identified"]
    original_ok = [r for r in originals if r.get("identification_status") == "identified"]
    basis = Counter(r.get("identification_basis") for r in named_ok)
    batches = Counter(cases[r["case_id"]]["source_batch"] for r in named if r["case_id"] in cases)
    return {
        "schema_version": 1,
        "kind": "hebeltrader-corpus-v1-report-v1",
        "freeze_counts": freeze.get("counts") or {},
        "manifest_cases": len(cases),
        "named": {
            "total": len(named),
            "identified": len(named_ok),
            "not_identified": [r["case_id"] for r in named_fail],
            "basis": dict(basis),
            "by_batch": dict(batches),
        },
        "original": {
            "total": len(originals),
            "identified": len(original_ok),
            "identified_case_ids": [r["case_id"] for r in original_ok],
        },
        "provisional_publication_at": provisional,
        "blocked_out_of_corpus": list(BLOCKED_OUT),
        "gates": {
            "min_confirmed_specific_clues": 2,
            "min_score_margin": 35,
            "min_checked_candidates": 5,
            "named_all_meet_gates": all(
                (r.get("confirmed_specific_clues") or 0) >= 2
                and (r.get("score_margin") or 0) >= 35
                and (r.get("checked_candidates") or 0) >= 5
                for r in named_ok
            ),
        },
    }


def render_text(report: dict) -> str:
    named = report["named"]
    original = report["original"]
    lines = [
        "corpus-v1 evidence scorecard",
        f"  manifest cases: {report['manifest_cases']}",
        f"  named identified: {named['identified']}/{named['total']}",
        f"  originals identified: {original['identified']}/{original['total']}",
        f"  provisional pub_at: {', '.join(report['provisional_publication_at']) or '—'}",
        f"  blocked (out): {', '.join(report['blocked_out_of_corpus'])}",
        f"  gates ok: {report['gates']['named_all_meet_gates']}",
        "  by batch:",
    ]
    for batch, count in sorted(named["by_batch"].items()):
        lines.append(f"    {batch}: {count}")
    if named["not_identified"]:
        lines.append(f"  named gaps: {', '.join(named['not_identified'])}")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze", type=Path, default=DEFAULT_FREEZE)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text")
    parser.add_argument("--out", type=Path, help="Optional write path for JSON report")
    args = parser.parse_args(argv)

    freeze = json.loads(args.freeze.read_text(encoding="utf-8"))
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    report = build_report(freeze, manifest)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(render_text(report), end="")
    return (
        0
        if report["gates"]["named_all_meet_gates"] and not report["named"]["not_identified"]
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
