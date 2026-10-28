"""STUB. Owner: @role-1-database. Deterministic scores per run.

Planned tables (write them as SQLAlchemy 2.0 typed models: `class X(Base)` with `Mapped[...]`,
then generate the migration `alembic revision --autogenerate -m "scores_create_tables"`):
- scores_scores: run_id PK, cui (indexed), trust_score, band (indexed), coverage_pct, config_version, computed_at, payload JSONB (schema.scoring.Score)
- Portfolio view = latest score per cui (DISTINCT ON (cui) ORDER BY computed_at DESC)
"""

from __future__ import annotations

from verifirm.persistence.models.base import Base

__all__ = ["Base"]
