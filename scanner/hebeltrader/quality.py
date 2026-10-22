"""Read-only candidate replay and field-completeness comparison."""

from collections import Counter
from decimal import Decimal, InvalidOperation

from sqlalchemy import select

from scanner.hebeltrader.analysis import FEATURE_FIELDS
from scanner.hebeltrader.domain import EXTRACTOR_VERSION
from scanner.hebeltrader.models import Document, HistoricalRecommendation
from scanner.hebeltrader.parser import extract_pdf

NUMERIC_FIELDS = {
    "entry_price",
    "stock_price",
    "strike",
    "omega",
    "crv",
    "derivative_target1",
    "derivative_target2",
    "derivative_stop1",
    "derivative_stop2",
    "stock_target1",
    "stock_target2",
    "stock_stop1",
    "stock_stop2",
}
FIELDS = tuple(
    f
    for f in FEATURE_FIELDS
    if f not in ("fundamental_notes", "technical_notes", "quote_as_of_text")
)


def extraction_snapshot(extraction, sha, version=EXTRACTOR_VERSION):
    return dict(
        sha256=sha,
        version=version,
        flags=extraction.flags,
        recommendations=[
            dict(values=r.values, evidence=r.evidence, flags=r.flags)
            for r in extraction.recommendations
        ],
    )


def completeness(documents):
    rows = [r for d in documents for r in d.get("recommendations", [])]
    hints = Counter()
    computed = Counter()
    for document in documents:
        for flag in document.get("flags", []):
            hints["document:" + flag["code"]] += 1
    for row in rows:
        for flag in row.get("flags", []):
            hints[flag["code"] + ":" + flag.get("field", "")] += 1
        for metric in row.get("evidence", {}).get("_calculated_crv", []):
            computed[metric["target"]] += 1
    return dict(
        documents=len(documents),
        recommendations=len(rows),
        errors=sum("error" in d for d in documents),
        fields={
            f: dict(
                present=sum(r["values"].get(f) is not None for r in rows),
                missing=sum(r["values"].get(f) is None for r in rows),
            )
            for f in FIELDS
        },
        computed_crv={f: computed[f] for f in ("derivative_target1", "derivative_target2")},
        review_hints=dict(sorted(hints.items())),
    )


def _same(field, a, b):
    if field in NUMERIC_FIELDS and a is not None and b is not None:
        try:
            return Decimal(str(a)) == Decimal(str(b))
        except InvalidOperation:
            return False
    return str(a) == str(b)


def compare_snapshots(before, after):
    old = {d["sha256"]: d for d in before if d.get("sha256")}
    new = {d["sha256"]: d for d in after if d.get("sha256")}
    changes = []
    retained = 0
    removed = 0
    for sha, doc in old.items():
        candidates = new.get(sha, {}).get("recommendations", [])
        for previous in doc.get("recommendations", []):
            values = previous["values"]
            identity = (
                values.get("derivative_wkn")
                or values.get("derivative_isin")
                or values.get("stock_wkn")
            )
            if not identity:
                removed += 1
                continue
            matches = [
                r
                for r in candidates
                if identity
                in (
                    r["values"].get("derivative_wkn"),
                    r["values"].get("derivative_isin"),
                    r["values"].get("stock_wkn"),
                )
            ]
            if len(matches) != 1:
                changes.append(
                    dict(
                        sha256=sha,
                        instrument=identity,
                        field="recommendation",
                        reason="missing_or_ambiguous_match",
                    )
                )
                continue
            for field in FIELDS:
                if values.get(field) is None or field == "product_type":
                    continue
                candidate = matches[0]["values"].get(field)
                if _same(field, values[field], candidate):
                    retained += 1
                else:
                    changes.append(
                        dict(
                            sha256=sha,
                            instrument=identity,
                            field=field,
                            before=str(values[field]),
                            after=str(candidate) if candidate is not None else None,
                        )
                    )
    return dict(
        parser_version=EXTRACTOR_VERSION,
        mode="read_only_candidate_replay",
        before=completeness(before),
        after=completeness(after),
        retained_source_values=retained,
        source_value_changes=changes,
        baseline_unidentified_rows=removed,
        missing_documents=sorted(set(old) - set(new)),
        added_documents=sorted(set(new) - set(old)),
    )


def preview_database(session):
    before = []
    after = []
    with session.no_autoflush:
        for document in session.scalars(select(Document).order_by(Document.sha256)):
            records = session.scalars(
                select(HistoricalRecommendation)
                .where(HistoricalRecommendation.document_sha == document.sha256)
                .order_by(HistoricalRecommendation.ordinal)
            ).all()
            before.append(
                dict(
                    sha256=document.sha256,
                    version=document.extractor_version,
                    flags=document.flags,
                    recommendations=[
                        dict(
                            values={f: getattr(r, f) for f in FIELDS},
                            flags=r.flags,
                            evidence=r.evidence,
                        )
                        for r in records
                    ],
                )
            )
            try:
                import hashlib

                data = bytes(document.original_pdf)
                if hashlib.sha256(data).hexdigest() != document.sha256:
                    raise ValueError("Source hash mismatch")
                after.append(extraction_snapshot(extract_pdf(data), document.sha256))
            except Exception as exc:
                after.append(dict(sha256=document.sha256, error=type(exc).__name__))
    return compare_snapshots(before, after)
