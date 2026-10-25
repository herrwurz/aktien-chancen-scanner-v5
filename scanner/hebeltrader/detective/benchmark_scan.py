"""Blind scanner process: consumes teaser inputs, never solution labels."""

import argparse
import hashlib
import json
from pathlib import Path
from time import perf_counter

from scanner.config import Settings

from .factory import build_detective
from .schemas import DetectiveRequest


def _sha(value):
    return hashlib.sha256(value.encode()).hexdigest()


def scan_manifest(manifest_path, service):
    started = perf_counter()
    manifest_bytes = Path(manifest_path).read_bytes()
    manifest = json.loads(manifest_bytes)
    rows = []
    for case in manifest["cases"]:
        text = case["teaser_text"]
        result = service.analyze(
            DetectiveRequest(
                analysis_mode=case.get("analysis_mode", "hypothesis"),
                teaser_text=text,
                publication_at=case.get("publication_at"),
            )
        )
        coverage = result["candidate_source"]["coverage"]
        rows.append(
            {
                "case_id": case["case_id"],
                "teaser_sha256": _sha(text),
                "input_text": text,
                "status": result["identification"]["status"],
                "reason": result["identification"].get("reason"),
                "failure_code": result["identification"].get("failure_code"),
                "ranked_asset_ids": [row["asset_id"] for row in result["candidates"]],
                "stage_a_asset_ids": list(coverage.get("stage_a_asset_ids") or []),
                "visible_universe_size": coverage.get("visible_universe_size"),
                "matched_before_limit": coverage.get("matched_before_limit"),
                "channel_limit": coverage.get("channel_limit"),
                "channel_counts": coverage.get("channel_counts") or {},
                "channel_matched_before_limit": coverage.get("channel_matched_before_limit") or {},
            }
        )
    stable = json.dumps(rows, sort_keys=True, separators=(",", ":"))
    coverage = (
        getattr(service.candidate_source, "coverage", {})
        if hasattr(service, "candidate_source")
        else {}
    )
    return {
        "schema_version": 3,
        "corpus_kind": manifest["corpus_kind"],
        "input_manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "ranking_payload_sha256": _sha(stable),
        "runtime_ms": round((perf_counter() - started) * 1000, 3),
        "request_count": int(coverage.get("requests_attempted", 0)),
        "cost_eur": float(coverage.get("cost_eur", 0)),
        "cases": rows,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", required=True, type=Path)
    parser.add_argument("--research-index", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    service = build_detective(
        Settings(
            _env_file=None,
            detective_research_mode="indexed_research",
            detective_research_index=args.research_index,
        )
    )
    report = scan_manifest(args.inputs, service)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
