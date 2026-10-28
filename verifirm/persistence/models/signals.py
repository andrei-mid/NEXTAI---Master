"""STUB. Owner: @role-1-database. Signals produced by agents (after entity resolution).

Planned tables (write them as SQLAlchemy 2.0 typed models: `class X(Base)` with `Mapped[...]`,
then generate the migration `alembic revision --autogenerate -m "signals_create_tables"`):
- signals_signals: (run_id, signal_id) PK, cui, agent, component, rule_id, severity, validated, auto_stop_candidate, confidence, evidence_date, payload JSONB (schema.signals.Signal)
- indexes: (cui, run_id), rule_id, severity
"""

from __future__ import annotations

from verifirm.persistence.models.base import Base

__all__ = ["Base"]
