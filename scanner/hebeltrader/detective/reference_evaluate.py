"""Post-freeze reference evaluator. Solutions are accessible only in this process."""

import argparse
import json
import re
from pathlib import Path

from .case_journal import read_frozen
from .reference_cases import historical_summary, load_references


def _company(value):
    value = value.casefold() if value else ""
    value = re.sub(
        r"\b(?:incorporated|inc|corporation|corp|limited|ltd|plc|ag|se|sa|nv|spa)\b",
        " ",
        value,
    )
    return re.sub(r"[^a-z0-9]", "", value)


def evaluate(rankings, references):
    frozen = read_frozen(rankings)  # Integrity check before loading any solutions.
    reference = load_references(references)
    labels = {c["case_id"]: c for c in reference["cases"]}
    reports = frozen["report"]["cases"]
    if len(reports) != len(labels) or {r["case_id"] for r in reports} != set(labels):
        raise ValueError("A complete unique set of frozen reference cases is required")
    results = []
    for report in reports:
        label = labels[report["case_id"]]
        rank = None
        if label["outcome"] != "unresolved":
            for i, candidate in enumerate(report.get("candidates", [])[:3], 1):
                identity = candidate.get("identity", {})
                if (
                    label["actual_ticker"] and identity.get("ticker") == label["actual_ticker"]
                ) or _company(identity.get("name")) == _company(label["actual_company"]):
                    rank = i
                    break
        hypothesis_rank = None
        market_rank = None
        if label["actual_company"]:
            for i, candidate in enumerate(report.get("offline_hypotheses", []), 1):
                if (
                    label["actual_ticker"] and candidate.get("ticker") == label["actual_ticker"]
                ) or _company(candidate.get("name")) == _company(label["actual_company"]):
                    hypothesis_rank = i
                    break
            for i, candidate in enumerate(report.get("market_hypotheses", []), 1):
                if (
                    label["actual_ticker"] and candidate.get("ticker") == label["actual_ticker"]
                ) or _company(candidate.get("name")) == _company(label["actual_company"]):
                    market_rank = i
                    break
        results.append(
            {
                "case_id": label["case_id"],
                "original_historical_prediction": label["first_prediction"],
                "historical_outcome": label["outcome"],
                "new_top3": report.get("candidates", [])[:3],
                "correct_rank": rank,
                "offline_hypothesis_rank": hypothesis_rank,
                "offline_hypotheses": report.get("offline_hypotheses", []),
                "offline_hypothesis_status": report.get("offline_hypothesis_status"),
                "market_hypothesis_rank": market_rank,
                "market_hypotheses": report.get("market_hypotheses", []),
                "market_hypothesis_meta": report.get("market_hypothesis_meta"),
                "abstained": report["identification"]["status"] == "not_identified",
                "countercandidate_count": report.get("countercandidate_count"),
                "input_completeness": report.get("reference_input_completeness"),
                "analysis_seconds": report.get("analysis_seconds"),
                "evaluation_class": "development_regression",
            }
        )
    return {
        "ranking_sha256": frozen["sha256"],
        "historical_conversation": historical_summary(reference),
        "regression": {
            "cases": len(results),
            "graded_cases": sum(label["actual_company"] is not None for label in labels.values()),
            "abstentions": sum(c["abstained"] for c in results),
            "candidate_top1_hits": sum(c["correct_rank"] == 1 for c in results),
            "candidate_top3_hits": sum(c["correct_rank"] is not None for c in results),
            "top1_rate": None,
            "top3_rate": None,
            "rate_status": "known_development_cases_not_independent_benchmark",
        },
        "offline_hypothesis_coverage": {
            "graded_cases": sum(label["actual_company"] is not None for label in labels.values()),
            "suggestion_cases": sum(bool(r.get("offline_hypotheses")) for r in reports),
            "solution_in_first_suggestion": sum(
                result["offline_hypothesis_rank"] == 1 for result in results
            ),
            "solution_in_top3_suggestions": sum(
                result["offline_hypothesis_rank"] is not None
                and result["offline_hypothesis_rank"] <= 3
                for result in results
            ),
            "solution_in_top8_suggestions": sum(
                result["offline_hypothesis_rank"] is not None for result in results
            ),
            "interpretation": (
                "Unverified local sector-universe suggestions only; not evidence-backed "
                "identifications or an independent benchmark."
            ),
        },
        "market_hypothesis_coverage": {
            "graded_cases": sum(label["actual_company"] is not None for label in labels.values()),
            "suggestion_cases": sum(bool(r.get("market_hypotheses")) for r in reports),
            "snapshots_not_provided": sum(
                (r.get("market_hypothesis_meta") or {}).get("status") == "snapshots_not_provided"
                for r in reports
            ),
            "solution_in_first_suggestion": sum(
                result["market_hypothesis_rank"] == 1 for result in results
            ),
            "solution_in_top3_suggestions": sum(
                result["market_hypothesis_rank"] is not None
                and result["market_hypothesis_rank"] <= 3
                for result in results
            ),
            "solution_in_top8_suggestions": sum(
                result["market_hypothesis_rank"] is not None for result in results
            ),
            "interpretation": (
                "Unverified chart-universe suggestions only; not evidence-backed "
                "identifications or an independent benchmark."
            ),
        },
        "missing_full_text_count": sum(c["teaser_text"] is None for c in reference["cases"]),
        "independent_real_blind_tests": 0,
        "cases": results,
        "limitations": [
            "Headline-only inputs are not complete original teasers.",
            "No exact publication times are present in this reconstruction.",
            "No identification quality proven without authentic dated candidate-source packets.",
            "The original 10/7 history (HT-016 dropped) is not the performance of this new scan.",
            "New reference cases are development regressions, not independent blind tests.",
            "Market hypotheses require an external snapshot export and remain unverified.",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rankings", type=Path, required=True)
    parser.add_argument(
        "--references", type=Path, default=Path("data/hebeltrader/teaser-cases.json")
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = evaluate(args.rankings, args.references)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
