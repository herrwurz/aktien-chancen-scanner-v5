"""initial market history signals and audit schema

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "market_candles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("asset_class", sa.String(length=16), nullable=False),
        sa.Column("symbol", sa.String(length=30), nullable=False),
        sa.Column("interval", sa.String(length=4), nullable=False),
        sa.Column("open_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("close_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("high", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("low", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("close", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("volume", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("quote_volume", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("close_time > open_time", name="ck_candle_time"),
        sa.CheckConstraint("volume >= 0 AND quote_volume >= 0", name="ck_nonnegative_volume"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider", "asset_class", "symbol", "interval", "open_time", name="uq_bar"
        ),
    )
    op.create_index(
        "ix_market_history",
        "market_candles",
        ["provider", "asset_class", "symbol", "interval", "open_time"],
        unique=False,
    )
    op.create_table(
        "scan_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("error_count", sa.Integer(), nullable=False),
        sa.Column("errors", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_scan_runs_started_at"), "scan_runs", ["started_at"], unique=False)
    op.create_table(
        "evaluations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("candle_id", sa.Integer(), nullable=False),
        sa.Column("detector_key", sa.String(length=160), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_signal", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.String(length=40), nullable=False),
        sa.Column("baseline_volume", sa.Numeric(precision=38, scale=18), nullable=True),
        sa.Column("ratio", sa.Numeric(precision=38, scale=18), nullable=True),
        sa.ForeignKeyConstraint(["candle_id"], ["market_candles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("candle_id", "detector_key", name="uq_evaluation"),
    )
    op.create_index("ix_evaluated_at", "evaluations", ["evaluated_at"], unique=False)
    op.create_table(
        "signals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("evaluation_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["evaluation_id"], ["evaluations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("evaluation_id"),
    )
    op.create_table(
        "outcomes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("signal_id", sa.Integer(), nullable=False),
        sa.Column("horizon_hours", sa.Integer(), nullable=False),
        sa.Column("measured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("return_pct", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.CheckConstraint("horizon_hours IN (1, 4, 24)", name="ck_outcome_horizon"),
        sa.ForeignKeyConstraint(["signal_id"], ["signals.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("signal_id", "horizon_hours", name="uq_outcome_horizon"),
    )


def downgrade():
    op.drop_table("outcomes")
    op.drop_table("signals")
    op.drop_index("ix_evaluated_at", table_name="evaluations")
    op.drop_table("evaluations")
    op.drop_index(op.f("ix_scan_runs_started_at"), table_name="scan_runs")
    op.drop_table("scan_runs")
    op.drop_index("ix_market_history", table_name="market_candles")
    op.drop_table("market_candles")
