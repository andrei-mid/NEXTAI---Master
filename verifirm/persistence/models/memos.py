"""STUB. Owner: @role-1-database. Memos after the critic pass.

Planned tables (write them as SQLAlchemy 2.0 typed models: `class X(Base)` with `Mapped[...]`,
then generate the migration `alembic revision --autogenerate -m "memos_create_tables"`):
- memos_memos: run_id PK, cui (indexed), generated_at, model, verifier_passed bool, payload JSONB (schema.memo.Memo)
"""

from __future__ import annotations

from verifirm.persistence.models.base import Base

__all__ = ["Base"]
