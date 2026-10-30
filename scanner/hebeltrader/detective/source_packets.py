"""Operator source-packet contract for historical evidence scans.

Packets are lists of document dicts consumed by ``reference_scan --source-packets``.
They are never solutions. Historical use requires an exact ``publication_at`` on the
case input; a calendar ``publication_date`` alone does not unlock packets.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REQUIRED_DOC_FIELDS = (
    "company_name",
    "url",
    "title",
    "text",
    "source_kind",
    "published_at",
    "retrieved_at",
)

OPTIONAL_DOC_FIELDS = (
    "ticker",
    "source_available_at",
    "raw_sha256",
    "availability_evidence",
)

ALLOWED_SOURCE_KINDS = frozenset(
    {"issuer", "regulator", "exchange", "archive", "secondary", "other"}
)


def validate_document(doc, *, index=0):
    """Return a list of human-readable problems for one document dict."""
    problems = []
    if not isinstance(doc, dict):
        return [f"doc[{index}]: must be an object"]
    for field in REQUIRED_DOC_FIELDS:
        if not doc.get(field):
            problems.append(f"doc[{index}]: missing required field '{field}'")
    kind = doc.get("source_kind")
    if kind and kind not in ALLOWED_SOURCE_KINDS:
        problems.append(f"doc[{index}]: source_kind '{kind}' not in {sorted(ALLOWED_SOURCE_KINDS)}")
    evidence = doc.get("availability_evidence")
    if evidence is not None:
        if not isinstance(evidence, dict):
            problems.append(f"doc[{index}]: availability_evidence must be an object")
        else:
            for field in ("basis", "source_url", "observed_at", "content_sha256"):
                if not evidence.get(field):
                    problems.append(f"doc[{index}]: availability_evidence missing '{field}'")
            if doc.get("raw_sha256") and evidence.get("content_sha256"):
                if doc["raw_sha256"] != evidence["content_sha256"]:
                    problems.append(
                        f"doc[{index}]: raw_sha256 must equal availability_evidence.content_sha256"
                    )
    return problems


def validate_packet(docs):
    """Validate a packet (JSON array of documents)."""
    if not isinstance(docs, list):
        return ["packet must be a JSON array of documents"]
    if not docs:
        return ["packet is empty"]
    problems = []
    for index, doc in enumerate(docs):
        problems.extend(validate_document(doc, index=index))
    return problems


def validate_packet_dir(root: Path):
    """Validate ``{case_id}.json`` packets under a directory."""
    root = Path(root)
    if not root.is_dir():
        return [{"path": str(root), "problems": ["not a directory"]}]
    results = []
    for path in sorted(root.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            results.append({"path": str(path), "problems": [f"invalid JSON: {exc}"]})
            continue
        problems = validate_packet(payload)
        doc_count = len(payload) if isinstance(payload, list) else 0
        results.append({"path": str(path), "problems": problems, "documents": doc_count})
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "path",
        type=Path,
        help="Packet file or directory of {case_id}.json packets",
    )
    args = parser.parse_args(argv)
    target = args.path
    if target.is_dir():
        rows = validate_packet_dir(target)
    else:
        payload = json.loads(target.read_text(encoding="utf-8"))
        problems = validate_packet(payload)
        rows = [
            {
                "path": str(target),
                "problems": problems,
                "documents": len(payload) if isinstance(payload, list) else 0,
            }
        ]
    ok = sum(1 for row in rows if not row["problems"])
    print(json.dumps({"checked": len(rows), "ok": ok, "results": rows}, indent=2))
    return 0 if ok == len(rows) and rows else 1


if __name__ == "__main__":
    raise SystemExit(main())
