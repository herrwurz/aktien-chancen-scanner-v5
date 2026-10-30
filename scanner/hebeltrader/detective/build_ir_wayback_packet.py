"""Build issuer IR source packets bound via Wayback Machine snapshots.

Only use captures that already exist on web.archive.org before the teaser cutoff.
Binding: ``availability_evidence.basis = archived_snapshot`` with
``observed_at == source_available_at`` (Wayback timestamp).
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import html
import json
import re
import time
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from .build_sec_packet import _focus_text, build_packet

UA = (
    "AktienChancenScanner/0.1 "
    "(research; source-packet-builder; contact@aktien-chancen-scanner.local)"
)


def _get(url: str) -> bytes:
    req = urllib.request.Request(
        url, headers={"User-Agent": UA, "Accept-Encoding": "identity"}
    )
    with urllib.request.urlopen(req, timeout=90) as response:
        data = response.read()
    if data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    return data


def wayback_timestamp_to_iso(ts: str) -> str:
    """``YYYYMMDDhhmmss`` → ISO-8601 UTC."""
    return datetime.strptime(ts, "%Y%m%d%H%M%S").replace(tzinfo=UTC).isoformat()


def list_wayback_captures(url: str, *, cutoff_ymd: str, since_ymd: str = "20260101"):
    query = urllib.parse.urlencode(
        {
            "url": url,
            "matchType": "exact",
            "from": since_ymd,
            "to": cutoff_ymd,
            "output": "json",
            "fl": "timestamp,statuscode,mimetype,original,length",
            "filter": "statuscode:200",
            "limit": "20",
        }
    )
    time.sleep(0.15)
    rows = json.loads(_get(f"https://web.archive.org/cdx/search/cdx?{query}").decode())
    if not rows or len(rows) < 2:
        return []
    out = []
    for row in rows[1:]:
        ts, status, mime, original, *rest = row
        length = int(rest[0]) if rest and str(rest[0]).isdigit() else 0
        out.append(
            {
                "timestamp": ts,
                "status": status,
                "mime": mime,
                "original": original,
                "length": length,
                "wayback_url": f"https://web.archive.org/web/{ts}id_/{original}",
            }
        )
    out.sort(key=lambda r: (r["length"], r["timestamp"]), reverse=True)
    return out


def pick_capture(captures: list[dict], *, needles: tuple[str, ...] = ()):
    if not captures:
        return None
    if not needles:
        return captures[0]
    for cap in captures[:8]:
        try:
            time.sleep(0.2)
            raw = _get(cap["wayback_url"])
        except Exception:
            continue
        lowered = raw.decode("utf-8", "replace").casefold()
        if any(n.casefold() in lowered for n in needles if n):
            cap = dict(cap)
            cap["raw"] = raw
            return cap
    # fall back to largest capture
    try:
        time.sleep(0.2)
        raw = _get(captures[0]["wayback_url"])
        cap = dict(captures[0])
        cap["raw"] = raw
        return cap
    except Exception:
        return None


def build_ir_document(
    *,
    company_name: str,
    ticker: str,
    capture: dict,
    published_at: str,
    needles: tuple[str, ...],
    observed_now: str,
):
    raw = capture["raw"]
    sha = hashlib.sha256(raw).hexdigest()
    available = wayback_timestamp_to_iso(capture["timestamp"])
    return {
        "company_name": company_name,
        "ticker": ticker,
        "url": capture["wayback_url"],
        "title": f"{company_name} IR (Wayback {capture['timestamp']})",
        "text": _focus_text(raw, needles),
        "source_kind": "issuer",
        "published_at": published_at,
        "retrieved_at": observed_now,
        "source_available_at": available,
        "raw_sha256": sha,
        "availability_evidence": {
            "basis": "archived_snapshot",
            "source_url": capture["wayback_url"],
            "observed_at": available,
            "content_sha256": sha,
        },
    }


def build_hybrid_packet(
    *,
    lead: dict,
    peer_issuers: list[dict],
    cutoff: datetime,
    raw_dir: Path,
    needles: tuple[str, ...] = (),
):
    """Lead = Wayback IR; peers = SEC EDGAR via ``build_packet``."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    observed = datetime.now(UTC).isoformat()
    cutoff_ymd = cutoff.strftime("%Y%m%d")
    captures = list_wayback_captures(lead["url"], cutoff_ymd=cutoff_ymd)
    capture = pick_capture(captures, needles=needles)
    if not capture or "raw" not in capture:
        raise RuntimeError(f"no usable Wayback capture for {lead['url']}")
    lead_doc = build_ir_document(
        company_name=lead["name"],
        ticker=lead["ticker"],
        capture=capture,
        published_at=lead["published_at"],
        needles=needles,
        observed_now=observed,
    )
    path = raw_dir / f"{lead['ticker']}-wayback-{capture['timestamp']}-{lead_doc['raw_sha256'][:8]}.bin"
    path.write_bytes(capture["raw"])
    meta = [
        {
            "ticker": lead["ticker"],
            "name": lead["name"],
            "form": "wayback_ir",
            "filing_date": capture["timestamp"][:8],
            "url": capture["wayback_url"],
            "chars": len(lead_doc["text"]),
            "raw_path": str(path),
            "needles_hit": {
                n: html.unescape(lead_doc["text"]).casefold().count(n.casefold())
                for n in needles
            },
        }
    ]
    peer_docs, peer_meta = build_packet(
        peer_issuers,
        cutoff=cutoff,
        raw_dir=raw_dir,
        needles_by_ticker={},
    )
    return [lead_doc, *peer_docs], meta + peer_meta


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--cutoff", required=True)
    parser.add_argument("--lead-ticker", required=True)
    parser.add_argument("--lead-name", required=True)
    parser.add_argument("--lead-url", required=True)
    parser.add_argument("--lead-published-at", required=True)
    parser.add_argument(
        "--issuer",
        action="append",
        default=[],
        help="SEC peer ticker:cik:name[:extra8k]",
    )
    parser.add_argument("--needle", action="append", default=[])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    cutoff = datetime.fromisoformat(args.cutoff)
    if cutoff.utcoffset() is None:
        raise SystemExit("cutoff must include timezone offset")
    peers = []
    for raw in args.issuer:
        parts = raw.split(":")
        if len(parts) < 3:
            raise SystemExit(f"bad --issuer {raw!r}")
        ticker, cik, name, *rest = parts
        peers.append(
            {
                "ticker": ticker,
                "cik": cik.zfill(10),
                "name": name,
                "extra_8k": bool(rest and rest[0] in {"1", "true", "extra8k"}),
            }
        )
    docs, meta = build_hybrid_packet(
        lead={
            "ticker": args.lead_ticker,
            "name": args.lead_name,
            "url": args.lead_url,
            "published_at": args.lead_published_at,
        },
        peer_issuers=peers,
        cutoff=cutoff,
        raw_dir=args.raw_dir,
        needles=tuple(args.needle),
    )
    out = args.out
    if out.is_dir() or str(out).endswith("/"):
        out = Path(out) / f"{args.case_id}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(docs, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {"case_id": args.case_id, "documents": len(docs), "path": str(out), "meta": meta},
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
