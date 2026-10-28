"""STUB. Owner: @role-1-database. Index of the LOCAL MIRROR (docs/LOCAL_DATA.md): what each
adapter has downloaded onto our server. The bytes live in the ObjectStore.

Today the mirror entries are `mirror/<adapter>/<hash(cache_key)>` JSON files in the ObjectStore
(written by BaseAdapter.store_in_mirror). These tables make them queryable: "what is stale?",
"which companies are not synced?", audit and replay of any signal's SourceRef.

Planned tables (write them as SQLAlchemy 2.0 typed models: `class X(Base)` with `Mapped[...]`,
then generate the migration `alembic revision --autogenerate -m "source_cache_create_tables"`):
- source_cache_raw: content_hash PK, adapter, raw_ref (ObjectStore key), url, retrieved_at, size_bytes
- source_cache_mirror: (adapter, cache_key) PK, cui (indexed), content_hash FK, retrieved_at (indexed)
  -> the current mirror entry per request. Write it from store_in_mirror (ask role 2 for the hook).
"""

from __future__ import annotations

from verifirm.persistence.models.base import Base

__all__ = ["Base"]
