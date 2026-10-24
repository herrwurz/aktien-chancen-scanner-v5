"""Deterministic retrieval metrics with real/synthetic and lookahead separation."""

from datetime import datetime


def _timestamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _metrics(cases):
    labelled = [row for row in cases if row.get("target")]
    abstention = [row for row in cases if not row.get("target")]

    def hit_at(size):
        if not labelled:
            return None
        return sum(row["target"] in row.get("ranked", [])[:size] for row in labelled) / len(
            labelled
        )

    violations = []
    for row in cases:
        if not row.get("as_of"):
            continue
        as_of = _timestamp(row["as_of"])
        if any(_timestamp(value) > as_of for value in row.get("evidence_available_at", [])):
            violations.append(row["case_id"])
    latencies = [float(row["latency_ms"]) for row in cases if row.get("latency_ms") is not None]
    costs = [float(row["cost_eur"]) for row in cases if row.get("cost_eur") is not None]
    requests = [int(row["request_count"]) for row in cases if row.get("request_count") is not None]
    predictions = [prediction for row in cases for prediction in row.get("ranked", [])[:3]]
    false_predictions = sum(
        prediction != row.get("target") for row in cases for prediction in row.get("ranked", [])[:3]
    )
    return {
        "case_count": len(cases),
        "labelled_case_count": len(labelled),
        "recall_at_10": hit_at(10),
        "recall_at_50": hit_at(50),
        "top_1": hit_at(1),
        "top_3": hit_at(3),
        "abstention_case_count": len(abstention),
        "abstention_accuracy": (
            sum(
                row.get("status") in {"unresolved", "insufficiently_constrained"}
                for row in abstention
            )
            / len(abstention)
            if abstention
            else None
        ),
        "lookahead_violations": violations,
        "measured_latency_case_count": len(latencies),
        "max_latency_ms": max(latencies, default=None),
        "total_cost_eur": sum(costs) if costs else None,
        "total_request_count": sum(requests) if requests else None,
        "false_positive_predictions_at_3": false_predictions,
        "prediction_count_at_3": len(predictions),
        "false_positive_rate_at_3": (false_predictions / len(predictions) if predictions else 0.0),
        "market_coverage": sorted({row["market"] for row in cases if row.get("market")}),
        "sector_coverage": sorted({row["sector"] for row in cases if row.get("sector")}),
    }


def evaluate_cases(cases):
    rows = list(cases)
    return {
        "all": _metrics(rows),
        "real_archived": _metrics([row for row in rows if row.get("kind") == "real_archived"]),
        "synthetic": _metrics([row for row in rows if row.get("kind") == "synthetic"]),
    }
