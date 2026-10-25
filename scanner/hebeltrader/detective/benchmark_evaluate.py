"""Evaluate immutable blind rankings after the scanner process has exited."""

import argparse
import hashlib
import json
from pathlib import Path


def _rate(value, total):
    return value / total if total else 0.0


def evaluate_rankings(rankings_path, labels_path):
    rankings = json.loads(Path(rankings_path).read_text(encoding="utf-8"))
    labels = json.loads(Path(labels_path).read_text(encoding="utf-8"))["cases"]
    rows = rankings.get("cases", [])
    case_ids = [row.get("case_id") for row in rows]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("duplicate benchmark case ids")
    if set(case_ids) != set(labels):
        raise ValueError("benchmark case integrity mismatch")
    stable = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
    if rankings.get("ranking_payload_sha256") != hashlib.sha256(stable).hexdigest():
        raise ValueError("ranking payload integrity mismatch")
    violations = []
    top_1 = top_3 = abstentions = false_assignments = missing = 0
    valid_real_cases = 0
    for row in rows:
        label = labels[row["case_id"]]
        if (
            row.get("teaser_sha256")
            != hashlib.sha256(row.get("input_text", "").encode()).hexdigest()
        ):
            raise ValueError("teaser integrity mismatch")
        if rankings["corpus_kind"] == "real_original":
            required = ("solution_source", "reviewer", "confirmed_at", "original_sha256")
            if not all(label.get(field) for field in required):
                raise ValueError("real benchmark provenance missing")
            valid_real_cases += 1
        haystack = f"{row['case_id']} {row.get('input_text', '')}".casefold()
        leaked = [
            value
            for value in label.get("forbidden_identifiers", [])
            if value and value.casefold() in haystack
        ]
        if leaked:
            violations.append({"case_id": row["case_id"], "identifiers": leaked})
        ranked = row["ranked_asset_ids"] if row.get("status") != "unresolved" else []
        target = label["asset_id"]
        top_1 += bool(ranked and ranked[0] == target)
        top_3 += target in ranked[:3]
        abstentions += not ranked
        false_assignments += bool(ranked and target not in ranked[:3])
        missing += label.get("expected_in_universe") is False
    if violations:
        raise ValueError(f"solution leakage detected: {violations}")
    total = len(rows)
    metrics = {
        "case_count": total,
        "top_1_count": top_1,
        "top_1_rate": _rate(top_1, total),
        "top_3_count": top_3,
        "top_3_rate": _rate(top_3, total),
        "abstention_count": abstentions,
        "false_assignment_count": false_assignments,
        "missing_universe_count": missing,
    }
    payload = json.dumps(metrics, sort_keys=True, separators=(",", ":")).encode()
    real_count = valid_real_cases
    return {
        "schema_version": 3,
        "corpus_kind": rankings["corpus_kind"],
        "metrics": metrics,
        "leakage_violations": [],
        "real_benchmark_status": (
            "measured" if real_count >= 10 else "insufficient_real_benchmark_coverage"
        ),
        "metrics_sha256": hashlib.sha256(payload).hexdigest(),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rankings", required=True, type=Path)
    parser.add_argument("--labels", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    report = evaluate_rankings(args.rankings, args.labels)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
