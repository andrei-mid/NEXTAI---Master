"""STUB. Owner: @role-1-database. Queries for the `source_cache_*` tables (see models/source_cache.py).

Implement an `SourceCacheStore` class that takes an AsyncSession and exposes the
reads/writes SqlRepository needs. Upserts use INSERT ... ON CONFLICT (idempotent jobs).
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession


class SourceCacheStore:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
