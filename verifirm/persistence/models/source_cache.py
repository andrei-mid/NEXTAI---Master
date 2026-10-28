"""STUB. Owner: @role-1-database. Metadata index of archived raw source responses (bytes live in the ObjectStore).

Planned tables (write them as SQLAlchemy 2.0 typed models: `class X(Base)` with `Mapped[...]`,
then generate the migration `alembic revision --autogenerate -m "source_cache_create_tables"`):
- source_cache_raw: content_hash PK, adapter, cache_key, raw_ref (ObjectStore key), url, retrieved_at, size_bytes
- source_cache_last_good: (adapter, cache_key) PK, content_hash FK, retrieved_at  -> audit + replay of any signal's SourceRef
"""

from __future__ import annotations

from verifirm.persistence.models.base import Base

__all__ = ["Base"]
