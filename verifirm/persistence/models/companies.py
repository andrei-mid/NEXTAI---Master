"""STUB. Owner: @role-1-database. Portfolio companies and their identity sheets.

Planned tables (write them as SQLAlchemy 2.0 typed models: `class X(Base)` with `Mapped[...]`,
then generate the migration `alembic revision --autogenerate -m "companies_create_tables"`):
- companies_companies: cui PK, current_name, fictional bool, in_portfolio bool, last_checked_at, latest_run_id, latest_band (indexed)
- companies_identity_sheets: id PK, cui FK, run_id, payload JSONB (schema.identity.IdentitySheet), created_at
- companies_submitted_financials: id PK, run_id, cui, payload JSONB (schema.financials.SubmittedFinancials)
"""

from __future__ import annotations

from verifirm.persistence.models.base import Base

__all__ = ["Base"]
