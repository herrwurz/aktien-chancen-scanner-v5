from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select

from scanner.hebeltrader.models import Document, HistoricalRecommendation, Publication, ReviewEvent

FEATURE_FIELDS = (
    "stock_name",
    "stock_wkn",
    "stock_isin",
    "derivative_wkn",
    "derivative_isin",
    "product_type",
    "issuer",
    "strike",
    "strike_currency",
    "maturity_date",
    "term_text",
    "entry_price",
    "entry_kind",
    "omega",
    "omega_label",
    "stock_price",
    "derivative_target1",
    "derivative_target2",
    "derivative_stop1",
    "derivative_stop2",
    "stock_target1",
    "stock_target2",
    "stock_stop1",
    "stock_stop2",
    "crv",
    "derivative_currency",
    "stock_currency",
    "quote_as_of_text",
    "fundamental_notes",
    "technical_notes",
)


def review_document(
    session, sha256, action, reviewer, note, *, available_at=None, availability_evidence=None
):
    if action not in ("approve", "reject") or not reviewer.strip() or not note.strip():
        raise ValueError("Review requires action, reviewer and explanation")
    document = session.get(Document, sha256)
    if document is None:
        raise ValueError("Unknown document")
    if action == "approve" and (
        document.publication_id is None or document.publication_date is None
    ):
        raise ValueError("Publication identity/date must be resolved before review")
    issue = session.scalar(
        select(Publication).where(Publication.id == document.publication_id).with_for_update()
    )
    if action == "approve":
        if (available_at is None) != (availability_evidence is None):
            raise ValueError("Availability timestamp and source evidence must be supplied together")
        if available_at is not None:
            if available_at.tzinfo is None or not availability_evidence.strip():
                raise ValueError("Availability requires timezone and explicit evidence")
            earliest = datetime.combine(
                document.publication_date, time.min, ZoneInfo("Europe/Berlin")
            )
            if available_at < earliest:
                raise ValueError("Source availability precedes publication day")
            document.verified_available_at = available_at.astimezone(UTC)
            document.availability_evidence = availability_evidence
        if document.revision_conflict and document.verified_available_at is None:
            raise ValueError(
                "Conflicting revisions require source-specific historical availability evidence"
            )
        if document.extraction_status != "extracted":
            raise ValueError("Extraction failed")
        recs = session.scalars(
            select(HistoricalRecommendation).where(HistoricalRecommendation.document_sha == sha256)
        ).all()
        if not recs or any(not r.stock_name or not r.evidence for r in recs):
            raise ValueError("No supported recommendations to approve")
        for other in session.scalars(select(Document).where(Document.publication_id == issue.id)):
            if other.sha256 != sha256:
                other.review_status = "superseded"
        issue.selected_sha = sha256
        document.review_status = "approved"
    else:
        document.review_status = "rejected"
        if issue is not None and issue.selected_sha == sha256:
            issue.selected_sha = None
    session.add(
        ReviewEvent(
            document_sha=sha256,
            action=action,
            reviewer=reviewer,
            note=note,
            reviewed_at=datetime.now(UTC),
            verified_available_at=document.verified_available_at,
            availability_evidence=document.availability_evidence,
        )
    )
    session.flush()


def export_features(session, as_of):
    if as_of.tzinfo is None:
        raise ValueError("as_of must have timezone")
    query = (
        select(HistoricalRecommendation, Document, Publication)
        .join(Document, HistoricalRecommendation.document_sha == Document.sha256)
        .join(Publication, Document.publication_id == Publication.id)
        .where(Document.review_status == "approved", Publication.selected_sha == Document.sha256)
    )
    rows = []
    for rec, document, issue in session.execute(
        query.order_by(
            Publication.issue_year, Publication.issue_number, HistoricalRecommendation.ordinal
        )
    ):
        if document.publication_date is None:
            continue
        if document.revision_conflict and document.verified_available_at is None:
            continue
        available = document.verified_available_at or datetime.combine(
            document.publication_date + timedelta(days=1), time.min, ZoneInfo("Europe/Berlin")
        ).astimezone(UTC)
        if available > as_of:
            continue
        fields = {}
        for name in FEATURE_FIELDS:
            value = getattr(rec, name)
            fields[name] = str(value) if value is not None else None
        rows.append(
            dict(
                source_sha256=document.sha256,
                recommendation_ordinal=rec.ordinal,
                publication_date=document.publication_date.isoformat(),
                issue=f"{issue.issue_number}/{issue.issue_year}",
                available_at=available.isoformat(),
                availability_assumption=(
                    "reviewed_source_availability"
                    if document.verified_available_at
                    else "end_of_publication_day_Europe_Berlin"
                ),
                availability_evidence=document.availability_evidence,
                features=fields,
            )
        )
    return rows
