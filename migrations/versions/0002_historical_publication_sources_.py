"""historical publication sources recommendations and reviews

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "hebel_import_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "hebel_publications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("issue_year", sa.Integer(), nullable=False),
        sa.Column("issue_number", sa.Integer(), nullable=False),
        sa.Column("selected_sha", sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("issue_year", "issue_number", name="uq_hebel_issue"),
    )
    op.create_table(
        "hebel_documents",
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("publication_id", sa.Integer(), nullable=True),
        sa.Column("publication_date", sa.Date(), nullable=True),
        sa.Column("original_pdf", sa.LargeBinary(), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("extractor_version", sa.String(length=64), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("extraction_status", sa.String(length=20), nullable=False),
        sa.Column("review_status", sa.String(length=20), nullable=False),
        sa.Column("revision_conflict", sa.Boolean(), nullable=False),
        sa.Column("pages", sa.JSON(), nullable=False),
        sa.Column("flags", sa.JSON(), nullable=False),
        sa.Column("metadata_evidence", sa.JSON(), nullable=False),
        sa.Column("verified_available_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("availability_evidence", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["publication_id"],
            ["hebel_publications.id"],
        ),
        sa.PrimaryKeyConstraint("sha256"),
    )
    op.create_table(
        "hebel_recommendations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_sha", sa.String(length=64), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("stock_name", sa.Text(), nullable=True),
        sa.Column("stock_wkn", sa.String(length=6), nullable=True),
        sa.Column("stock_isin", sa.String(length=12), nullable=True),
        sa.Column("derivative_wkn", sa.String(length=6), nullable=True),
        sa.Column("derivative_isin", sa.String(length=12), nullable=True),
        sa.Column("product_type", sa.Text(), nullable=True),
        sa.Column("issuer", sa.Text(), nullable=True),
        sa.Column("strike", sa.Numeric(precision=38, scale=18), nullable=True),
        sa.Column("strike_currency", sa.String(length=3), nullable=True),
        sa.Column("maturity_date", sa.Date(), nullable=True),
        sa.Column("term_text", sa.Text(), nullable=True),
        sa.Column("entry_price", sa.Numeric(precision=38, scale=18), nullable=True),
        sa.Column("entry_kind", sa.String(length=20), nullable=True),
        sa.Column("omega", sa.Numeric(precision=38, scale=18), nullable=True),
        sa.Column("omega_label", sa.Text(), nullable=True),
        sa.Column("stock_price", sa.Numeric(precision=38, scale=18), nullable=True),
        sa.Column("derivative_target1", sa.Numeric(precision=38, scale=18), nullable=True),
        sa.Column("derivative_target2", sa.Numeric(precision=38, scale=18), nullable=True),
        sa.Column("derivative_stop1", sa.Numeric(precision=38, scale=18), nullable=True),
        sa.Column("derivative_stop2", sa.Numeric(precision=38, scale=18), nullable=True),
        sa.Column("stock_target1", sa.Numeric(precision=38, scale=18), nullable=True),
        sa.Column("stock_target2", sa.Numeric(precision=38, scale=18), nullable=True),
        sa.Column("stock_stop1", sa.Numeric(precision=38, scale=18), nullable=True),
        sa.Column("stock_stop2", sa.Numeric(precision=38, scale=18), nullable=True),
        sa.Column("crv", sa.Numeric(precision=38, scale=18), nullable=True),
        sa.Column("derivative_currency", sa.String(length=3), nullable=True),
        sa.Column("stock_currency", sa.String(length=3), nullable=True),
        sa.Column("quote_as_of_text", sa.Text(), nullable=True),
        sa.Column("fundamental_notes", sa.Text(), nullable=True),
        sa.Column("source_commentary", sa.Text(), nullable=True),
        sa.Column("technical_notes", sa.Text(), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("flags", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["document_sha"], ["hebel_documents.sha256"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_sha", "ordinal", name="uq_hebel_recommendation"),
    )
    op.create_index(
        op.f("ix_hebel_recommendations_document_sha"),
        "hebel_recommendations",
        ["document_sha"],
        unique=False,
    )
    op.create_table(
        "hebel_reviews",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_sha", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("reviewer", sa.Text(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verified_available_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("availability_evidence", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["document_sha"], ["hebel_documents.sha256"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "hebel_source_locations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_sha", sa.String(length=64), nullable=False),
        sa.Column("root_id", sa.String(length=64), nullable=False),
        sa.Column("relative_path", sa.Text(), nullable=False),
        sa.Column("categories", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["document_sha"], ["hebel_documents.sha256"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_sha", "root_id", "relative_path", name="uq_hebel_location"),
    )
    op.create_table(
        "hebel_outcomes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("recommendation_id", sa.Integer(), nullable=False),
        sa.Column("measured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_reference", sa.Text(), nullable=False),
        sa.Column("method_version", sa.Text(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["recommendation_id"], ["hebel_recommendations.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade():
    op.drop_table("hebel_outcomes")
    op.drop_table("hebel_source_locations")
    op.drop_table("hebel_reviews")
    op.drop_index(op.f("ix_hebel_recommendations_document_sha"), table_name="hebel_recommendations")
    op.drop_table("hebel_recommendations")
    op.drop_table("hebel_documents")
    op.drop_table("hebel_publications")
    op.drop_table("hebel_import_runs")
