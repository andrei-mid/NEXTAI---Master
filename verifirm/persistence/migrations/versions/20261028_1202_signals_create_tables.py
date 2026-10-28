"""signals_create_tables

Revision ID: a3sig0000001
Revises: a2run0000001
Create Date: 2026-10-28 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a3sig0000001"
down_revision: str | None = "a2run0000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "signals_signals",
        sa.Column("run_id", sa.String(64), nullable=False),
        sa.Column("signal_id", sa.String(128), nullable=False),
        sa.Column("cui", sa.String(16), nullable=False),
        sa.Column("agent", sa.String(32), nullable=False),
        sa.Column("component", sa.String(16), nullable=False),
        sa.Column("rule_id", sa.String(64), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("validated", sa.Boolean(), nullable=False),
        sa.Column("auto_stop_candidate", sa.Boolean(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("evidence_date", sa.Date(), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("run_id", "signal_id", name=op.f("pk_signals_signals")),
    )
    op.create_index("ix_signals_signals_cui_run_id", "signals_signals", ["cui", "run_id"])
    op.create_index(op.f("ix_signals_signals_rule_id"), "signals_signals", ["rule_id"])
    op.create_index(op.f("ix_signals_signals_severity"), "signals_signals", ["severity"])


def downgrade() -> None:
    op.drop_table("signals_signals")
