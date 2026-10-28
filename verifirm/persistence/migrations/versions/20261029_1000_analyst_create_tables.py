"""analyst_create_tables

Revision ID: a7ana0000001
Revises: a6aud0000001
Create Date: 2026-10-29 10:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a7ana0000001"
down_revision: str | None = "a6aud0000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "analyst_opinions",
        sa.Column("run_id", sa.String(64), nullable=False),
        sa.Column("cui", sa.String(16), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("model", sa.String(128), nullable=True),
        sa.Column("opinion_score", sa.Integer(), nullable=True),
        sa.Column("n_flags", sa.Integer(), nullable=False),
        sa.Column("n_rejected", sa.Integer(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("dossier", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.PrimaryKeyConstraint("run_id", name=op.f("pk_analyst_opinions")),
    )
    op.create_index(
        "ix_analyst_opinions_cui_generated_at", "analyst_opinions", ["cui", "generated_at"]
    )


def downgrade() -> None:
    op.drop_table("analyst_opinions")
