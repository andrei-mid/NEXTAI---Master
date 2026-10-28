"""STUB. Owner: @role-1-database. Queries for the `graph_*` tables (see models/graph.py).

Implement an `GraphStore` class that takes an AsyncSession and exposes the
reads/writes SqlRepository needs. Upserts use INSERT ... ON CONFLICT (idempotent jobs).
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession


class GraphStore:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
