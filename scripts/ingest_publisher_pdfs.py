#!/usr/bin/env python3
"""Ingest operator-uploaded HEBELTRADER publisher PDFs into a private local archive.

PDFs and full-text extracts stay under gitignored ``data/hebeltrader/``.
Only a metadata inventory is written for commit (no PDF bytes, no full body text).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path

import pdfplumber

ROOT = Path(__file__).resolve().parents[1]
PDF_DIR = ROOT / "data" / "hebeltrader" / "publisher-pdfs"
EXTRACT_DIR = ROOT / "data" / "hebeltrader" / "publisher-pdf-extracts"
INVENTORY_JSON = ROOT / "docs" / "hebeltrader-publisher-pdf-inventory.json"
INVENTORY_MD = ROOT / "docs" / "hebeltrader-publisher-pdf-inventory.md"
TEASER_CASES = ROOT / "data" / "hebeltrader" / "teaser-cases.json"

ISSUE_RE = re.compile(
    r"(?:#\s*)?(\d{1,3})\s*/\s*(20)?(25|26)\b",
    re.I,
)
DATE_RE = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(20\d{2})\b")
TIME_RE = re.compile(
    r"Stand:\s*(\d{1,2})\.(\d{1,2})\.(20\d{2})\s+um\s+(\d{1,2}):(\d{2})\s*Uhr",
    re.I,
)
WKN_RE = re.compile(r"\bWKN\s+([A-Z0-9]{6})\b")
CALL_WKN_RE = re.compile(
    r"Optionsschein\s+Call.*?WKN\s+([A-Z0-9]{6})",
    re.I | re.S,
)
FILENAME_RE = re.compile(
    r"Hebeltrader_(20\d{2})-(\d{1,3})(?:[_-](.+))?_[0-9a-f]{4}\.pdf$",
    re.I,
)
BLIND_ISSUES = {"202/26": "BLIND-202-26"}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _parse_filename(name: str) -> dict:
    match = FILENAME_RE.match(name)
    if not match:
        return {"year_hint": None, "issue_hint": None, "label_hint": None}
    label = match.group(3)
    if label:
        label = re.sub(r"_(allOK|allFail|halfOK|fail|all)$", "", label, flags=re.I)
        label = label.replace("_", " ").strip()
    return {
        "year_hint": int(match.group(1)),
        "issue_hint": int(match.group(2)),
        "label_hint": label or None,
    }


def _normalize_issue(num: int, year: int) -> str:
    yy = year % 100
    return f"{num}/{yy:02d}"


def _parse_text(text: str, filename_meta: dict) -> dict:
    issue = None
    year = filename_meta.get("year_hint")
    for match in ISSUE_RE.finditer(text[:4000]):
        num = int(match.group(1))
        yy = int(match.group(3))
        year = 2000 + yy
        issue = _normalize_issue(num, year)
        break
    if issue is None and filename_meta.get("issue_hint") and year:
        issue = _normalize_issue(int(filename_meta["issue_hint"]), int(year))

    publication_date = None
    for match in DATE_RE.finditer(text[:2500]):
        d, m, y = int(match.group(1)), int(match.group(2)), int(match.group(3))
        if 1 <= d <= 31 and 1 <= m <= 12:
            publication_date = f"{y:04d}-{m:02d}-{d:02d}"
            break

    publication_at = None
    time_match = TIME_RE.search(text[:4000])
    if time_match:
        d, m, y = int(time_match.group(1)), int(time_match.group(2)), int(time_match.group(3))
        hh, mm = int(time_match.group(4)), int(time_match.group(5))
        # Publisher times are Europe/Berlin wall clock without offset in the PDF.
        publication_at = f"{y:04d}-{m:02d}-{d:02d}T{hh:02d}:{mm:02d}:00+01:00"

    call_match = CALL_WKN_RE.search(text[:5000])
    if call_match:
        wkns = [call_match.group(1)]
    else:
        wkns = list(dict.fromkeys(WKN_RE.findall(text)))[:1]
    headline = None
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("www.") or "HEBELTRADER" in line.upper():
            continue
        if re.fullmatch(r"\d{1,2}\.\d{1,2}\.\d{4}.*", line):
            continue
        if len(line) >= 12:
            headline = line[:200]
            break

    return {
        "issue": issue,
        "year": year,
        "publication_date": publication_date,
        "publication_at_guess": publication_at,
        "call_wkns": wkns,
        "headline_guess": headline,
        "label_hint": filename_meta.get("label_hint"),
    }


def _load_case_index():
    if not TEASER_CASES.is_file():
        return {}
    cases = json.loads(TEASER_CASES.read_text(encoding="utf-8"))["cases"]
    by_issue = {}
    for case in cases:
        issue = case.get("publication_issue")
        if issue:
            by_issue[str(issue)] = case
    return by_issue


def _reference_gaps(public_rows: list[dict]) -> dict[str, str]:
    """Remaining active-register PDF gaps after this ingest."""
    by_case = {
        row["mapped_case_id"]: row
        for row in public_rows
        if row.get("mapped_case_id") and row.get("in_reference_27")
    }
    gaps: dict[str, str] = {}
    costco = by_case.get("HT-003")
    if not costco or costco.get("issue") != "192/26":
        gaps["HT-003"] = "Costco 192/26 not in upload set (have Costco 70/26 instead)"
    elif not costco.get("publication_at_guess"):
        gaps["HT-003"] = "Costco 192/26 present but Stand Uhr missing"
    basf = by_case.get("HT-012")
    if not basf or basf.get("issue") != "137/26":
        gaps["HT-012"] = "BASF 137/26 not in upload set"
    elif not basf.get("publication_at_guess"):
        gaps["HT-012"] = "BASF 137/26 present but Stand Uhr missing"
    return gaps


def ingest_one(path: Path, case_by_issue: dict) -> tuple[dict, dict]:
    data = path.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    filename_meta = _parse_filename(path.name)
    pages_text = []
    with pdfplumber.open(path) as pdf:
        page_count = len(pdf.pages)
        for page in pdf.pages[: min(page_count, 40)]:
            pages_text.append(page.extract_text() or "")
    text = "\n".join(pages_text).strip()
    parsed = _parse_text(text, filename_meta)
    issue = parsed.get("issue")
    matched = case_by_issue.get(issue) if issue else None
    mapped_case_id = matched.get("case_id") if matched else BLIND_ISSUES.get(issue or "")
    mapped_company = (matched or {}).get("actual_company")
    if mapped_case_id == "BLIND-202-26":
        mapped_company = mapped_company or "Deutsche Bank"

    public = {
        "filename": path.name,
        "sha256": sha,
        "bytes": len(data),
        "page_count": page_count,
        "issue": issue,
        "year": parsed.get("year"),
        "publication_date": parsed.get("publication_date"),
        "publication_at_guess": parsed.get("publication_at_guess"),
        "call_wkns": parsed.get("call_wkns") or [],
        "label_hint": parsed.get("label_hint"),
        "headline_guess": parsed.get("headline_guess"),
        "text_chars": len(text),
        "has_extractable_text": bool(text),
        "mapped_case_id": mapped_case_id,
        "mapped_company": mapped_company,
        "in_reference_27": bool(matched),
        "is_blind_case": mapped_case_id == "BLIND-202-26",
    }
    private = {
        **public,
        "archive_path": str(path.relative_to(ROOT)),
        "text": text,
        "pages": [
            {"number": i + 1, "text": page_text, "chars": len(page_text)}
            for i, page_text in enumerate(pages_text)
        ],
    }
    return public, private


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf-dir", type=Path, default=PDF_DIR)
    parser.add_argument("--extract-dir", type=Path, default=EXTRACT_DIR)
    parser.add_argument("--inventory-json", type=Path, default=INVENTORY_JSON)
    parser.add_argument("--inventory-md", type=Path, default=INVENTORY_MD)
    args = parser.parse_args(argv)

    pdfs = sorted(args.pdf_dir.glob("Hebeltrader_*.pdf"))
    if not pdfs:
        raise SystemExit(f"no PDFs in {args.pdf_dir}")

    case_by_issue = _load_case_index()
    args.extract_dir.mkdir(parents=True, exist_ok=True)

    public_rows = []
    errors = []
    for path in pdfs:
        try:
            public, private = ingest_one(path, case_by_issue)
            public_rows.append(public)
            out = args.extract_dir / f"{path.stem}.json"
            payload = json.dumps(private, ensure_ascii=False, indent=2) + "\n"
            out.write_text(payload, encoding="utf-8")
            print(f"ok {path.name} issue={public.get('issue')} case={public.get('mapped_case_id')}")
        except Exception as exc:  # noqa: BLE001 - inventory must continue
            errors.append({"filename": path.name, "error": str(exc)})
            print(f"FAIL {path.name}: {exc}")

    inventory = {
        "schema_version": 1,
        "format": "hebeltrader-publisher-pdf-inventory-v1",
        "recorded_at": datetime.now(UTC).isoformat(),
        "archive_dir": "data/hebeltrader/publisher-pdfs/ (gitignored)",
        "extract_dir": "data/hebeltrader/publisher-pdf-extracts/ (gitignored)",
        "policy": [
            "Publisher PDFs are operator-private; never commit PDF bytes or full text.",
            "This inventory records filenames, hashes, issue/date/WKN guesses, and HT mapping.",
            (
                "publication_at_guess uses Europe/Berlin wall clock from "
                "'Stand: … um … Uhr' when present."
            ),
        ],
        "counts": {
            "pdfs": len(public_rows),
            "with_issue": sum(1 for r in public_rows if r.get("issue")),
            "with_publication_at_guess": sum(
                1 for r in public_rows if r.get("publication_at_guess")
            ),
            "with_call_wkn": sum(1 for r in public_rows if r.get("call_wkns")),
            "mapped_to_reference_27": sum(1 for r in public_rows if r.get("in_reference_27")),
            "mapped_blind": sum(1 for r in public_rows if r.get("is_blind_case")),
            "unique_issues": len({r.get("issue") for r in public_rows if r.get("issue")}),
            "errors": len(errors),
        },
        "reference_gaps": _reference_gaps(public_rows),
        "pdfs": public_rows,
        "errors": errors,
    }
    args.inventory_json.parent.mkdir(parents=True, exist_ok=True)
    args.inventory_json.write_text(
        json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    lines = [
        "# HEBELTRADER Publisher-PDF Inventar",
        "",
        f"Stand: {inventory['recorded_at'][:10]} (UTC).",
        "",
        "## Policy",
        "",
        "- PDF-Dateien und Volltexte liegen **nur lokal** unter `data/hebeltrader/publisher-pdfs/`",
        "  und `publisher-pdf-extracts/` (**gitignored**).",
        "- Dieses Dokument enthält Metadaten (Hash, Ausgabe, Datum, WKN-Guess, Mapping).",
        "",
        "## Kennzahlen",
        "",
        "| Kennzahl | Wert |",
        "|---|---:|",
        f"| PDFs | {inventory['counts']['pdfs']} |",
        f"| mit Issue | {inventory['counts']['with_issue']} |",
        f"| mit `publication_at` Guess | {inventory['counts']['with_publication_at_guess']} |",
        f"| mit Call-WKN | {inventory['counts']['with_call_wkn']} |",
        f"| gemappt auf 27er-Refs | {inventory['counts']['mapped_to_reference_27']} |",
        f"| Extraktionsfehler | {inventory['counts']['errors']} |",
        "",
        "## Mapping auf Referenz-27",
        "",
        "| Issue | Case | Company | PDF |",
        "|---|---|---|---|",
    ]
    mapped = [r for r in public_rows if r.get("in_reference_27")]
    mapped.sort(key=lambda r: (r.get("issue") or "", r["filename"]))
    for row in mapped:
        lines.append(
            f"| {row.get('issue')} | {row.get('mapped_case_id')} | "
            f"{row.get('mapped_company') or '—'} | `{row['filename']}` |"
        )
    lines.extend(
        [
            "",
            "## Alle Ausgaben (kurz)",
            "",
            "| Issue | Date | WKN | Label | Ref27 | File |",
            "|---|---|---|---|---|---|",
        ]
    )

    def sort_key(row):
        return (row.get("year") or 0, row.get("issue") or "", row["filename"])

    for row in sorted(public_rows, key=sort_key):
        wkn = ",".join(row.get("call_wkns") or []) or "—"
        lines.append(
            f"| {row.get('issue') or '—'} | {row.get('publication_date') or '—'} | {wkn} | "
            f"{row.get('label_hint') or '—'} | "
            f"{'yes' if row.get('in_reference_27') else '—'} | `{row['filename']}` |"
        )
    lines.append("")
    args.inventory_md.write_text("\n".join(lines), encoding="utf-8")
    print(
        json.dumps(
            {
                "pdfs": inventory["counts"]["pdfs"],
                "mapped_to_reference_27": inventory["counts"]["mapped_to_reference_27"],
                "with_publication_at_guess": inventory["counts"]["with_publication_at_guess"],
                "inventory": str(args.inventory_json),
            },
            indent=2,
        )
    )
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
