import base64
from io import BytesIO

import pytest
from reportlab.pdfgen import canvas

from scanner.hebeltrader.detective.cli import main
from scanner.hebeltrader.detective.clues import extract_atomic_clues
from scanner.hebeltrader.detective.documents import MAX_PDF_BYTES, extract_document
from scanner.hebeltrader.detective.schemas import DetectiveRequest, SourceSpan


def pdf_bytes(*pages):
    buffer = BytesIO()
    document = canvas.Canvas(buffer)
    for text in pages:
        if text:
            document.drawString(72, 720, text)
        document.showPage()
    document.save()
    return buffer.getvalue()


class StubOcr:
    engine = "stub_ocr"

    def __init__(self, text="OCR Ersatztext"):
        self.text = text
        self.calls = 0

    def extract(self, payload, media_type):
        assert payload
        assert media_type == "image/png"
        self.calls += 1
        return self.text


def test_pdf_uses_text_layer_then_ocr_for_empty_page_with_page_provenance():
    ocr = StubOcr()
    result = extract_document(pdf_bytes("Primärtext", ""), "application/pdf", ocr=ocr)

    assert result.complete is True
    assert result.page_count == 2
    assert [page.method for page in result.pages] == ["pdf_text", "ocr"]
    assert result.pages[0].text == "Primärtext"
    assert result.pages[1].text == "OCR Ersatztext"
    assert result.pages[1].requires_manual_review is True
    assert ocr.calls == 1


def test_pdf_partial_ocr_failure_is_visible_per_page():
    class FailingOcr(StubOcr):
        def extract(self, payload, media_type):
            raise ValueError("local OCR unavailable")

    result = extract_document(pdf_bytes("Text", ""), "application/pdf", ocr=FailingOcr())

    assert result.complete is False
    assert result.pages[1].status == "failed"
    assert result.pages[1].warnings == ["local OCR unavailable"]


def test_pdf_limits_and_invalid_payload_fail_closed():
    with pytest.raises(ValueError, match="20 MiB"):
        extract_document(b"%PDF" + b"0" * MAX_PDF_BYTES, "application/pdf", ocr=StubOcr())
    with pytest.raises(ValueError, match="could not be read"):
        extract_document(b"not a pdf", "application/pdf", ocr=StubOcr())
    with pytest.raises(ValueError, match="40 page"):
        extract_document(pdf_bytes(*([""] * 41)), "application/pdf", ocr=StubOcr())


def test_atomic_clues_keep_quotes_scope_and_exclude_promotional_returns():
    text = (
        "Der US-Pharmakonzern hob die Prognose an. Der Umsatz stieg um 18 % im Q2 2025. "
        "Mit diesem Call sind 1.091 % Gewinnchance möglich. Call WKN HS5RMP."
    )
    clues = extract_atomic_clues(
        text,
        [SourceSpan(source_id="input", page=3, start=0, end=len(text))],
    )

    promotional = [clue for clue in clues if clue.category == "promotional_derivative_return"]
    assert [clue.value for clue in promotional] == ["1091"]
    assert promotional[0].instrument_scope == "promotional"
    assert promotional[0].page == 3
    assert "1.091 %" in promotional[0].quote
    assert any(clue.category == "financial_metric" and clue.value == "18" for clue in clues)
    assert not any(clue.category == "financial_metric" and clue.value == "1091" for clue in clues)
    assert any(
        clue.category == "identifier"
        and clue.instrument_scope == "derivative"
        and clue.value == "HS5RMP"
        for clue in clues
    )
    assert len({clue.clue_id for clue in clues}) == len(clues)


def test_promotional_cue_before_percentage_and_negated_stock_clue_stay_separate():
    text = "Kein US-Konzern. Die Rendite mit diesem Call könnte 2.631 % betragen."
    clues = extract_atomic_clues(
        text, [SourceSpan(source_id="input", page=1, start=0, end=len(text))]
    )

    assert any(
        item.category == "promotional_derivative_return" and item.value == "2631" for item in clues
    )
    assert any(
        item.category == "countries" and item.value == "US" and item.polarity == "negated"
        for item in clues
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Einmalige Chance mit 1.717 Prozent Rendite.", "1717"),
        ("Gewinnchance von 1.717 Prozent", "1717"),
        ("1.717 % Potenzial!", "1717"),
        ("2.631 Prozent mit diesem Call", "2631"),
        (
            "Mit dem empfohlenen Hebelprodukt winkt eine Renditechance von bis zu 1.900 Prozent.",
            "1900",
        ),
    ],
)
def test_promotional_returns_accept_prozent_and_potenzial_chance_cues(text, expected):
    clues = extract_atomic_clues(text, [SourceSpan(source_id="input", start=0, end=len(text))])
    promotional = [item for item in clues if item.category == "promotional_derivative_return"]
    assert [item.value for item in promotional] == [expected]
    assert not any(item.category == "financial_metric" for item in clues)


def test_turnaround_teaser_keeps_buyback_and_excludes_promotional_1900():
    text = (
        "Ein internationaler Branchenriese sendet mit milliardenschweren Aktienrückkäufen "
        "ein Signal. Steigende Gewinne und eine Renditechance von bis zu 1.900 Prozent."
    )
    clues = extract_atomic_clues(text, [SourceSpan(source_id="input", start=0, end=len(text))])
    assert any(item.category == "events" and item.value == "share_buyback" for item in clues)
    assert any(
        item.category == "fact_claims" and item.value == "net_income_increase" for item in clues
    )
    assert any(
        item.category == "promotional_derivative_return" and item.value == "1900" for item in clues
    )
    assert not any(item.category == "financial_metric" for item in clues)


def test_financial_metric_accepts_prozent_word_without_becoming_promotional():
    text = "Der Umsatz stieg im Q2 2025 um 18 Prozent."
    clues = extract_atomic_clues(text, [SourceSpan(source_id="input", start=0, end=len(text))])
    metric = next(item for item in clues if item.category == "financial_metric")
    assert metric.value == "18"
    assert metric.unit == "%"
    assert metric.period == "Q2 2025"
    assert not any(item.category == "promotional_derivative_return" for item in clues)


def test_request_accepts_bounded_pdf_and_declares_schema_v3():
    payload = base64.b64encode(pdf_bytes("Teaser")).decode()
    request = DetectiveRequest(pdf_base64=payload, pdf_media_type="application/pdf")

    assert request.schema_version == 3
    assert request.pdf_base64 == payload


def test_cli_accepts_pdf_through_same_request_contract(tmp_path, monkeypatch):
    source = tmp_path / "teaser.pdf"
    source.write_bytes(pdf_bytes("Teaser"))
    output = tmp_path / "result.json"
    captured = {}

    class Service:
        def analyze(self, request):
            captured["request"] = request
            return {"status": "candidate_identification_only", "candidates": []}

    monkeypatch.setattr(
        "scanner.hebeltrader.detective.cli.build_detective", lambda settings: Service()
    )
    assert main(["--pdf", str(source), "--output", str(output)]) == 0
    assert captured["request"].schema_version == 3
    assert base64.b64decode(captured["request"].pdf_base64) == source.read_bytes()
    assert captured["request"].pdf_media_type == "application/pdf"
