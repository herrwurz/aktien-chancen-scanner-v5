"""Deterministic artificial inputs; no real recommendation or market prices."""

import hashlib
import io
from datetime import UTC, date, datetime

from reportlab.pdfgen.canvas import Canvas

from scanner.hebeltrader.models import Document, HistoricalRecommendation

QUOTE = "Sell 50% at target 1; move stop to entry."
AVAILABLE = datetime(2026, 1, 2, 8, tzinfo=UTC)
AS_OF = datetime(2026, 1, 6, 20, tzinfo=UTC)
RUN_AT = datetime(2026, 2, 1, tzinfo=UTC)


def seed_sample(session):
    stream = io.BytesIO()
    canvas = Canvas(stream, invariant=1)
    lines = [
        "SYNTHETIC TEST ONLY",
        "02.01.2026 #1/2026",
        "Stock WKN AB1234",
        "Stock EUR: quote 10; target1 12; target2 15; stop1 8",
        QUOTE,
    ]
    for index, text in enumerate(lines):
        canvas.drawString(40, 800 - index * 25, text)
    canvas.save()
    data = stream.getvalue()
    sha = hashlib.sha256(data).hexdigest()
    doc = Document(
        sha256=sha,
        publication_date=date(2026, 1, 2),
        original_pdf=data,
        byte_size=len(data),
        extractor_version="synthetic-backtest-example",
        imported_at=RUN_AT,
        extraction_status="extracted",
        review_status="pending",
        revision_conflict=False,
        pages=[dict(number=1, text="\n".join(lines))],
        flags=[],
        metadata_evidence=[dict(page=1, raw=lines[1], rule="header-v1")],
        verified_available_at=AVAILABLE,
        availability_evidence="Synthetic archive at 08:00 UTC",
    )
    rec = HistoricalRecommendation(
        document_sha=sha,
        ordinal=1,
        stock_wkn="AB1234",
        stock_currency="EUR",
        stock_price=10,
        stock_target1=12,
        stock_target2=15,
        stock_stop1=8,
        product_type="Turbo Unlimited Long",
        term_text="open end",
        evidence={
            k: [dict(page=1, raw=str(v))]
            for k, v in {
                "stock_price": 10,
                "stock_target1": 12,
                "stock_target2": 15,
                "stock_stop1": 8,
            }.items()
        },
        flags=[],
    )
    session.add_all([doc, rec])
    session.flush()
    return doc, rec


def market_inputs(root):
    (root / "bars.csv").write_text(
        "timestamp,end_timestamp,open,high,low,close,volume\n"
        "2026-01-02T09:30:00+01:00,2026-01-02T17:30:00+01:00,10,11,9,10,100\n"
        "2026-01-05T09:30:00+01:00,2026-01-05T17:30:00+01:00,12,13,11,12,200\n"
        "2026-01-06T09:30:00+01:00,2026-01-06T17:30:00+01:00,9,11,8,10,300\n"
    )
    (root / "calendar.csv").write_text(
        "timestamp,end_timestamp\n"
        "2026-01-02T09:30:00+01:00,2026-01-02T17:30:00+01:00\n"
        "2026-01-05T09:30:00+01:00,2026-01-05T17:30:00+01:00\n"
        "2026-01-06T09:30:00+01:00,2026-01-06T17:30:00+01:00\n"
    )
    (root / "actions.csv").write_text("timestamp,type\n")
    return {
        "AB1234": dict(
            file="bars.csv",
            wkn="AB1234",
            symbol="SYNTHETIC",
            venue="TEST",
            timezone="Europe/Berlin",
            currency="EUR",
            adjustment="raw",
            source_reference="invented example, no vendor",
            license="CC0 synthetic fixture",
            retrieved_at=RUN_AT.isoformat(),
            calendar_file="calendar.csv",
            calendar_reference="synthetic session calendar",
            corporate_actions_file="actions.csv",
            corporate_actions_reference="synthetic, no actions",
            coverage_start="2026-01-01T00:00:00+01:00",
            identity_reference="synthetic identity declaration",
            identity_valid_from="2026-01-01T00:00:00+01:00",
            identity_valid_until=AS_OF.isoformat(),
            coverage_end=AS_OF.isoformat(),
        )
    }


def rule_inputs(doc, rec):
    return {
        f"{doc.sha256}:{rec.ordinal}": dict(
            document_sha=doc.sha256,
            ordinal=rec.ordinal,
            partial_fraction="0.5",
            after_target1="entry",
            reviewer="synthetic fixture",
            reviewed_at=RUN_AT.isoformat(),
            evidence=[dict(page=1, quote=QUOTE, fields=["partial_fraction", "after_target1"])],
        )
    }
