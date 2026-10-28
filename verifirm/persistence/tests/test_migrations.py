"""Migrations: offline SQL renders, and the migrated database matches the models (no drift)."""

from __future__ import annotations

import io
from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy.engine import Connection

from verifirm.core.config import Settings
from verifirm.persistence import engine as db
from verifirm.persistence.models import Base

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


def test_offline_sql_renders_every_table() -> None:
    buf = io.StringIO()
    command.upgrade(Config(str(ALEMBIC_INI), output_buffer=buf), "head", sql=True)
    sql = buf.getvalue()
    for table in Base.metadata.tables:
        assert f"CREATE TABLE {table}" in sql


def _diff(conn: Connection) -> list[object]:
    ctx = MigrationContext.configure(conn, opts={"compare_type": True})
    return list(compare_metadata(ctx, Base.metadata))


async def test_models_match_migrated_schema(migrated_db: Settings) -> None:
    async with db.get_engine(migrated_db).connect() as conn:
        diff = await conn.run_sync(_diff)
    await db.dispose_engine()
    assert diff == [], f"models and migrations drifted: {diff}"
