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
    violations = []
    top_1 = top_3 = abstentions = false_assignments = missing = 0
    for row in rankings["cases"]:
        label = labels[row["case_id"]]
        haystack = f"{row['case_id']} {row.get('input_text', '')}".casefold()
        leaked = [
            value
            for value in label.get("forbidden_identifiers", [])
            if value and value.casefold() in haystack
        ]
        if leaked:
            violations.append({"case_id": row["case_id"], "identifiers": leaked})
        ranked = row["ranked_asset_ids"]
        target = label["asset_id"]
        top_1 += bool(ranked and ranked[0] == target)
        top_3 += target in ranked[:3]
        abstentions += not ranked
        false_assignments += bool(ranked and target not in ranked[:3])
        missing += label.get("expected_in_universe") is False
    if violations:
        raise ValueError(f"solution leakage detected: {violations}")
    total = len(rankings["cases"])
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
    real_count = total if rankings["corpus_kind"] == "real_original" else 0
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
