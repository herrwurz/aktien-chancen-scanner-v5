import hashlib
from datetime import UTC, datetime

import pytest
from reportlab.pdfgen import canvas
from sqlalchemy import select
from test_import import FIXTURES, copy_pdf, count

from scanner.hebeltrader.analysis import export_features, review_document
from scanner.hebeltrader.domain import RecommendationData
from scanner.hebeltrader.importer import import_folder
from scanner.hebeltrader.models import Document, Publication
from scanner.hebeltrader.parser import parse_fields


@pytest.mark.parametrize("premium", ["1,25 EUR", "1,25"])
def test_strike_currency_does_not_label_premium(premium):
    rec = RecommendationData()
    lines = [
        dict(text=text, page=1, bbox=[0, 0, 100, 20])
        for text in [f"Akt. Kurs {premium}", "Basispreis 100,00 USD"]
    ]
    parse_fields(rec, lines)
    assert rec.values["strike_currency"] == "USD"
    assert rec.values.get("derivative_currency") == ("EUR" if premium.endswith("EUR") else None)
    assert not rec.flags


def test_revision_requires_source_availability(sessions, tmp_path):
    copy_pdf(tmp_path)
    copy_pdf(tmp_path, "table.pdf", "revision.pdf")
    import_folder(sessions, tmp_path)
    with sessions.begin() as s:
        original_sha = hashlib.sha256((FIXTURES / "complete.pdf").read_bytes()).hexdigest()
        revised = s.scalar(select(Document).where(Document.sha256 != original_sha))
        with pytest.raises(ValueError):
            review_document(
                s, revised.sha256, "approve", "tester", "Generic approval is insufficient"
            )
        review_document(
            s,
            revised.sha256,
            "approve",
            "tester",
            "Checked archived source",
            available_at=datetime(2025, 3, 1, tzinfo=UTC),
            availability_evidence="Archived revision snapshot dated 2025-03-01",
        )
        assert export_features(s, datetime(2025, 2, 20, tzinfo=UTC)) == []
        rows = export_features(s, datetime(2025, 3, 2, tzinfo=UTC))
        assert len(rows) == 1
        assert rows[0]["availability_assumption"] == "reviewed_source_availability"


def test_invalid_date_keeps_issue_identity(sessions, tmp_path):
    copy_pdf(tmp_path)
    import_folder(sessions, tmp_path)
    with sessions.begin() as s:
        review_document(s, s.scalar(select(Document)).sha256, "approve", "tester", "Checked")
    pdf = canvas.Canvas(str(tmp_path / "invalid.pdf"), invariant=1)
    pdf.drawString(40, 800, "32.02.2025 # 25/2025")
    pdf.showPage()
    pdf.save()
    import_folder(sessions, tmp_path)
    with sessions() as s:
        assert count(s, Publication) == 1
        assert s.scalar(select(Publication)).selected_sha is None
        assert all(d.publication_id is not None for d in s.scalars(select(Document)))


def test_unclassified_opening_text_is_not_a_fundamental_feature():
    from scanner.hebeltrader.analysis import FEATURE_FIELDS
    from scanner.hebeltrader.parser import extract_pdf

    result = extract_pdf((FIXTURES / "table.pdf").read_bytes())
    rec = result.recommendations[0]
    assert rec.values.get("fundamental_notes") is None
    assert rec.values["source_commentary"]
    assert "source_commentary" not in FEATURE_FIELDS


def test_same_page_stock_and_derivative_are_separate(tmp_path):
    from decimal import Decimal

    from scanner.hebeltrader.parser import extract_pdf

    path = tmp_path / "mixed.pdf"
    pdf = canvas.Canvas(str(path), invariant=1)
    lines = [
        "14.02.2025 # 25/2025",
        "Muster AG",
        "Optionsschein Call",
        "WKN AB1C23",
        "Akt. Kurs 1,25 EUR",
        "Basiswert Muster AG",
        "WKN 123456",
        "Akt. Kurs 100,00 EUR",
        "Kursziel 1 120,00 EUR",
    ]
    for i, line in enumerate(lines):
        pdf.drawString(40, 800 - i * 20, line)
    pdf.showPage()
    pdf.save()
    rec = extract_pdf(path.read_bytes()).recommendations[0]
    assert rec.values["entry_price"] == Decimal("1.25")
    assert rec.values["stock_price"] == 100
    assert rec.values["derivative_wkn"] == "AB1C23"
    assert rec.values["stock_wkn"] == "123456"
