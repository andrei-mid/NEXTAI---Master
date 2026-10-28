"""STUB. Owner: @role-1-database. APPEND-ONLY audit log of analyst decisions (the AI never decides).

Planned tables (write them as SQLAlchemy 2.0 typed models: `class X(Base)` with `Mapped[...]`,
then generate the migration `alembic revision --autogenerate -m "audit_create_tables"`):
- audit_decisions: decision_id PK, cui (indexed), run_id, decision, comment, analyst, band_at_decision, recorded_at
- The application DB role gets INSERT/SELECT only (no UPDATE/DELETE): grant it in the migration.
- Retention period: PENDING in docs/DECISIONS.md (GDPR).
"""

from __future__ import annotations

from verifirm.persistence.models.base import Base

__all__ = ["Base"]
