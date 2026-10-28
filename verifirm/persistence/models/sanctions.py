"""STUB. Owner: @role-1-database. Sanctions + PEP lists (bulk, COPY).

Planned tables (write them as SQLAlchemy 2.0 typed models: `class X(Base)` with `Mapped[...]`,
then generate the migration `alembic revision --autogenerate -m "sanctions_create_tables"`):
- sanctions_lists: list_id PK ('EU'|'UN'|'OFAC'|'PEP_MOCK'), source_url, published_at, content_hash, loaded_at
- sanctions_entries: (list_id, ref) PK, entity_type, names text[], names_normalized text[] (GIN index), birth_dates, countries, identifiers JSONB, programme, listed_on
- A changed content_hash triggers a portfolio re-screen (change detection).
"""

from __future__ import annotations

from verifirm.persistence.models.base import Base

__all__ = ["Base"]
