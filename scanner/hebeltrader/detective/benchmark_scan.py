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
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    rows = []
    for case in manifest["cases"]:
        text = case["teaser_text"]
        result = service.analyze(
            DetectiveRequest(
                teaser_text=text,
                publication_at=case.get("publication_at"),
            )
        )
        rows.append(
            {
                "case_id": case["case_id"],
                "teaser_sha256": _sha(text),
                "input_text": text,
                "status": result["identification"]["status"],
                "ranked_asset_ids": [row["asset_id"] for row in result["candidates"]],
                "visible_universe_size": result["candidate_source"]["coverage"].get(
                    "visible_universe_size"
                ),
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
