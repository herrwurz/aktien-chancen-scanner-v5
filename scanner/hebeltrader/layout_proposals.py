"""Geometry-bound stock-table suggestions, independent of the import parser.

Exact stock headings and literal, source-proven aliases are mandatory. Values
remain pending proposals; original values, flags and parser behavior are untouched.
"""

import hashlib
import re

from scanner.hebeltrader.parser import parse_number

FIELDS = {
    "Akt. Kurs": "stock_price",
    "Kursziel 1": "stock_target1",
    "Kursziel 2": "stock_target2",
    "Stopp 1": "stock_stop1",
    "Stopp 2": "stock_stop2",
}


def _name(value):
    return " ".join(value.casefold().split())


def _proof(line):
    return dict(page=line["page"], bbox=line["bbox"], quote=line["text"])


def suggest_stock_repairs(doc, rec):
    result = dict(status="unresolved", proposals=[], review_hints=[], requires_manual_review=True)
    if hashlib.sha256(doc.original_pdf).hexdigest() != doc.sha256 or rec.document_sha != doc.sha256:
        result["review_hints"].append("original_sha_mismatch")
        return result
    if not rec.stock_name:
        result["review_hints"].append("stock_name_unavailable")
        return result
    tables = []
    for page in doc.pages:
        for region in page.get("regions", []):
            bases = [r for r in region if r["text"].startswith("Basiswert ")]
            if len(bases) != 1:
                continue
            base = bases[0]
            name = base["text"].removeprefix("Basiswert ").strip()
            headings = [
                r
                for r in region
                if r["bbox"][3] < base["bbox"][1]
                and re.fullmatch(re.escape(name) + r"[ -]Aktie", r["text"], re.I)
            ]
            if len(headings) != 1:
                continue
            linkage = [headings[0], base]
            if _name(name) != _name(rec.stock_name or ""):
                # No fuzzy names, substring matching or hardcoded company aliases.
                alias = re.compile(
                    re.escape(rec.stock_name or "") + r"\s*\(kurz:\s*" + re.escape(name) + r"\)",
                    re.I,
                )
                proofs = [
                    row
                    for p in doc.pages
                    for lines in p.get("regions", [])
                    for row in lines
                    if alias.search(row["text"])
                ]
                if len(proofs) != 1:
                    result["review_hints"].append("stock_name_link_unverified")
                    continue
                linkage.extend(proofs)
            left = base["bbox"][0]
            rows = [
                r
                for r in region
                if abs(r["bbox"][0] - left) <= 8
                and base["bbox"][3] < r["bbox"][1] < base["bbox"][1] + 150
            ]
            values = {}
            for row in rows:
                text = row["text"]
                if text == "WKN":
                    neighbors = [
                        r
                        for r in region
                        if re.fullmatch(r"[A-HJ-NP-Z0-9]{6}", r["text"])
                        and r["bbox"][0] > row["bbox"][2]
                        and abs(r["bbox"][1] - row["bbox"][1]) <= 5
                        and min(r["bbox"][3], row["bbox"][3]) > max(r["bbox"][1], row["bbox"][1])
                    ]
                    if len(neighbors) == 1:
                        values.setdefault("stock_wkn", []).append(
                            (neighbors[0]["text"], [row, neighbors[0]])
                        )
                elif re.fullmatch(r"WKN [A-HJ-NP-Z0-9]{6}", text):
                    values.setdefault("stock_wkn", []).append((text.split()[1], [row]))
                for label, field in FIELDS.items():
                    match = re.fullmatch(
                        re.escape(label) + r"\s+(\d[\d.,]*)\s+(€|\$|EUR|USD|GBP)", text
                    )
                    if match:
                        value = str(parse_number(match[1]))
                        values.setdefault(field, []).append((value, [row]))
                        if field == "stock_price":
                            currency = {"€": "EUR", "$": "USD"}.get(match[2], match[2])
                            values.setdefault("stock_currency", []).append((currency, [row]))
            if any(len(items) != 1 for items in values.values()):
                result["review_hints"].append("ambiguous_stock_table_rows")
                return result
            if not {"stock_wkn", "stock_price", "stock_target1", "stock_stop1"} <= values.keys():
                result["review_hints"].append("incomplete_stock_table")
                continue
            tables.append((values, linkage))
    if len(tables) != 1:
        result["review_hints"].append("stock_table_not_unique")
        return result
    values, linkage = tables[0]
    for field, items in values.items():
        if getattr(rec, field, None) is not None:
            continue
        value, rows = items[0]
        result["proposals"].append(
            dict(
                field=field,
                value=value,
                current_value=None,
                document_sha=doc.sha256,
                ordinal=rec.ordinal,
                evidence=[_proof(r) for r in rows],
                stock_scope_evidence=[_proof(r) for r in linkage],
                method="stock-table-geometry-v14",
                confidence="high_source_support_not_approval",
                review_status="pending",
                requires_manual_review=True,
            )
        )
    result["status"] = "supported_proposal" if result["proposals"] else "no_missing_values"
    return result
