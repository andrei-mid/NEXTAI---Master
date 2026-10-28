"""audit_create_tables

Revision ID: a6aud0000001
Revises: a5mem0000001
Create Date: 2026-10-28 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a6aud0000001"
down_revision: str | None = "a5mem0000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_decisions",
        sa.Column("decision_id", sa.String(64), nullable=False),
        sa.Column("cui", sa.String(16), nullable=False),
        sa.Column("run_id", sa.String(64), nullable=True),
        sa.Column("decision", sa.String(32), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("analyst", sa.Text(), nullable=False),
        sa.Column("band_at_decision", sa.String(16), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("decision_id", name=op.f("pk_audit_decisions")),
    )
    op.create_index(op.f("ix_audit_decisions_cui"), "audit_decisions", ["cui"])
    # Append-only for every role (owner included): GRANTs alone do not bind the table owner.
    op.execute(
        """
        CREATE FUNCTION audit_decisions_append_only() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'audit_decisions is append-only (% refused)', TG_OP;
        END
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_decisions_append_only
        BEFORE UPDATE OR DELETE OR TRUNCATE ON audit_decisions
        FOR EACH STATEMENT EXECUTE FUNCTION audit_decisions_append_only()
        """
    )


def downgrade() -> None:
    op.drop_table("audit_decisions")
    op.execute("DROP FUNCTION audit_decisions_append_only()")
