"""memos_create_tables

Revision ID: a5mem0000001
Revises: a4sco0000001
Create Date: 2026-10-28 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a5mem0000001"
down_revision: str | None = "a4sco0000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "memos_memos",
        sa.Column("run_id", sa.String(64), nullable=False),
        sa.Column("cui", sa.String(16), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("model", sa.String(128), nullable=True),
        sa.Column("verifier_passed", sa.Boolean(), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("run_id", name=op.f("pk_memos_memos")),
    )
    op.create_index("ix_memos_memos_cui_generated_at", "memos_memos", ["cui", "generated_at"])


def downgrade() -> None:
    op.drop_table("memos_memos")
