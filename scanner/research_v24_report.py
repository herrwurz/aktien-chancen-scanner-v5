"""Build a deterministic V2.4 audit from archived SEC universe and news metadata."""

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path

from scanner.news import NewsBatch
from scanner.research_index.builder import build_index
from scanner.research_index.models import CandidateQuery
from scanner.research_index.repository import ResearchIndex
from scanner.research_providers.sec_edgar import normalize_universe


def build_report(sec_request_path, news_batch_path, index_path, *, query, as_of):
    sec_request_path = Path(sec_request_path)
    manifest = json.loads(sec_request_path.read_text())
    cache_root = sec_request_path.parent.parent
    raw = (cache_root / manifest["raw_file"]).read_bytes()
    if hashlib.sha256(raw).hexdigest() != manifest["raw_sha256"]:
        raise ValueError("SEC universe cache integrity error")
    record = {**manifest, "payload": json.loads(raw)}
    issuers = {}
    for identity in normalize_universe(record):
        if not identity.cik:
            continue
        issuers.setdefault(
            identity.cik,
            identity.model_copy(update={"source_available_at": identity.retrieved_at}),
        )
    batch = NewsBatch.model_validate_json(Path(news_batch_path).read_bytes())
    index_manifest = build_index(
        index_path,
        assets=list(issuers.values()),
        events=[],
        facts=[],
        news=batch.items,
    )
    result = ResearchIndex(index_path).candidates(
        CandidateQuery(text=query, event_types=["issuer_announcement"]),
        as_of=as_of,
        limit=50,
    )
    return {
        "schema_version": 1,
        "run_kind": "real_archived" if batch.provider != "fixture" else "synthetic",
        "as_of": as_of.isoformat(),
        "query": query,
        "real_data": {
            "sec_issuers": len(issuers),
            "news_items": len(batch.items),
            "news_provider": batch.provider,
            "news_retrieved_at": batch.retrieved_at.isoformat(),
            "network_requests_in_replay": 0,
            "cost_eur": batch.cost_eur,
        },
        "integrity": {
            "sec_raw_sha256": manifest["raw_sha256"],
            "index_payload_sha256": index_manifest.payload_sha256,
            "news_content_sha256": sorted({row.content_hash for row in batch.items}),
        },
        "candidate_result": result.model_dump(mode="json"),
        "claims": {
            "investment_signal": False,
            "probability_calibrated": False,
            "article_full_text_archived": False,
        },
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sec-universe-request", required=True, type=Path)
    parser.add_argument("--news-batch", required=True, type=Path)
    parser.add_argument("--index", required=True, type=Path)
    parser.add_argument("--query", required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    report = build_report(
        args.sec_universe_request,
        args.news_batch,
        args.index,
        query=args.query,
        as_of=datetime.fromisoformat(args.as_of.replace("Z", "+00:00")),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
