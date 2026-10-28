"""MemosStore: one memo per run, latest by generated_at, verifier flag denormalised."""

from typing import Any

from verifirm.core.config import Settings
from verifirm.persistence.engine import session_scope
from verifirm.persistence.models.memos import MemoRow
from verifirm.persistence.repositories.sql_repository import SqlRepository


async def test_roundtrip_and_verifier_flag(
    repo: SqlRepository, migrated_db: Settings, ids: Any, make: Any
) -> None:
    cui, run_id = ids.cui(), ids.run()
    memo = make.memo(cui, run_id)
    await repo.save_memo(memo)
    await repo.save_memo(memo)
    assert await repo.get_latest_memo(cui) == memo
    async with session_scope(migrated_db) as s:
        row = await s.get(MemoRow, run_id)
    assert row is not None and row.verifier_passed is True


async def test_memo_without_critic(repo: SqlRepository, ids: Any, make: Any) -> None:
    cui = ids.cui()
    memo = make.memo(cui, ids.run(), verifier_report=None)
    await repo.save_memo(memo)
    assert await repo.get_latest_memo(cui) == memo
