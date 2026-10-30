"""Solution-free, offline development scan. Mount inputs/packets only, never references."""

import argparse
import json
from pathlib import Path

from .history import freeze_analysis
from .investigation import InvestigationRequest, Investigator
from .structure_screen import screen

_FIELDS = {"case_id", "headline", "teaser_text", "publication_date", "publication_at"}


def run_scan(inputs, root, source_packets=None):
    payload = json.loads(Path(inputs).read_text())
    if set(payload) != {"schema_version", "evaluation_class", "cases"}:
        raise ValueError("forbidden scan manifest fields")
    if payload["evaluation_class"] != "development_regression":
        raise ValueError("Known-reference scan is always development_regression")
    cases = payload["cases"]
    if any(set(case) != _FIELDS for case in cases):
        raise ValueError("forbidden scan fields: solutions and old predictions must stay separate")
    if len({c["case_id"] for c in cases}) != len(cases):
        raise ValueError("duplicate case ids")
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
            evaluation_class="development_regression",
            previously_used_for_development=True,
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
        report["offline_hypotheses"] = screen(
            "\n".join(part for part in (case["headline"], case["teaser_text"]) if part),
            limit=8,
        )
        report["offline_hypothesis_status"] = (
            "unverified_sector_universe_suggestions"
            if report["offline_hypotheses"]
            else "no_local_sector_hypotheses"
        )
        report["source_packet_status"] = (
            "no_exact_cutoff" if not case["publication_at"] else "provided" if docs else "missing"
        )
        results.append(report)
    return freeze_analysis(
        {
            "evaluation_class": "development_regression",
            "execution_mode": "offline_no_solution_files",
            "cases": results,
        },
        root / "rankings.json",
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--source-packets", type=Path)
    args = parser.parse_args(argv)
    frozen = run_scan(args.inputs, args.root, args.source_packets)
    print(
        json.dumps(
            {"cases": len(frozen["report"]["cases"]), "ranking_sha256": frozen["sha256"]}, indent=2
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
