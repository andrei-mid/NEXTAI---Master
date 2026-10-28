"""STUB. Owner: @role-1-database. Pipeline runs (idempotent by run_id).

Planned tables (write them as SQLAlchemy 2.0 typed models: `class X(Base)` with `Mapped[...]`,
then generate the migration `alembic revision --autogenerate -m "runs_create_tables"`):
- runs_runs: run_id PK, cui (indexed), trigger, state, requested_at, started_at, finished_at, band, error, request JSONB (schema.runs.RunRequest)
- runs_agent_results: (run_id, agent) PK, component, status, duration_ms, sources_checked/failed text[], notes, payload JSONB
"""

from __future__ import annotations

from verifirm.persistence.models.base import Base

__all__ = ["Base"]
