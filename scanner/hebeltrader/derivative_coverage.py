"""Deterministic derivative quote coverage and acquisition planning."""

import csv
import io
import json
from collections import Counter
from pathlib import Path

from .derivative_quotes import verify_product_terms
from .eodhd import canonical, exclusive, sha

PRIORITIES = (
    "verified_executable_quotes",
    "restricted_archive",
    "terms_only",
    "insufficient_data",
)


def build_hs5rmp_coverage(*, product_terms, quote_archive=None, tiingo=None):
    terms = verify_product_terms(product_terms)
    blockers = []
    if not terms["verified"]:
        blockers.append("historical_product_terms_unverified")
    if quote_archive is None:
        blockers.append("historical_bid_ask_unavailable")
    underlying = {
        "supplied": tiingo is not None,
        "observations": len(tiingo.get("payload", [])) if tiingo else 0,
        "raw_sha256": tiingo.get("raw_sha256") if tiingo else None,
        "scope": "JNJ underlying plausibility only",
        "may_replace_derivative_quotes": False,
    }
    return {
        "format_version": 1,
        "instrument": "HS5RMP",
        "product_terms": terms,
        "quote_archive": {
            "supplied": quote_archive is not None,
            "manifest_sha256": quote_archive.get("manifest_sha256") if quote_archive else None,
        },
        "underlying_plausibility": underlying,
        "blockers": blockers,
        "derivative_result": {
            "status": "blocked" if blockers else "ready_for_execution_model",
            "return_pct": None,
            "training_eligible": False,
            "reason": "No derivative result is computed by the coverage report.",
        },
    }


def _priority(row):
    availability = row.get("quote_availability")
    if availability == "approved":
        return "verified_executable_quotes"
    if availability == "partial":
        return "restricted_archive"
    if row.get("terms_available"):
        return "terms_only"
    return "insufficient_data"


def prioritize_acquisition(recommendations):
    rows = []
    for source in recommendations:
        row = {
            key: value
            for key, value in source.items()
            if key not in {"source_categories", "directory_category"}
        }
        row["priority"] = _priority(source)
        rows.append(row)
    rows.sort(key=lambda item: (PRIORITIES.index(item["priority"]), item["recommendation_key"]))
    counts = Counter(row["priority"] for row in rows)
    return {
        "format_version": 1,
        "recommendation_count": len(rows),
        "counts": {priority: counts.get(priority, 0) for priority in PRIORITIES},
        "rows": rows,
        "classification_basis": "product terms and quote evidence only",
        "training_labels_from_directories": False,
    }


def write_coverage(prefix, report):
    prefix = Path(prefix)
    json_path = Path(f"{prefix}.json")
    csv_path = Path(f"{prefix}.csv")
    hash_path = Path(f"{prefix}.sha256")
    json_bytes = canonical(report)
    fields = sorted({key for row in report["rows"] for key in row})
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in report["rows"]:
        writer.writerow(
            {
                key: (
                    json.dumps(row[key], sort_keys=True)
                    if isinstance(row.get(key), (list, dict))
                    else row.get(key)
                )
                for key in fields
            }
        )
    csv_bytes = buffer.getvalue().encode()
    digest = canonical({"json_sha256": sha(json_bytes), "csv_sha256": sha(csv_bytes)})
    exclusive(json_path, json_bytes)
    exclusive(csv_path, csv_bytes)
    exclusive(hash_path, digest)
    return [json_path, csv_path, hash_path]
