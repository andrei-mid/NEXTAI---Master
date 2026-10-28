"""AuditStore + the append-only trigger: UPDATE / DELETE / TRUNCATE are refused for everyone."""

from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from verifirm.core.config import Settings
from verifirm.persistence.engine import session_scope
from verifirm.persistence.repositories.sql_repository import SqlRepository


async def test_duplicate_decision_is_noop(repo: SqlRepository, ids: Any, make: Any) -> None:
    cui = ids.cui()
    record = make.decision(cui, f"dec_{ids.tag}")
    await repo.record_decision(record)
    await repo.record_decision(record.model_copy(update={"comment": "changed"}))
    assert await repo.list_decisions(cui) == [record]


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE audit_decisions SET comment = 'x' WHERE cui = :cui",
        "DELETE FROM audit_decisions WHERE cui = :cui",
        "TRUNCATE audit_decisions",
    ],
)
async def test_mutations_are_refused(
    sql: str, repo: SqlRepository, migrated_db: Settings, ids: Any, make: Any
) -> None:
    cui = ids.cui()
    await repo.record_decision(make.decision(cui, f"dec_{ids.tag}"))
    with pytest.raises(DBAPIError, match="append-only"):
        async with session_scope(migrated_db) as s:
            await s.execute(text(sql), {"cui": cui} if ":cui" in sql else {})
    assert len(await repo.list_decisions(cui)) == 1
