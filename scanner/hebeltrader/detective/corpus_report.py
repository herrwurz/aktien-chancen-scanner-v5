"""Corpus-v1 operator CLI: scorecard, recipe, originals gap, market tie-break, readiness.

Subcommands:
  report     named/original freeze scorecard (default)
  recipe     print standard evidence_batch + pad800 snapshot recipe
  originals  original-teaser packet_evidence gap from freeze
  tiebreak   market chart as tie-break on pad800 (optional Blind remap file)
  readiness  single board of gates / operator blockers / API keys

Does not retune Blind 202/26 scores. Does not require Tavily/OpenAI.
"""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

DEFAULT_FREEZE = Path("docs/examples/source-packets/corpus-v1/evidence-batch-corpus-v1.json")
DEFAULT_MANIFEST = Path("docs/examples/source-packets/corpus-v1/manifest.json")
DEFAULT_PACKETS = Path("docs/examples/source-packets/corpus-v1/packets")
DEFAULT_SNAPSHOTS = Path("reports/snapshots-pit-pool-v1-pad800-2026-10-31.json")
DEFAULT_HT016 = Path("docs/examples/source-packets/ht-016-blocked/manifest.json")
DEFAULT_TIEBREAK = Path("docs/examples/market-tiebreak-pad800-2026-10-31.json")
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


def build_recipe(
    *,
    packets: Path = DEFAULT_PACKETS,
    snapshots: Path = DEFAULT_SNAPSHOTS,
    corpus_dir: Path = DEFAULT_MANIFEST.parent,
) -> dict:
    cmd = (
        "python3 -m scanner.hebeltrader.detective.evidence_batch \\\n"
        f"  --inputs {corpus_dir}/HT-*.inputs.*.json \\\n"
        f"  --source-packets {packets} \\\n"
        f"  --snapshots {snapshots} \\\n"
        f"  --summary {corpus_dir}/evidence-batch-corpus-v1.json"
    )
    return {
        "schema_version": 1,
        "kind": "hebeltrader-corpus-v1-recipe-v1",
        "packets": str(packets),
        "snapshots": str(snapshots),
        "scorecard": "python3 -m scanner.hebeltrader.detective.corpus_report report",
        "tiebreak": (
            "python3 -m scanner.hebeltrader.detective.corpus_report tiebreak "
            f"--snapshots {snapshots}"
        ),
        "promote_pending_pdfs": "python3 scripts/promote_provisional_publication_at.py",
        "investigate_corpus_case": (
            "python3 -m scanner.hebeltrader.detective.investigate_cli analyze "
            "--corpus-case HT-001 --corpus-variant named "
            "--root /tmp/ht-corpus-case"
        ),
        "simulated_3b": (
            'python3 -c "from pathlib import Path; from scanner.hebeltrader.detective.'
            "simulated_falsification import run_simulated_live_falsification; "
            "print(run_simulated_live_falsification(Path('/tmp/sim3b'))"
            "['identification'])\""
        ),
        "readiness": "python3 -m scanner.hebeltrader.detective.corpus_report readiness",
        "evidence_batch": cmd,
        "notes": [
            "Named freeze is already committed; re-run only after packet edits.",
            "HT-016 stays out until operator issue + PDF Stand.",
            "Stufe 3b live web needs Tavily/OpenAI; use simulated_falsification offline.",
        ],
    }


def render_recipe(recipe: dict) -> str:
    lines = [
        "corpus-v1 operator recipe",
        "",
        "evidence_batch:",
        recipe["evidence_batch"],
        "",
        f"scorecard: {recipe['scorecard']}",
        f"tiebreak:  {recipe['tiebreak']}",
        f"promote:   {recipe['promote_pending_pdfs']}",
        "",
        "notes:",
    ]
    for note in recipe["notes"]:
        lines.append(f"  - {note}")
    return "\n".join(lines) + "\n"


def build_originals(freeze: dict) -> dict:
    from .market_tiebreak import original_packet_gap

    gap = original_packet_gap(freeze)
    gap["schema_version"] = 1
    gap["kind"] = "hebeltrader-corpus-v1-originals-gap-v1"
    gap["blocked_out_of_corpus"] = list(BLOCKED_OUT)
    gap["interpretation"] = (
        "0 originals identified: teaser anonymity (≥2 native named anchors missing), "
        "not packet tooling. HT-023 original reaches partial_evidence via issuer_literal."
    )
    return gap


def render_originals(gap: dict) -> str:
    lines = [
        "corpus-v1 original teaser gap",
        f"  originals identified: {gap['identified']}/{gap['total']}",
        f"  blocked (out): {', '.join(gap['blocked_out_of_corpus'])}",
        "  by packet_evidence:",
    ]
    for status, bucket in gap["by_packet_evidence_status"].items():
        lines.append(f"    {status}: {bucket['count']}")
        for row in bucket["cases"][:5]:
            extra = ""
            if row.get("ticker"):
                extra = f" → {row['ticker']} clues={row.get('confirmed_specific_clues')}"
            lines.append(f"      {row['case_id']}{extra}")
    lines.append(f"  note: {gap['interpretation']}")
    return "\n".join(lines) + "\n"


def _promote_plan() -> dict:
    try:
        from scripts.promote_provisional_publication_at import (
            PROVISIONAL_REFS,
            plan_promotions,
        )

        inventory = json.loads(
            Path("docs/hebeltrader-publisher-pdf-inventory.json").read_text(encoding="utf-8")
        )
        provisional = json.loads(PROVISIONAL_REFS.read_text(encoding="utf-8"))
        plan = plan_promotions(inventory, provisional)
        return {
            "ready": plan["ready"],
            "still_missing": plan["still_missing"],
            "blocked": plan["blocked"],
            "actions": plan["actions"],
        }
    except Exception as exc:  # noqa: BLE001 - readiness must not crash
        return {"error": str(exc)[:200]}


def build_readiness(
    *,
    freeze_path: Path = DEFAULT_FREEZE,
    manifest_path: Path = DEFAULT_MANIFEST,
    ht016_path: Path = DEFAULT_HT016,
    tiebreak_path: Path = DEFAULT_TIEBREAK,
) -> dict:
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    report = build_report(freeze, manifest)
    originals = build_originals(freeze)
    promote = _promote_plan()
    ht016 = None
    if ht016_path.exists():
        ht016 = json.loads(ht016_path.read_text(encoding="utf-8")).get("case")
    tiebreak = None
    if tiebreak_path.exists():
        raw = json.loads(tiebreak_path.read_text(encoding="utf-8"))
        tiebreak = {
            "market": raw.get("market"),
            "packet_leader_confirmation": {
                k: raw.get("packet_leader_confirmation", {}).get(k)
                for k in (
                    "named_identified",
                    "market_confirms_in_top8",
                    "market_misses_top8",
                )
            },
            "blind_202_26": {
                k: raw.get("blind_202_26", {}).get(k)
                for k in ("dbk_rank", "dbk_score", "in_top8", "residual_error_class", "note")
            },
        }
        if tiebreak["blind_202_26"].get("residual_error_class") is None:
            tiebreak["blind_202_26"]["residual_error_class"] = "B_chart_rank"
    blockers = []
    if promote.get("still_missing"):
        blockers.append(
            {
                "id": "pending_pdfs_192_137",
                "status": "blocked",
                "detail": "Costco 192/26 and/or BASF 137/26 PDF Stand still missing",
                "actions": promote.get("actions"),
            }
        )
    if ht016 and ht016.get("status") == "blocked_no_publication_at":
        blockers.append(
            {
                "id": "ht016_no_publication_at",
                "status": "blocked",
                "detail": "HT-016 headline-only; needs issue binding + Call-PDF Stand",
            }
        )
    if originals["identified"] == 0:
        blockers.append(
            {
                "id": "original_teaser_anchor_gap",
                "status": "corpus_gap",
                "detail": "0/26 originals have ≥2 native named anchors",
            }
        )
    if not os.environ.get("TAVILY_API_KEY") and not os.environ.get("OPENAI_API_KEY"):
        blockers.append(
            {
                "id": "live_3b_api_keys",
                "status": "blocked",
                "detail": "Tavily/OpenAI absent; use simulated_falsification offline",
            }
        )
    return {
        "schema_version": 1,
        "kind": "hebeltrader-operator-readiness-v1",
        "recorded_at": datetime.now(UTC).isoformat(),
        "corpus": {
            "named_identified": f"{report['named']['identified']}/{report['named']['total']}",
            "originals_identified": (
                f"{report['original']['identified']}/{report['original']['total']}"
            ),
            "gates_ok": report["gates"]["named_all_meet_gates"],
            "provisional_publication_at": report["provisional_publication_at"],
            "blocked_out_of_corpus": report["blocked_out_of_corpus"],
        },
        "promote_pending_pdf": promote,
        "ht016": {
            "status": (ht016 or {}).get("status"),
            "suspected_ticker": (ht016 or {}).get("suspected_ticker"),
            "identification_freeze": (ht016 or {}).get("identification_freeze"),
        },
        "tiebreak": tiebreak,
        "api_keys_present": {
            "EODHD_API_TOKEN": bool(os.environ.get("EODHD_API_TOKEN")),
            "TAVILY_API_KEY": bool(os.environ.get("TAVILY_API_KEY")),
            "OPENAI_API_KEY": bool(os.environ.get("OPENAI_API_KEY")),
        },
        "blockers": blockers,
        "next_operator_actions": (
            (
                [
                    "Upload Hebeltrader PDFs 192/26 (Costco) and 137/26 (BASF); "
                    "run scripts/ingest_publisher_pdfs.py then "
                    "scripts/promote_provisional_publication_at.py --apply"
                ]
                if promote.get("still_missing")
                else []
            )
            + [
                "Bind HT-016 to an issue + PDF Stand; re-cut ht-016-blocked packet",
                "For live Stufe 3b: provide TAVILY_API_KEY and/or OPENAI_API_KEY",
                "Secure next real teaser before reading Call-PDF (≥2 named anchors)",
            ]
        ),
        "smoke": {
            "corpus_case": (
                "python3 -m scanner.hebeltrader.detective.investigate_cli analyze "
                "--corpus-case HT-003 --root /tmp/ht-corpus-case"
            ),
            "simulated_3b": ("python3 -m scanner.hebeltrader.detective.corpus_report recipe"),
        },
    }


def render_readiness(board: dict) -> str:
    corpus = board["corpus"]
    lines = [
        "operator readiness",
        f"  corpus named: {corpus['named_identified']} (gates_ok={corpus['gates_ok']})",
        f"  corpus originals: {corpus['originals_identified']}",
        f"  provisional pub_at: {', '.join(corpus['provisional_publication_at']) or '—'}",
        f"  HT-016: {board['ht016'].get('status')}",
        (
            "  API keys: "
            + ", ".join(f"{k}={'yes' if v else 'no'}" for k, v in board["api_keys_present"].items())
        ),
        f"  blockers ({len(board['blockers'])}):",
    ]
    for item in board["blockers"]:
        lines.append(f"    - [{item['status']}] {item['id']}: {item['detail']}")
    lines.append("  next:")
    for action in board["next_operator_actions"]:
        lines.append(f"    - {action}")
    if board.get("tiebreak") and board["tiebreak"].get("market"):
        m = board["tiebreak"]["market"]
        lines.append(
            f"  pad800 market Top1/3/8: {m['top1']}/{m['top3']}/{m['top8']} of {m['graded']}"
        )
    return "\n".join(lines) + "\n"


def _write(path: Path | None, payload: dict) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command")

    report_p = sub.add_parser("report", help="named/original freeze scorecard")
    report_p.add_argument("--freeze", type=Path, default=DEFAULT_FREEZE)
    report_p.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    report_p.add_argument("--json", action="store_true")
    report_p.add_argument("--out", type=Path)

    recipe_p = sub.add_parser("recipe", help="print operator evidence_batch recipe")
    recipe_p.add_argument("--packets", type=Path, default=DEFAULT_PACKETS)
    recipe_p.add_argument("--snapshots", type=Path, default=DEFAULT_SNAPSHOTS)
    recipe_p.add_argument("--json", action="store_true")
    recipe_p.add_argument("--out", type=Path)

    originals_p = sub.add_parser("originals", help="original teaser packet_evidence gap")
    originals_p.add_argument("--freeze", type=Path, default=DEFAULT_FREEZE)
    originals_p.add_argument("--json", action="store_true")
    originals_p.add_argument("--out", type=Path)

    tie_p = sub.add_parser("tiebreak", help="market chart tie-break on pad800")
    tie_p.add_argument("--snapshots", type=Path, default=DEFAULT_SNAPSHOTS)
    tie_p.add_argument("--json", action="store_true")
    tie_p.add_argument("--out", type=Path)

    ready_p = sub.add_parser("readiness", help="operator readiness board")
    ready_p.add_argument("--freeze", type=Path, default=DEFAULT_FREEZE)
    ready_p.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    ready_p.add_argument("--json", action="store_true")
    ready_p.add_argument("--out", type=Path)

    # Back-compat: bare flags without subcommand → report
    if argv is None:
        import sys

        argv = sys.argv[1:]
    if not argv or argv[0].startswith("-"):
        argv = ["report", *argv]

    args = parser.parse_args(argv)

    if args.command == "report":
        freeze = json.loads(args.freeze.read_text(encoding="utf-8"))
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        payload = build_report(freeze, manifest)
        _write(args.out, payload)
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print(render_text(payload), end="")
        ok = payload["gates"]["named_all_meet_gates"] and not payload["named"]["not_identified"]
        return 0 if ok else 1

    if args.command == "recipe":
        payload = build_recipe(packets=args.packets, snapshots=args.snapshots)
        _write(args.out, payload)
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print(render_recipe(payload), end="")
        return 0

    if args.command == "originals":
        freeze = json.loads(args.freeze.read_text(encoding="utf-8"))
        payload = build_originals(freeze)
        _write(args.out, payload)
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print(render_originals(payload), end="")
        return 0 if payload["identified"] == 0 else 1

    if args.command == "tiebreak":
        from . import market_tiebreak as mt

        if not args.snapshots.exists():
            raise SystemExit(f"missing snapshots {args.snapshots}")
        payload = mt.build_report(
            snapshots_path=args.snapshots,
            freeze_path=DEFAULT_FREEZE,
            blind_inputs_path=mt.DEFAULT_BLIND_INPUTS,
            blind_snapshots_path=mt.DEFAULT_BLIND_SNAPSHOTS,
        )
        _write(args.out, payload)
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print(mt.render_text(payload), end="")
        return 0

    if args.command == "readiness":
        payload = build_readiness(freeze_path=args.freeze, manifest_path=args.manifest)
        _write(args.out, payload)
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print(render_readiness(payload), end="")
        # Exit 0 even with blockers — readiness is informational.
        return 0

    parser.error(f"unknown command {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
