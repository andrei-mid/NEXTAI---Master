"""scores_create_tables

Revision ID: a4sco0000001
Revises: a3sig0000001
Create Date: 2026-10-28 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a4sco0000001"
down_revision: str | None = "a3sig0000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "scores_scores",
        sa.Column("run_id", sa.String(64), nullable=False),
        sa.Column("cui", sa.String(16), nullable=False),
        sa.Column("trust_score", sa.Float(), nullable=True),
        sa.Column("band", sa.String(16), nullable=False),
        sa.Column("coverage_pct", sa.Float(), nullable=False),
        sa.Column("config_version", sa.String(64), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("run_id", name=op.f("pk_scores_scores")),
    )
    op.create_index("ix_scores_scores_cui_computed_at", "scores_scores", ["cui", "computed_at"])
    op.create_index(op.f("ix_scores_scores_band"), "scores_scores", ["band"])


def downgrade() -> None:
    op.drop_table("scores_scores")
