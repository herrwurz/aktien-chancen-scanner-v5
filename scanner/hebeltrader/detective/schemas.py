from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class DetectiveRequest(BaseModel):
    schema_version: int = 3
    analysis_mode: Literal["hypothesis", "strict"] = "hypothesis"
    teaser_text: str = Field(default="", max_length=20_000)
    screenshot_base64: str | None = Field(default=None, max_length=3_000_000)
    screenshot_media_type: str | None = None
    pdf_base64: str | None = Field(default=None, max_length=28_000_000)
    pdf_media_type: str | None = None
    publication_at: datetime | None = None
    known_hints: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("publication_at")
    @classmethod
    def normalize_publication_time(cls, value):
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("publication timestamp timezone required")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def require_input(self):
        if not self.teaser_text.strip() and not self.screenshot_base64 and not self.pdf_base64:
            raise ValueError("teaser text or screenshot or PDF required")
        if self.screenshot_base64 and not self.screenshot_media_type:
            raise ValueError("screenshot media type required")
        if self.pdf_base64 and self.pdf_media_type != "application/pdf":
            raise ValueError("PDF media type must be application/pdf")
        return self


class SourceSpan(BaseModel):
    source_id: str
    page: int | None = None
    start: int = Field(ge=0)
    end: int = Field(ge=0)


class AtomicClue(BaseModel):
    clue_id: str
    category: str
    normalized: str
    quote: str
    source_id: str
    page: int | None = None
    start: int
    end: int
    instrument_scope: Literal["stock", "derivative", "ambiguous", "promotional"]
    value: str | None = None
    unit: str | None = None
    period: str | None = None
    reference_date: str | None = None
    polarity: Literal["asserted", "negated", "unknown"] = "asserted"
    extraction_method: str = "deterministic_regex"
    confidence_class: Literal["high", "medium", "low"] = "medium"
    requires_manual_review: bool = True


class ExtractedPage(BaseModel):
    number: int
    text: str
    method: Literal["pdf_text", "ocr", "none"]
    status: Literal["ok", "failed"]
    requires_manual_review: bool = False
    warnings: list[str] = Field(default_factory=list)


class ExtractedDocument(BaseModel):
    sha256: str
    media_type: str
    page_count: int
    complete: bool
    pages: list[ExtractedPage]

    @property
    def text(self):
        return "\n".join(page.text for page in self.pages if page.text)
