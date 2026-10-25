"""Deterministic preflight artifacts for an externally supplied real teaser."""

import argparse
import csv
import hashlib
import json
from pathlib import Path


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def write_acceptance_preflight(
    *, teaser_path, publication_at, rights_status, research_index, output_dir
):
    teaser_path = Path(teaser_path)
    research_index = Path(research_index)
    output_dir = Path(output_dir)
    blockers = []
    if not teaser_path.is_file():
        blockers.append("original_teaser_missing")
    if not publication_at:
        blockers.append("publication_time_missing")
    if not research_index.is_file():
        blockers.append("research_index_missing")
    if not rights_status:
        blockers.append("rights_status_missing")
    payload = {
        "schema_version": 3,
        "status": "pending_external_material" if blockers else "ready_for_read_only_scan",
        "blockers": blockers,
        "publication_at": publication_at,
        "rights_status": rights_status,
        "teaser_sha256": _sha(teaser_path.read_bytes()) if teaser_path.is_file() else None,
        "research_index_sha256": (
            _sha(research_index.read_bytes()) if research_index.is_file() else None
        ),
        "real_end_to_end_completed": False,
    }
    stable = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    payload["payload_sha256"] = _sha(stable)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "preflight.json"
    csv_path = output_dir / "preflight.csv"
    sha_path = output_dir / "preflight.sha256"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=("status", "blocker"))
        writer.writeheader()
        rows = blockers or [""]
        writer.writerows({"status": payload["status"], "blocker": item} for item in rows)
    sha_path.write_text(f"{_sha(json_path.read_bytes())}  {json_path.name}\n", encoding="utf-8")
    return {
        **payload,
        "artifacts": {"json": str(json_path), "csv": str(csv_path), "sha256": str(sha_path)},
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--teaser", required=True, type=Path)
    parser.add_argument("--publication-at")
    parser.add_argument("--rights-status")
    parser.add_argument("--research-index", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    result = write_acceptance_preflight(
        teaser_path=args.teaser,
        publication_at=args.publication_at,
        rights_status=args.rights_status,
        research_index=args.research_index,
        output_dir=args.output,
    )
    print(json.dumps({"status": result["status"], "artifacts": result["artifacts"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
