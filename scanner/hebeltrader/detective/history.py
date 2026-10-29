"""Offline case-history inventory and post-freeze evaluation.

Never call inventory_history from candidate retrieval or scan ranking. History is a
partial development record, not an independent accuracy benchmark.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path


def inventory_history(path) -> dict:
    path = Path(path)
    raw = path.read_text(encoding="utf-8")
    cases = []
    for line in raw.replace("\\n", "\n").splitlines():
        if not re.match(r"^\| HT-\d{3} \|", line):
            continue
        fields = [part.strip() for part in line.strip("|").split("|")]
        case_id, context, identity, warrant, status, notes = fields[:6]

        def clean(value):
            return value.replace("**", "")

        context, identity, status = map(clean, (context, identity, status))
        title = re.search("„([^“]+)“", context)
        # A resolution date is not the publication date of the teaser.
        date = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", context) if title else None
        unresolved = "Ungelöst" in status
        cases.append(
            {
                "case_id": case_id,
                "context": context,
                "original_text": None,
                "original_text_available": False,
                "available_excerpt": title.group(1) if title else None,
                "publication_date": f"{date[3]}-{date[2]}-{date[1]}" if date else None,
                "publication_time": None,
                "publication_time_available": False,
                "historical_top3": None,
                "status": "unresolved" if unresolved else "known",
                "reported_identity": identity,
                "verified_identity": None,
                "call_wkn": None if clean(warrant) == "unbekannt" else clean(warrant),
                "label_provenance": status,
                "notes": clean(notes),
                "evaluation_class": "development_regression",
                "provenance": {
                    "path": str(path),
                    "source_row": line,
                    "sha256": hashlib.sha256(raw.encode()).hexdigest(),
                },
            }
        )
    # Offline inventory only. Candidate ranking never calls this function.
    reference_path = path.parent.parent / "data/hebeltrader/teaser-cases.json"
    if reference_path.exists():
        from .reference_cases import load_references

        structured = {c["case_id"]: c for c in load_references(reference_path)["cases"]}
        for case in cases:
            reference = structured.get(case["case_id"])
            if reference:
                case["original_text"] = reference["teaser_text"]
                case["original_text_available"] = reference["teaser_text"] is not None
                case["publication_date"] = reference["publication_date"]
                case["first_prediction"] = reference["first_prediction"]
                case["historical_outcome"] = reference["outcome"]
                case["reference_number"] = reference["reference_number"]
                case["structured_reference_path"] = str(reference_path)
    return {
        "cases": cases,
        "case_count": len(cases),
        "evaluation_class": "development_regression",
        "independent_benchmark": False,
    }


def _canonical(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def freeze_analysis(report, path) -> dict:
    """Create an exclusive, read-only snapshot, with a canonical report SHA256.

    The digest detects accidental changes; this is not a signed audit system.
    No solution history or labels are read here.
    """
    snapshot = json.loads(_canonical(report))
    envelope = {
        "format": "hebeltrader-frozen-analysis-v1",
        "frozen_at": datetime.now(UTC).isoformat(),
        "sha256": hashlib.sha256(_canonical(snapshot)).hexdigest(),
        "report": snapshot,
    }
    path = Path(path)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(envelope, handle, ensure_ascii=False, sort_keys=True, allow_nan=False)
    path.chmod(0o444)
    return envelope


def _cases(value):
    if isinstance(value, list):
        return value
    return value.get("cases", [value])


def _asset(value):
    return value.get("asset_id") or value.get("identity", {}).get("asset_id")


def evaluate_frozen(path, labels_path) -> dict:
    """Read labels only after validating an already frozen analysis snapshot."""
    envelope = json.loads(Path(path).read_text(encoding="utf-8"))
    if (
        envelope.get("format") != "hebeltrader-frozen-analysis-v1"
        or "report" not in envelope
        or not envelope.get("sha256")
    ):
        raise ValueError("A frozen analysis with SHA256 is required")
    if hashlib.sha256(_canonical(envelope["report"])).hexdigest() != envelope["sha256"]:
        raise ValueError("Frozen analysis SHA256 mismatch")
    labels = json.loads(Path(labels_path).read_text(encoding="utf-8"))
    labels_by_id = {item["case_id"]: item for item in _cases(labels)}
    results = []
    for case in _cases(envelope["report"]):
        case_id = case.get("case_id")
        label = labels_by_id.get(case_id, {})
        unresolved = label.get("status") == "unresolved" or not _asset(label)
        candidates = case.get("candidates", case.get("top3", []))[:3]
        abstained = case.get("identification", {}).get("status") == "not_identified"
        rank = (
            next(
                (
                    i
                    for i, candidate in enumerate(candidates, 1)
                    if _asset(candidate) == _asset(label)
                ),
                None,
            )
            if not unresolved
            else None
        )
        # Historical IDs cannot be promoted to independent data by a label flag.
        historical = bool(re.fullmatch(r"HT-\d{3}", str(case_id)))
        classification = (
            "development_regression"
            if historical
            else label.get("evaluation_class", case.get("evaluation_class", "unclassified"))
        )
        if classification == "independent":
            try:
                confirmed = datetime.fromisoformat(label["confirmed_at"].replace("Z", "+00:00"))
                frozen = datetime.fromisoformat(envelope["frozen_at"])
                eligible = (
                    confirmed.utcoffset() is not None
                    and confirmed > frozen
                    and label.get("original_sha256") == case.get("teaser_sha256")
                    and bool(case.get("teaser_sha256"))
                    and label.get("solution_source")
                    and label.get("previously_used_for_development") is False
                )
            except (KeyError, TypeError, ValueError):
                eligible = False
            if not eligible:
                classification = "independent_unverified"
        results.append(
            {
                "case_id": case_id,
                "correct_rank": rank,
                "original_top3": candidates,
                "abstained": abstained,
                "graded": not unresolved,
                "unresolved": unresolved,
                "candidate_rank1_hit": rank == 1,
                "candidate_top3_hit": rank is not None,
                "top1_hit": not abstained and rank == 1,
                "top3_hit": not abstained and rank is not None,
                "false_assignment": not unresolved and not abstained and rank != 1,
                "countercandidate_count": case.get("countercandidate_count"),
                "source_quality": case.get("source_quality", {}),
                "analysis_seconds": case.get("analysis_seconds"),
                "evaluation_class": classification,
            }
        )

    def summarize(rows):
        graded = sum(row["graded"] for row in rows)
        top1 = sum(row["top1_hit"] for row in rows)
        top3 = sum(row["top3_hit"] for row in rows)
        return {
            "total": len(rows),
            "graded": graded,
            "unresolved": sum(row["unresolved"] for row in rows),
            "abstentions": sum(row["abstained"] for row in rows),
            "false_assignments": sum(row["false_assignment"] for row in rows),
            "top1_hits": top1,
            "top3_hits": top3,
            "top1_rate": None,
            "top3_rate": None,
            "rates_status": "counts_only_no_validated_complete_independent_corpus",
        }

    return {
        "analysis_sha256": envelope["sha256"],
        "cases": results,
        "summary": summarize(results),
        "independent": summarize(
            [row for row in results if row["evaluation_class"] == "independent"]
        ),
        "development_regression": summarize(
            [row for row in results if row["evaluation_class"] == "development_regression"]
        ),
    }
