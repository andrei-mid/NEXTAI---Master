"""Integration tests against the Docker Postgres (`make up`). Skipped if it is unreachable;
CI always runs them (postgres:17 service). No SQLite, not even in tests."""

from collections.abc import AsyncIterator

import pytest
from sqlalchemy import text

from verifirm.core.config import Settings
from verifirm.persistence import engine as db


@pytest.fixture
async def pg() -> AsyncIterator[Settings]:
    settings = Settings()
    try:
        async with db.create_engine(settings).connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:  # unreachable / auth / not started
        pytest.skip(
            f"Postgres not reachable at DATABASE_URL ({type(exc).__name__}). Run `make up`."
        )
    yield settings
    await db.dispose_engine()


def test_sqlite_is_refused() -> None:
    with pytest.raises(ValueError):
        db.create_engine(Settings(database_url="sqlite+aiosqlite:///x.db"))


async def test_session_scope_and_server_version(pg: Settings) -> None:
    async with db.session_scope(pg) as session:
        version = (await session.execute(text("SHOW server_version"))).scalar_one()
    assert str(version).startswith("17"), f"local Postgres must match RDS (17), got {version}"


async def test_copy_records(pg: Settings) -> None:
    async with db.get_engine(pg).begin() as conn:
        await conn.execute(text("CREATE TABLE IF NOT EXISTS _copy_probe (a int, b text)"))
        await conn.execute(text("TRUNCATE _copy_probe"))
    await db.copy_records("_copy_probe", ["a", "b"], [(1, "x"), (2, "y")], settings=pg)
    async with db.get_engine(pg).begin() as conn:
        n = (await conn.execute(text("SELECT count(*) FROM _copy_probe"))).scalar_one()
        await conn.execute(text("DROP TABLE _copy_probe"))
    assert n == 2
