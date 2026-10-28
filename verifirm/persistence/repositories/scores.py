"""STUB. Owner: @role-1-database. Queries for the `scores_*` tables (see models/scores.py).

Implement an `ScoresStore` class that takes an AsyncSession and exposes the
reads/writes SqlRepository needs. Upserts use INSERT ... ON CONFLICT (idempotent jobs).
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession


class ScoresStore:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
