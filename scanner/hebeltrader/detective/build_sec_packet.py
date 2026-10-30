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

# SEC fair-access policy requires a descriptive UA with contact.
UA = (
    "AktienChancenScanner/0.1 "
    "(research; source-packet-builder; contact@aktien-chancen-scanner.local)"
)


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "identity"})
    with urllib.request.urlopen(req, timeout=90) as response:
        return response.read()


_REVENUE_HINT = re.compile(
    r"\b(?:revenue|revenues|sales|million|billion|operational(?:ly)?|grew|increase|decrease)\b|\$",
    re.I,
)

# Domestic + foreign-private-issuer forms used for evidence packets.
_FILING_FORMS = frozenset({"10-Q", "10-K", "8-K", "6-K", "20-F"})

_EARNINGS_NAME_HINT = re.compile(
    # Prefer explicit earnings/results tokens. Avoid generic stems like "group".
    # Filing names vary: q32026…, edgar3q26…, 3q2026…
    r"(?:earnings?|results?|financial|interim|quarter|"
    r"q[1-4]\d{2,4}|[1-4]q\d{2,4}|"
    r"press|financiero|presentation|release)",
    re.I,
)

_EXHIBIT_NAME_HINT = re.compile(
    r"(?:991|99[_-]?1|ex[-_]?99|exhibit|earn|result|press|release|interim)",
    re.I,
)


def _best_needle_span(text: str, needle: str) -> tuple[int, int] | None:
    """Pick the needle hit nearest revenue/sales prose (skip glossary-first traps)."""
    # Prefer prose tokens (Skyrizi), not XBRL tags (SKYRIZIMember).
    pattern = re.compile(rf"(?<![A-Za-z0-9]){re.escape(needle)}(?![A-Za-z0-9])", re.I)
    best = None
    best_score = float("-inf")
    for match in pattern.finditer(text):
        ctx = text[max(0, match.start() - 160) : match.end() + 220]
        score = len(_REVENUE_HINT.findall(ctx))
        # Prefer acquisition/merger narrative over bare XBRL label hits.
        if re.search(
            r"\b(?:acquisition of|acquired|completed|merger)\b",
            ctx,
            re.I,
        ):
            score += 3
        if re.search(r"\b(?:the company|the registrant|\bwe\b|our)\b", ctx, re.I):
            score += 2
        # Strong ownership: "which we acquired" / "KKR completed the … acquisition".
        if re.search(
            r"\bwe\s+acquired\b|\bcompleted\s+the\b.{0,40}\bacquisition\b",
            ctx,
            re.I,
        ):
            score += 6
        # Glossary/definition lines are weak ownership anchors.
        if re.search(r"\b(?:includes?|means?|refers to|formerly|abbreviation)\b", ctx, re.I):
            score -= 2
        if score > best_score:
            best_score = score
            best = match
    if best is None:
        return None
    return (max(0, best.start() - 500), min(len(text), best.end() + 1500))


def _focus_text(raw: bytes, needles: tuple[str, ...] = ()) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", raw.decode("utf-8", "replace")))
    text = re.sub(r"\s+", " ", text).strip()
    windows = [(0, 6000)]
    for needle in needles:
        span = _best_needle_span(text, needle)
        if span:
            windows.append(span)
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


def _filing_url(cik: str, accession: str, primary: str) -> str:
    acc = accession.replace("-", "")
    return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc}/{primary}"


def _earnings_name_score(name: str) -> int:
    text = name or ""
    score = 0
    for match in _EARNINGS_NAME_HINT.finditer(text):
        token = match.group(0).casefold()
        score += 5 if token.startswith("earn") else 3 if "q" in token else 2
    return score


def list_filings(cik: str, *, cutoff_date: str, since: str = "2025-01-01"):
    time.sleep(0.12)
    payload = json.loads(_get(f"https://data.sec.gov/submissions/CIK{cik}.json"))
    recent = payload["filings"]["recent"]
    rows = []
    for index, form in enumerate(recent["form"]):
        if form not in _FILING_FORMS:
            continue
        filed = recent["filingDate"][index]
        # Exclude same calendar day as the teaser: EDGAR timestamps are often
        # afternoon UTC while teasers publish in the morning local time.
        if filed >= cutoff_date or filed < since:
            continue
        accession = recent["accessionNumber"][index]
        primary = recent["primaryDocument"][index]
        rows.append(
            {
                "form": form,
                "filed": filed,
                "accession": accession,
                "primary": primary,
                "cik": cik,
                "url": _filing_url(cik, accession, primary),
                "name": payload.get("name"),
            }
        )

    def _rank(row):
        form_rank = {
            "10-Q": 0,
            "10-K": 1,
            "20-F": 2,
            "6-K": 3,
            "8-K": 4,
        }.get(row["form"], 9)
        return (form_rank, row["filed"], _earnings_name_score(row["primary"]))

    rows.sort(key=_rank, reverse=True)
    return rows, payload.get("name")


def _best_six_k(rows):
    six_ks = [row for row in rows if row["form"] == "6-K"]
    if not six_ks:
        return None
    six_ks.sort(
        key=lambda row: (
            _earnings_name_score(row["primary"]),
            row["filed"],
        ),
        reverse=True,
    )
    return six_ks[0]


def pick_filings(rows, *, extra_8k: bool = False):
    """Prefer quarterly evidence: 10-Q, else recent 6-K (FPI), else 10-K/20-F.

    Foreign private issuers rarely file 10-Q; their quarterly earnings arrive as
    Form 6-K. Prefer that over a stale annual 20-F when both exist.
    """
    chosen = []
    ten_q = next((row for row in rows if row["form"] == "10-Q"), None)
    if ten_q:
        chosen.append(ten_q)
    else:
        six_k = _best_six_k(rows)
        if six_k:
            chosen.append(six_k)
        else:
            ten_k = next((row for row in rows if row["form"] == "10-K"), None)
            if ten_k:
                chosen.append(ten_k)
            else:
                twenty_f = next((row for row in rows if row["form"] == "20-F"), None)
                if twenty_f:
                    chosen.append(twenty_f)
    if extra_8k:
        for row in rows:
            if row["form"] == "8-K" and row not in chosen:
                chosen.append(row)
                break
    return chosen


def resolve_filing_body(filing: dict) -> dict:
    """For 6-K cover pages, prefer a substantive exhibit (e.g. EX-99.1 earnings).

    SEC foreign-private-issuer 6-K primaries are often short wrappers; the
    earnings release lives in a sibling ``.htm`` under the same accession.
    Binding stays on the accession filing date / immutable EDGAR URL.
    """
    if filing.get("form") != "6-K":
        return filing
    cik = str(filing.get("cik") or "")
    accession = filing.get("accession") or ""
    if not cik or not accession:
        return filing
    acc = accession.replace("-", "")
    time.sleep(0.12)
    try:
        payload = json.loads(
            _get(f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc}/index.json")
        )
    except Exception:
        return filing
    items = (payload.get("directory") or {}).get("item") or []
    candidates = []
    primary = (filing.get("primary") or "").casefold()
    for item in items:
        name = str(item.get("name") or "")
        if not name.casefold().endswith((".htm", ".html")):
            continue
        if name.casefold() == primary:
            continue
        if "index" in name.casefold():
            continue
        try:
            size = int(item.get("size") or 0)
        except (TypeError, ValueError):
            size = 0
        score = _earnings_name_score(name) + (10 if _EXHIBIT_NAME_HINT.search(name) else 0)
        candidates.append((score, size, name))
    if not candidates:
        return filing
    candidates.sort(reverse=True)
    best_name = candidates[0][2]
    # Require a clear exhibit/earnings win or a substantially larger body.
    primary_size = 0
    for item in items:
        if str(item.get("name") or "").casefold() == primary:
            try:
                primary_size = int(item.get("size") or 0)
            except (TypeError, ValueError):
                primary_size = 0
            break
    best_score, best_size, _ = candidates[0]
    if best_score < 5 and best_size < max(80_000, primary_size * 2):
        return filing
    resolved = dict(filing)
    resolved["primary"] = best_name
    resolved["url"] = _filing_url(cik, accession, best_name)
    resolved["resolved_from_primary"] = filing.get("primary")
    return resolved


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
            filing = resolve_filing_body(filing)
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
                    "primary": filing.get("primary"),
                    "resolved_from_primary": filing.get("resolved_from_primary"),
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
