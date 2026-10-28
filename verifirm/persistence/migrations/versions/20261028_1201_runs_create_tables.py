"""runs_create_tables

Revision ID: a2run0000001
Revises: a1c0mp000001
Create Date: 2026-10-28 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a2run0000001"
down_revision: str | None = "a1c0mp000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "runs_runs",
        sa.Column("run_id", sa.String(64), nullable=False),
        sa.Column("cui", sa.String(16), nullable=False),
        sa.Column("trigger", sa.String(16), nullable=True),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("band", sa.String(16), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("request", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("run_id", name=op.f("pk_runs_runs")),
    )
    op.create_index(op.f("ix_runs_runs_cui"), "runs_runs", ["cui"])
    op.create_table(
        "runs_agent_results",
        sa.Column("run_id", sa.String(64), nullable=False),
        sa.Column("agent", sa.String(32), nullable=False),
        sa.Column("component", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("sources_checked", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("sources_failed", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("run_id", "agent", name=op.f("pk_runs_agent_results")),
    )


def downgrade() -> None:
    op.drop_table("runs_agent_results")
    op.drop_table("runs_runs")
