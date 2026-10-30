"""Batch offline evidence scans for operator packets — one freeze, one table.

Runs ``reference_scan`` logic over several input manifests that share a packet
directory and optional snapshots, then writes a compact evidence summary.
Never reads solution/label files.
"""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from .reference_scan import run_scan


def _row(case):
    pe = case.get("packet_evidence") or {}
    ident = case.get("identification") or {}
    decision = case.get("decision") or {}
    leader = (case.get("candidates") or [{}])[0]
    identity = leader.get("identity") or {}
    return {
        "case_id": case.get("case_id"),
        "source_packet_status": case.get("source_packet_status"),
        "packet_evidence_status": pe.get("status"),
        "packet_evidence_ticker": pe.get("ticker"),
        "packet_evidence_name": pe.get("name"),
        "confirmed_specific_clues": pe.get("confirmed_specific_clues"),
        "evidence_score": pe.get("evidence_score"),
        "score_margin": pe.get("score_margin"),
        "identification_status": ident.get("status"),
        "identification_basis": ident.get("basis"),
        "decision_status": decision.get("status"),
        "leader_ticker": identity.get("ticker"),
        "leader_name": identity.get("name"),
        "checked_candidates": len(case.get("checked_candidates") or []),
        "limitations": case.get("limitations") or [],
        "next_step": pe.get("next_step"),
    }


def run_batch(manifests, *, packets, snapshots=None, root=None):
    """Scan each inputs manifest into ``root`` (temp if omitted); return summary."""
    root = Path(root) if root is not None else Path(tempfile.mkdtemp(prefix="evidence-batch-"))
    root.mkdir(parents=True, exist_ok=True)
    rows = []
    freezes = []
    for index, inputs in enumerate(manifests):
        inputs = Path(inputs)
        case_root = root / f"{index:02d}-{inputs.stem}"
        if case_root.exists():
            raise FileExistsError(f"output root already exists: {case_root}")
        frozen = run_scan(inputs, case_root, packets, snapshots)
        freezes.append(
            {
                "inputs": str(inputs),
                "root": str(case_root),
                "ranking_sha256": frozen["sha256"],
                "cases": len(frozen["report"]["cases"]),
            }
        )
        for case in frozen["report"]["cases"]:
            row = _row(case)
            row["inputs"] = str(inputs)
            rows.append(row)
    summary = {
        "schema_version": 1,
        "kind": "hebeltrader-evidence-batch-v1",
        "packets": str(packets) if packets else None,
        "snapshots": str(snapshots) if snapshots else None,
        "root": str(root),
        "freezes": freezes,
        "rows": rows,
        "counts": {
            "cases": len(rows),
            "ticker_hypothesis_ready": sum(
                1 for r in rows if r["packet_evidence_status"] == "ticker_hypothesis_ready"
            ),
            "partial_evidence": sum(
                1 for r in rows if r["packet_evidence_status"] == "partial_evidence"
            ),
            "identified": sum(1 for r in rows if r["identification_status"] == "identified"),
            "identified_from_packet": sum(
                1 for r in rows if r["identification_basis"] == "historical_source_packet"
            ),
        },
    }
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--inputs",
        type=Path,
        nargs="+",
        required=True,
        help="One or more reference_scan input manifests",
    )
    parser.add_argument("--source-packets", type=Path, required=True)
    parser.add_argument("--snapshots", type=Path)
    parser.add_argument("--root", type=Path, help="Batch output root (default: temp dir)")
    parser.add_argument(
        "--summary",
        type=Path,
        help="Write JSON summary here (also printed)",
    )
    args = parser.parse_args(argv)
    summary = run_batch(
        args.inputs, packets=args.source_packets, snapshots=args.snapshots, root=args.root
    )
    text = json.dumps(summary, indent=2, ensure_ascii=False)
    if args.summary:
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        args.summary.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
