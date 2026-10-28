"""companies_create_tables

Revision ID: a1c0mp000001
Revises: 
Create Date: 2026-10-28 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a1c0mp000001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "companies_companies",
        sa.Column("cui", sa.String(16), nullable=False),
        sa.Column("current_name", sa.Text(), nullable=True),
        sa.Column("fictional", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("in_portfolio", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("latest_run_id", sa.String(64), nullable=True),
        sa.Column("latest_band", sa.String(16), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("cui", name=op.f("pk_companies_companies")),
    )
    op.create_index(
        op.f("ix_companies_companies_latest_band"), "companies_companies", ["latest_band"]
    )
    op.create_table(
        "companies_identity_sheets",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("cui", sa.String(16), nullable=False),
        sa.Column("run_id", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["cui"],
            ["companies_companies.cui"],
            name=op.f("fk_companies_identity_sheets_cui_companies_companies"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_companies_identity_sheets")),
        sa.UniqueConstraint("run_id", name=op.f("uq_companies_identity_sheets_run_id")),
    )
    op.create_index(
        op.f("ix_companies_identity_sheets_cui"), "companies_identity_sheets", ["cui"]
    )
    op.create_table(
        "companies_submitted_financials",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("run_id", sa.String(64), nullable=False),
        sa.Column("cui", sa.String(16), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_companies_submitted_financials")),
        sa.UniqueConstraint("run_id", name=op.f("uq_companies_submitted_financials_run_id")),
    )
    op.create_index(
        op.f("ix_companies_submitted_financials_cui"), "companies_submitted_financials", ["cui"]
    )


def downgrade() -> None:
    op.drop_table("companies_submitted_financials")
    op.drop_table("companies_identity_sheets")
    op.drop_table("companies_companies")
