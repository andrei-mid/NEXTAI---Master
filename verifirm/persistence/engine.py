"""Async engine + session factory from DATABASE_URL. Pool sizing comes from env (DB_POOL_*).

async with session_scope() as session:
    session.add(row)            # committed on exit, rolled back on error

await copy_records("onrc_companies", ["cui", "name"], rows)   # bulk COPY via asyncpg
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterable, Sequence
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from verifirm.core.config import Settings, get_settings

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def create_engine(settings: Settings) -> AsyncEngine:
    if not settings.database_url.startswith("postgresql+asyncpg://"):
        raise ValueError("DATABASE_URL must use postgresql+asyncpg:// (Postgres only, no SQLite)")
    return create_async_engine(
        settings.database_url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout_s,
        pool_pre_ping=True,
        echo=settings.db_echo,
    )


def get_engine(settings: Settings | None = None) -> AsyncEngine:
    """Process-wide engine (one pool per API replica / worker process)."""
    global _engine
    if _engine is None:
        _engine = create_engine(settings or get_settings())
    return _engine


def get_sessionmaker(settings: Settings | None = None) -> async_sessionmaker[AsyncSession]:
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(get_engine(settings), expire_on_commit=False)
    return _sessionmaker


@asynccontextmanager
async def session_scope(settings: Settings | None = None) -> AsyncIterator[AsyncSession]:
    """One unit of work: commit on success, roll back on any exception."""
    session = get_sessionmaker(settings)()
    try:
        yield session
        await session.commit()
    except BaseException:
        await session.rollback()
        raise
    finally:
        await session.close()


async def copy_records(
    table: str,
    columns: Sequence[str],
    records: Iterable[Sequence[Any]],
    *,
    schema_name: str | None = None,
    settings: Settings | None = None,
) -> None:
    """Bulk load with Postgres COPY (asyncpg copy_records_to_table). Use it for every bulk ingest.

    Load into a staging table and then swap/merge in SQL, so readers never see a half-loaded table.
    """
    async with get_engine(settings).connect() as conn:
        raw = await conn.get_raw_connection()
        driver = raw.driver_connection  # asyncpg.Connection
        assert driver is not None
        await driver.copy_records_to_table(
            table, records=records, columns=list(columns), schema_name=schema_name
        )
        await conn.commit()


async def dispose_engine() -> None:
    """Close the pool (app shutdown, end of a test session)."""
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _sessionmaker = None
