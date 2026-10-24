"""Run a predeclared candidate-retrieval corpus without embedding solutions in teasers."""

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from time import perf_counter

from scanner.news import NewsItem
from scanner.research import AssetIdentity
from scanner.research_evaluation import evaluate_cases
from scanner.research_index.builder import build_index
from scanner.research_index.models import CandidateQuery
from scanner.research_index.repository import ResearchIndex


def run_benchmark(definition_path, index_path):
    definition = json.loads(Path(definition_path).read_text())
    as_of = datetime.fromisoformat(definition["as_of"].replace("Z", "+00:00"))
    assets = []
    by_key = {}
    for row in definition["universe"]:
        identity = AssetIdentity(
            asset_type="stock",
            name=row["name"],
            ticker=row["ticker"],
            cik=row["cik"],
            country=row["country"],
            sector=row.get("sector"),
            instrument_type=row.get("instrument_type", "operating_company"),
            instrument_type_status="source_verified",
            source_id="synthetic-benchmark-universe",
            retrieved_at=as_of,
            source_available_at=as_of,
        )
        assets.append(identity)
        by_key[row["asset_key"]] = identity
    news = []
    for row in definition["evidence"]:
        available = datetime.fromisoformat(row["available_at"].replace("Z", "+00:00"))
        identity = by_key[row["asset_key"]]
        news.append(
            NewsItem(
                source_id=row["source_id"],
                source_type="PRIMARY",
                url=f"https://synthetic.invalid/{row['source_id']}",
                title=row["title"],
                published_at=available,
                first_seen_at=available,
                retrieved_at=available,
                source_available_at=available,
                company_identifiers={"cik": [identity.cik]},
                event_type=row["event_type"],
                event_confidence="source_claim",
                evidence_status="synthetic_benchmark",
                license_status="permitted_metadata",
                content_hash=hashlib.sha256(row["title"].encode()).hexdigest(),
                origin_id=row["source_id"],
            )
        )
    build_index(index_path, assets=assets, events=[], facts=[], news=news)
    index = ResearchIndex(index_path)
    violations, rows = [], []
    for case in definition["cases"]:
        target_key = definition["labels"].get(case["case_id"])
        target = by_key.get(target_key)
        teaser = case["teaser"].casefold()
        if target and any(
            value and str(value).casefold() in teaser
            for value in (target.name, target.ticker, target.cik)
        ):
            violations.append(case["case_id"])
        started = perf_counter()
        result = index.candidates(
            CandidateQuery(**case["query"], require_unique_top=True),
            as_of=as_of,
            limit=50,
        )
        latency_ms = (perf_counter() - started) * 1000
        ranked = (
            [f"cik:{hit.identity.cik}" for hit in result.candidates]
            if result.status == "ok"
            else []
        )
        rows.append(
            {
                "case_id": case["case_id"],
                "kind": case["kind"],
                "target": f"cik:{target.cik}" if target else None,
                "ranked": ranked,
                "status": result.status,
                "market": case["market"],
                "sector": case["sector"],
                "as_of": definition["as_of"],
                "evidence_available_at": [],
                "latency_ms": latency_ms,
                "cost_eur": 0.0,
                "request_count": 0,
            }
        )
    stable_cases = [
        {key: value for key, value in row.items() if key != "latency_ms"} for row in rows
    ]
    ranking_sha = hashlib.sha256(
        json.dumps(stable_cases, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {
        "schema_version": 1,
        "corpus": {
            "case_count": len(rows),
            "kind_counts": {
                kind: sum(row["kind"] == kind for row in rows)
                for kind in sorted({row["kind"] for row in rows})
            },
            "solution_identifiers_in_teasers": violations,
            "selection_independent_of_teasers": definition["selection_independent_of_teasers"],
            "ranking_payload_sha256": ranking_sha,
        },
        "metrics": evaluate_cases(rows),
        "cases": rows,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--definition", required=True, type=Path)
    parser.add_argument("--index", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    report = run_benchmark(args.definition, args.index)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
