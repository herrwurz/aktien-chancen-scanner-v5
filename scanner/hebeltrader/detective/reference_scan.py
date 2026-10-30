"""Solution-free, offline development scan. Mount inputs/packets only, never references."""

import argparse
import json
from pathlib import Path

from .history import freeze_analysis
from .investigation import InvestigationRequest, Investigator
from .market_screen import rank as market_rank
from .market_screen import resolve_case_snapshots
from .structure_screen import screen

_FIELDS = {"case_id", "headline", "teaser_text", "publication_date", "publication_at"}


def _teaser_blob(case):
    return "\n".join(part for part in (case.get("headline"), case.get("teaser_text")) if part)


def run_scan(inputs, root, source_packets=None, snapshots=None):
    payload = json.loads(Path(inputs).read_text())
    allowed_meta = {
        "schema_version",
        "evaluation_class",
        "cases",
        "corpus_kind",
        "note",
        "independent_benchmark",
    }
    forbidden = set(payload) - allowed_meta
    if forbidden:
        raise ValueError("forbidden scan manifest fields")
    if payload["evaluation_class"] not in {
        "development_regression",
        "prospective_blind",
    }:
        raise ValueError("Unsupported evaluation_class for offline scan")
    cases = payload["cases"]
    if any(set(case) - _FIELDS for case in cases):
        raise ValueError("forbidden scan fields: solutions and old predictions must stay separate")
    if any(not _FIELDS.issubset(case) for case in cases):
        raise ValueError("scan cases missing required input fields")
    if len({c["case_id"] for c in cases}) != len(cases):
        raise ValueError("duplicate case ids")
    snapshot_payload = None
    if snapshots is not None:
        snapshot_payload = json.loads(Path(snapshots).read_text(encoding="utf-8"))
        if "snapshots" not in snapshot_payload:
            raise ValueError("snapshots file must contain a snapshots object")
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    if (root / "rankings.json").exists():
        raise FileExistsError("Use a new output root; frozen rankings exist")
    results = []
    for case in cases:
        # Never invent a cutoff timestamp from a calendar date. No historical packet is
        # accepted without an actual cutoff; date-only cases remain evidence-limited.
        docs = []
        if source_packets and case["publication_at"]:
            file = Path(source_packets) / (case["case_id"] + ".json")
            if file.exists():
                docs = json.loads(file.read_text())
        request = InvestigationRequest(
            headline=case["headline"],
            teaser_text=case["teaser_text"] or case["headline"],
            publication_date=case["publication_date"],
            publication_at=case["publication_at"],
            evaluation_class=payload["evaluation_class"],
            previously_used_for_development=payload["evaluation_class"] == "development_regression",
        )
        report = Investigator(root).analyze(
            request,
            documents=docs,
            historical_blind=bool(case["publication_at"]),
            case_id=case["case_id"],
        )
        report["reference_input_completeness"] = (
            "complete" if case["teaser_text"] else "headline_only"
        )
        blob = _teaser_blob(case)
        report["offline_hypotheses"] = screen(blob, limit=8)
        report["offline_hypothesis_status"] = (
            "unverified_sector_universe_suggestions"
            if report["offline_hypotheses"]
            else "no_local_sector_hypotheses"
        )
        if snapshot_payload is not None:
            resolved = resolve_case_snapshots(snapshot_payload, case.get("publication_date"))
            if resolved["status"] != "ok" or not resolved["snapshots"]:
                report["market_hypotheses"] = []
                report["market_hypothesis_meta"] = {
                    "status": resolved["status"],
                    "snapshot_as_of": resolved.get("snapshot_as_of"),
                    "pit_basis": resolved.get("pit_basis"),
                }
            else:
                market = market_rank(blob, resolved["snapshots"], limit=8)
                report["market_hypotheses"] = market["ranking"]
                report["market_hypothesis_meta"] = {
                    "clues": market["clues"],
                    "sectors": market["sectors"],
                    "snapshot_as_of": resolved.get("snapshot_as_of"),
                    "snapshot_coverage": market["snapshot_coverage"],
                    "ranked_before_limit": market["ranked_before_limit"],
                    "pit_basis": resolved.get("pit_basis"),
                    "status": (
                        "unverified_chart_universe_suggestions"
                        if market["ranking"]
                        else "no_market_hypotheses"
                    ),
                }
        else:
            report["market_hypotheses"] = []
            report["market_hypothesis_meta"] = {"status": "snapshots_not_provided"}
        report["source_packet_status"] = (
            "no_exact_cutoff" if not case["publication_at"] else "provided" if docs else "missing"
        )
        results.append(report)
    return freeze_analysis(
        {
            "evaluation_class": payload["evaluation_class"],
            "execution_mode": "offline_no_solution_files",
            "corpus_kind": payload.get("corpus_kind"),
            "cases": results,
        },
        root / "rankings.json",
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--source-packets", type=Path)
    parser.add_argument(
        "--snapshots",
        type=Path,
        help="Optional market_screen export JSON for unverified chart hypotheses",
    )
    args = parser.parse_args(argv)
    frozen = run_scan(args.inputs, args.root, args.source_packets, args.snapshots)
    print(
        json.dumps(
            {"cases": len(frozen["report"]["cases"]), "ranking_sha256": frozen["sha256"]}, indent=2
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
