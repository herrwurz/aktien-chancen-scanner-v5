"""Build many SEC source packets from one manifest (parallel-friendly).

Reads ``batch-10/manifest.json``-style entries, reuses existing packets when
``reuse_packet`` is set, otherwise calls ``build_packet`` for each case.
"""

from __future__ import annotations

import argparse
import json
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from .build_sec_packet import build_packet


def _parse_issuer(raw: str) -> dict:
    parts = raw.split(":")
    if len(parts) < 3:
        raise ValueError(f"bad issuer {raw!r}; expected ticker:cik:name")
    ticker, cik, name, *rest = parts
    return {
        "ticker": ticker,
        "cik": cik.zfill(10),
        "name": name,
        "extra_8k": bool(rest and rest[0] in {"1", "true", "extra8k"}),
    }


def build_one(entry: dict, *, out_dir: Path, raw_root: Path) -> dict:
    case_id = entry["case_id"]
    out_path = out_dir / f"{case_id}.json"
    meta_path = out_dir / f"{case_id}.meta.json"
    if entry.get("reuse_packet"):
        src = Path(entry["reuse_packet"])
        shutil.copy(src, out_path)
        meta = {
            "case_id": case_id,
            "reused_from": str(src),
            "documents": len(json.loads(out_path.read_text(encoding="utf-8"))),
        }
        meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
        return {"case_id": case_id, "status": "reused", "path": str(out_path), **meta}

    cutoff = datetime.fromisoformat(entry["cutoff"])
    if cutoff.utcoffset() is None:
        raise ValueError(f"{case_id}: cutoff must include timezone offset")
    issuers = [_parse_issuer(entry["lead"]), *(_parse_issuer(p) for p in entry.get("peers", []))]
    needles = {issuers[0]["ticker"]: tuple(entry.get("needles") or ())}
    raw_dir = raw_root / case_id
    docs, meta_rows = build_packet(
        issuers, cutoff=cutoff, raw_dir=raw_dir, needles_by_ticker=needles
    )
    out_path.write_text(json.dumps(docs, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    meta = {
        "case_id": case_id,
        "cutoff_publication_at": entry["cutoff"],
        "documents": meta_rows,
        "needles": entry.get("needles") or [],
    }
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {
        "case_id": case_id,
        "status": "built",
        "path": str(out_path),
        "documents": len(docs),
    }


def run_batch(manifest: Path, *, out_dir: Path, raw_root: Path, workers: int = 3) -> dict:
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    entries = payload["cases"]
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_root.mkdir(parents=True, exist_ok=True)
    results = []
    errors = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {
            pool.submit(build_one, entry, out_dir=out_dir, raw_root=raw_root): entry["case_id"]
            for entry in entries
        }
        for future in as_completed(futures):
            case_id = futures[future]
            try:
                results.append(future.result())
            except Exception as exc:  # noqa: BLE001 — batch must continue
                errors.append({"case_id": case_id, "error": f"{type(exc).__name__}: {exc}"})
    results.sort(key=lambda row: row["case_id"])
    summary = {
        "schema_version": 1,
        "kind": "hebeltrader-sec-packet-batch-result-v1",
        "manifest": str(manifest),
        "out_dir": str(out_dir),
        "built": sum(1 for r in results if r["status"] == "built"),
        "reused": sum(1 for r in results if r["status"] == "reused"),
        "errors": errors,
        "results": results,
    }
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument(
        "--raw-root",
        type=Path,
        default=Path("data/hebeltrader/source-packet-raw"),
    )
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--summary", type=Path)
    args = parser.parse_args(argv)
    summary = run_batch(
        args.manifest, out_dir=args.out_dir, raw_root=args.raw_root, workers=args.workers
    )
    text = json.dumps(summary, indent=2, ensure_ascii=False)
    if args.summary:
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        args.summary.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 1 if summary["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
