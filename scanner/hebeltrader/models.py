from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    ForeignKey,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from scanner.models import Base, UTCDateTime


class Publication(Base):
    __tablename__ = "hebel_publications"
    __table_args__ = (UniqueConstraint("issue_year", "issue_number", name="uq_hebel_issue"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    issue_year: Mapped[int]
    issue_number: Mapped[int]
    selected_sha: Mapped[str | None] = mapped_column(String(64))


class Document(Base):
    __tablename__ = "hebel_documents"
    sha256: Mapped[str] = mapped_column(String(64), primary_key=True)
    publication_id: Mapped[int | None] = mapped_column(ForeignKey("hebel_publications.id"))
    publication_date: Mapped[date | None] = mapped_column(Date)
    original_pdf: Mapped[bytes] = mapped_column(LargeBinary)
    byte_size: Mapped[int]
    extractor_version: Mapped[str] = mapped_column(String(64))
    imported_at: Mapped[datetime] = mapped_column(UTCDateTime())
    extraction_status: Mapped[str] = mapped_column(String(20))
    review_status: Mapped[str] = mapped_column(String(20), default="pending")
    revision_conflict: Mapped[bool] = mapped_column(Boolean, default=False)
    pages: Mapped[list] = mapped_column(JSON)
    flags: Mapped[list] = mapped_column(JSON)
    metadata_evidence: Mapped[list] = mapped_column(JSON)
    verified_available_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    availability_evidence: Mapped[str | None] = mapped_column(Text)


class SourceLocation(Base):
    __tablename__ = "hebel_source_locations"
    __table_args__ = (
        UniqueConstraint("document_sha", "root_id", "relative_path", name="uq_hebel_location"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    document_sha: Mapped[str] = mapped_column(
        ForeignKey("hebel_documents.sha256", ondelete="CASCADE")
    )
    root_id: Mapped[str] = mapped_column(String(64))
    relative_path: Mapped[str] = mapped_column(Text)
    categories: Mapped[list] = mapped_column(JSON)


class HistoricalRecommendation(Base):
    __tablename__ = "hebel_recommendations"
    __table_args__ = (UniqueConstraint("document_sha", "ordinal", name="uq_hebel_recommendation"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    document_sha: Mapped[str] = mapped_column(
        ForeignKey("hebel_documents.sha256", ondelete="CASCADE"), index=True
    )
    ordinal: Mapped[int]
    stock_name: Mapped[str | None] = mapped_column(Text)
    stock_wkn: Mapped[str | None] = mapped_column(String(6))
    stock_isin: Mapped[str | None] = mapped_column(String(12))
    derivative_wkn: Mapped[str | None] = mapped_column(String(6))
    derivative_isin: Mapped[str | None] = mapped_column(String(12))
    product_type: Mapped[str | None] = mapped_column(Text)
    issuer: Mapped[str | None] = mapped_column(Text)
    strike: Mapped[Decimal | None] = mapped_column(Numeric(38, 18))
    strike_currency: Mapped[str | None] = mapped_column(String(3))
    maturity_date: Mapped[date | None] = mapped_column(Date)
    term_text: Mapped[str | None] = mapped_column(Text)
    entry_price: Mapped[Decimal | None] = mapped_column(Numeric(38, 18))
    entry_kind: Mapped[str | None] = mapped_column(String(20))
    omega: Mapped[Decimal | None] = mapped_column(Numeric(38, 18))
    omega_label: Mapped[str | None] = mapped_column(Text)
    stock_price: Mapped[Decimal | None] = mapped_column(Numeric(38, 18))
    derivative_target1: Mapped[Decimal | None] = mapped_column(Numeric(38, 18))
    derivative_target2: Mapped[Decimal | None] = mapped_column(Numeric(38, 18))
    derivative_stop1: Mapped[Decimal | None] = mapped_column(Numeric(38, 18))
    derivative_stop2: Mapped[Decimal | None] = mapped_column(Numeric(38, 18))
    stock_target1: Mapped[Decimal | None] = mapped_column(Numeric(38, 18))
    stock_target2: Mapped[Decimal | None] = mapped_column(Numeric(38, 18))
    stock_stop1: Mapped[Decimal | None] = mapped_column(Numeric(38, 18))
    stock_stop2: Mapped[Decimal | None] = mapped_column(Numeric(38, 18))
    crv: Mapped[Decimal | None] = mapped_column(Numeric(38, 18))
    derivative_currency: Mapped[str | None] = mapped_column(String(3))
    stock_currency: Mapped[str | None] = mapped_column(String(3))
    quote_as_of_text: Mapped[str | None] = mapped_column(Text)
    fundamental_notes: Mapped[str | None] = mapped_column(Text)
    source_commentary: Mapped[str | None] = mapped_column(Text)
    technical_notes: Mapped[str | None] = mapped_column(Text)
    evidence: Mapped[dict] = mapped_column(JSON)
    flags: Mapped[list] = mapped_column(JSON)


class ImportRun(Base):
    __tablename__ = "hebel_import_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime())
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    summary: Mapped[dict] = mapped_column(JSON)


class ReviewEvent(Base):
    __tablename__ = "hebel_reviews"
    id: Mapped[int] = mapped_column(primary_key=True)
    document_sha: Mapped[str] = mapped_column(
        ForeignKey("hebel_documents.sha256", ondelete="CASCADE")
    )
    action: Mapped[str] = mapped_column(String(20))
    reviewer: Mapped[str] = mapped_column(Text)
    note: Mapped[str] = mapped_column(Text)
    reviewed_at: Mapped[datetime] = mapped_column(UTCDateTime())
    verified_available_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    availability_evidence: Mapped[str | None] = mapped_column(Text)


class HistoricalOutcome(Base):
    """Reserved for independently sourced observations; never populated from folder names."""

    __tablename__ = "hebel_outcomes"
    id: Mapped[int] = mapped_column(primary_key=True)
    recommendation_id: Mapped[int] = mapped_column(
        ForeignKey("hebel_recommendations.id", ondelete="CASCADE")
    )
    measured_at: Mapped[datetime] = mapped_column(UTCDateTime())
    source_reference: Mapped[str] = mapped_column(Text)
    method_version: Mapped[str] = mapped_column(Text)
    result: Mapped[dict] = mapped_column(JSON)
