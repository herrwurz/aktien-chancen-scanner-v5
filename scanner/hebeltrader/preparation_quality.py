"""Source-bound, grouped manual quality checks. No corrections or DB writes."""

from collections import defaultdict

FIELDS = ("stock_identity", "stock_currency", "stock_stop1", "stock_target1", "stock_target2")


def _hints(doc, rec, fields):
    hints = []
    for field in fields:
        for item in (rec.evidence or {}).get(field, []):
            if isinstance(item, dict):
                hints.append(
                    dict(
                        page=item.get("page"),
                        bbox=item.get("bbox"),
                        quote=item.get("text") or item.get("raw"),
                        source="field_evidence",
                    )
                )
    if hints:
        return hints
    pages = sorted(
        {
            item.get("page")
            for field, items in (rec.evidence or {}).items()
            if field.startswith("stock_") and isinstance(items, list)
            for item in items
            if isinstance(item, dict) and isinstance(item.get("page"), int)
        }
    )
    if pages:
        return [dict(page=p, quote=None, source="stock_section_context") for p in pages]
    return [
        dict(page=p.get("number"), quote=None, source="document_context_only") for p in doc.pages
    ] or [dict(page=None, quote=None, source="page_unavailable")]


def assess_quality(doc, rec):
    findings = []
    for index, field in enumerate(FIELDS):
        fields = ("stock_wkn", "stock_isin") if field == "stock_identity" else (field,)
        value = (
            {k: getattr(rec, k) for k in fields}
            if field == "stock_identity"
            else getattr(rec, field)
        )
        missing = not any(value.values()) if isinstance(value, dict) else value is None
        if field == "stock_currency" and not rec.evidence.get("stock_currency"):
            missing = True
        invalid = any(
            f.get("field") in fields and f.get("code") in {"invalid_value", "conflicting_values"}
            for f in rec.flags
        )
        statuses = (["missing"] if missing else []) + (["unverified"] if invalid else [])
        if not statuses:
            continue
        findings.append(
            dict(
                document_sha=doc.sha256,
                ordinal=rec.ordinal,
                recommendation_key=f"{doc.sha256}:{rec.ordinal}",
                field=field,
                statuses=statuses,
                current_value=value if value is None or isinstance(value, dict) else str(value),
                priority=(index + 1) * 10 - (5 if invalid else 0),
                source_hints=_hints(doc, rec, fields),
                requires_manual_review=True,
                proposed_correction=None,
                review_action=(
                    "Inspect original page; document evidence before any separate manual correction"
                ),
            )
        )
    return findings


def group_quality(findings):
    grouped = defaultdict(list)
    for finding in findings:
        grouped[finding["document_sha"]].append(finding)
    documents = [
        dict(
            document_sha=sha,
            priority=min(f["priority"] for f in items),
            ordinals=sorted({f["ordinal"] for f in items}),
            recommendation_keys=sorted({f["recommendation_key"] for f in items}),
            findings=sorted(items, key=lambda f: (f["priority"], f["ordinal"], f["field"])),
            requires_manual_review=True,
        )
        for sha, items in grouped.items()
    ]
    documents.sort(key=lambda d: (d["priority"], -len(d["findings"]), d["document_sha"]))
    return dict(
        documents=documents,
        affected_documents=len(documents),
        summary={
            field: {
                status: sum(f["field"] == field and status in f["statuses"] for f in findings)
                for status in ("missing", "unverified")
            }
            for field in FIELDS
        },
        counting_note=(
            "Missing and unverified overlap; one invalid missing target may count in both columns"
        ),
    )
