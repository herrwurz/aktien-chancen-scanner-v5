"""Build a dated SEC EDGAR source packet for offline evidence scans.

Fetches filings before a cutoff, writes raw HTML under ``--raw-dir``, and emits
``{case_id}.json`` with ``sec_edgar_filing_date`` availability binding.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

UA = "AktienChancenScanner/0.1 (research; source-packet-builder)"


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "identity"})
    with urllib.request.urlopen(req, timeout=90) as response:
        return response.read()


def _focus_text(raw: bytes, needles: tuple[str, ...] = ()) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", raw.decode("utf-8", "replace")))
    text = re.sub(r"\s+", " ", text).strip()
    windows = [(0, 6000)]
    for needle in needles:
        # Prefer prose tokens (Skyrizi), not XBRL tags (SKYRIZIMember).
        pattern = re.compile(rf"(?<![A-Za-z0-9]){re.escape(needle)}(?![A-Za-z0-9])", re.I)
        match = pattern.search(text)
        if match:
            windows.append((max(0, match.start() - 500), min(len(text), match.end() + 1500)))
    windows.sort()
    merged: list[list[int]] = []
    for start, end in windows:
        if not merged or start > merged[-1][1] + 80:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    focused = "\n\n[...]\n\n".join(text[start:end] for start, end in merged)
    if len(focused) < 8000 and len(text) > len(focused):
        focused = text[:20000]
    return focused[:40000]


def list_filings(cik: str, *, cutoff_date: str, since: str = "2025-01-01"):
    time.sleep(0.12)
    payload = json.loads(_get(f"https://data.sec.gov/submissions/CIK{cik}.json"))
    recent = payload["filings"]["recent"]
    rows = []
    for index, form in enumerate(recent["form"]):
        if form not in {"10-Q", "10-K", "8-K"}:
            continue
        filed = recent["filingDate"][index]
        if filed > cutoff_date or filed < since:
            continue
        accession = recent["accessionNumber"][index]
        acc = accession.replace("-", "")
        primary = recent["primaryDocument"][index]
        rows.append(
            {
                "form": form,
                "filed": filed,
                "accession": accession,
                "primary": primary,
                "url": f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc}/{primary}",
                "name": payload.get("name"),
            }
        )

    def _rank(row):
        form_rank = 0 if row["form"] == "10-Q" else 1 if row["form"] == "10-K" else 2
        return (form_rank, row["filed"])

    rows.sort(key=_rank, reverse=True)
    return rows, payload.get("name")


def pick_filings(rows, *, extra_8k: bool = False):
    chosen = []
    ten_q = next((row for row in rows if row["form"] == "10-Q"), None)
    if ten_q:
        chosen.append(ten_q)
    else:
        ten_k = next((row for row in rows if row["form"] == "10-K"), None)
        if ten_k:
            chosen.append(ten_k)
    if extra_8k:
        for row in rows:
            if row["form"] == "8-K" and row not in chosen:
                chosen.append(row)
                break
    return chosen


def build_document(
    *,
    company_name: str,
    ticker: str,
    filing: dict,
    raw: bytes,
    needles: tuple[str, ...],
    observed_at: str,
):
    sha = hashlib.sha256(raw).hexdigest()
    published = f"{filing['filed']}T16:00:00+00:00"
    return {
        "company_name": company_name,
        "ticker": ticker,
        "url": filing["url"],
        "title": f"{company_name} SEC {filing['form']} {filing['filed']}",
        "text": _focus_text(raw, needles),
        "source_kind": "regulator",
        "published_at": published,
        "retrieved_at": observed_at,
        "source_available_at": published,
        "raw_sha256": sha,
        "availability_evidence": {
            "basis": "sec_edgar_filing_date",
            "source_url": filing["url"],
            "observed_at": observed_at,
            "content_sha256": sha,
        },
    }


def build_packet(
    issuers: list[dict],
    *,
    cutoff: datetime,
    raw_dir: Path,
    needles_by_ticker: dict[str, tuple[str, ...]] | None = None,
):
    """``issuers`` items: ``{ticker, cik, name, extra_8k?}``."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    cutoff_date = cutoff.date().isoformat()
    observed = datetime.now(UTC).isoformat()
    needles_by_ticker = needles_by_ticker or {}
    docs = []
    meta = []
    for issuer in issuers:
        ticker = issuer["ticker"]
        cik = issuer["cik"]
        rows, sec_name = list_filings(cik, cutoff_date=cutoff_date)
        name = issuer.get("name") or sec_name or ticker
        picks = pick_filings(rows, extra_8k=bool(issuer.get("extra_8k")))
        for filing in picks:
            time.sleep(0.2)
            raw = _get(filing["url"])
            sha = hashlib.sha256(raw).hexdigest()
            path = raw_dir / f"{ticker}-{filing['filed']}-{sha[:8]}.htm"
            path.write_bytes(raw)
            doc = build_document(
                company_name=name,
                ticker=ticker,
                filing=filing,
                raw=raw,
                needles=needles_by_ticker.get(ticker, ()),
                observed_at=observed,
            )
            docs.append(doc)
            meta.append(
                {
                    "ticker": ticker,
                    "name": name,
                    "form": filing["form"],
                    "filing_date": filing["filed"],
                    "url": filing["url"],
                    "chars": len(doc["text"]),
                    "raw_path": str(path),
                }
            )
    return docs, meta


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-id", required=True)
    parser.add_argument(
        "--cutoff",
        required=True,
        help="ISO-8601 publication cutoff with offset, e.g. 2026-06-08T08:15:00+01:00",
    )
    parser.add_argument(
        "--issuer",
        action="append",
        required=True,
        help="ticker:cik:Company Name[:extra8k] — repeatable; first is the lead",
    )
    parser.add_argument("--out", type=Path, required=True, help="Output {case_id}.json path or dir")
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument(
        "--needle",
        action="append",
        default=[],
        help="Optional focus needle for the lead ticker (repeatable)",
    )
    args = parser.parse_args(argv)
    cutoff = datetime.fromisoformat(args.cutoff)
    if cutoff.utcoffset() is None:
        raise SystemExit("cutoff must include timezone offset")
    issuers = []
    for raw in args.issuer:
        parts = raw.split(":")
        if len(parts) < 3:
            raise SystemExit(f"bad --issuer {raw!r}; expected ticker:cik:name")
        ticker, cik, name, *rest = parts
        issuers.append(
            {
                "ticker": ticker,
                "cik": cik.zfill(10),
                "name": name,
                "extra_8k": bool(rest and rest[0] in {"1", "true", "extra8k"}),
            }
        )
    needles = {issuers[0]["ticker"]: tuple(args.needle)} if args.needle else {}
    docs, meta = build_packet(
        issuers, cutoff=cutoff, raw_dir=args.raw_dir, needles_by_ticker=needles
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
