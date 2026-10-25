"""Bounded, provenance-preserving teaser document extraction."""

import hashlib
from io import BytesIO

import pdfplumber

from .schemas import ExtractedDocument, ExtractedPage

MAX_PDF_BYTES = 20 * 1024 * 1024
MAX_PDF_PAGES = 40


def _page_png(page):
    buffer = BytesIO()
    page.to_image(resolution=150).original.save(buffer, format="PNG")
    return buffer.getvalue()


def extract_document(data: bytes, media_type: str, *, ocr) -> ExtractedDocument:
    if media_type != "application/pdf":
        raise ValueError("unsupported document media type")
    if not data or len(data) > MAX_PDF_BYTES:
        raise ValueError("PDF exceeds 20 MiB limit")
    try:
        with pdfplumber.open(BytesIO(data)) as pdf:
            if len(pdf.pages) > MAX_PDF_PAGES:
                raise ValueError("PDF exceeds 40 page limit")
            pages = []
            for number, page in enumerate(pdf.pages, 1):
                text = (page.extract_text() or "").strip()
                if text:
                    pages.append(
                        ExtractedPage(number=number, text=text, method="pdf_text", status="ok")
                    )
                    continue
                try:
                    text = ocr.extract(_page_png(page), "image/png").strip()
                    pages.append(
                        ExtractedPage(
                            number=number,
                            text=text,
                            method="ocr",
                            status="ok",
                            requires_manual_review=True,
                        )
                    )
                except ValueError as exc:
                    pages.append(
                        ExtractedPage(
                            number=number,
                            text="",
                            method="none",
                            status="failed",
                            requires_manual_review=True,
                            warnings=[str(exc)],
                        )
                    )
    except ValueError as exc:
        if str(exc).startswith("PDF exceeds"):
            raise
        raise ValueError("PDF could not be read") from exc
    except Exception as exc:
        raise ValueError("PDF could not be read") from exc
    return ExtractedDocument(
        sha256=hashlib.sha256(data).hexdigest(),
        media_type=media_type,
        page_count=len(pages),
        complete=all(page.status == "ok" for page in pages),
        pages=pages,
    )
