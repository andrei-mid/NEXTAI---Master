"""SignalsStore: idempotent replace per (run_id, agent)."""

from typing import Any

from verifirm.core.config import Settings
from verifirm.persistence.engine import session_scope
from verifirm.persistence.repositories.signals import SignalsStore
from verifirm.persistence.repositories.sql_repository import SqlRepository


async def test_rerun_drops_signals_no_longer_reported(
    repo: SqlRepository, migrated_db: Settings, ids: Any, make: Any
) -> None:
    cui, run_id = ids.cui(), ids.run()
    a, b = make.signal(cui, "TAX-TEST-01:a"), make.signal(cui, "TAX-TEST-01:b")
    other = make.signal(cui, "LIT-TEST-01:c", agent="litigation")
    async with session_scope(migrated_db) as s:
        store = SignalsStore(s)
        await store.replace_for_agent(run_id, "tax", [a, b])
        await store.replace_for_agent(run_id, "litigation", [other])
        await store.replace_for_agent(run_id, "tax", [b])
        by_agent = await store.by_agent_for_run(run_id)
    assert by_agent == {"litigation": [other], "tax": [b]}


async def test_empty_replace_clears_agent(
    repo: SqlRepository, migrated_db: Settings, ids: Any, make: Any
) -> None:
    cui, run_id = ids.cui(), ids.run()
    async with session_scope(migrated_db) as s:
        store = SignalsStore(s)
        await store.replace_for_agent(run_id, "tax", [make.signal(cui, "TAX-TEST-01:a")])
        await store.replace_for_agent(run_id, "tax", [])
        assert await store.list_for_run(run_id) == []


async def test_upsert_updates_payload(
    repo: SqlRepository, migrated_db: Settings, ids: Any, make: Any
) -> None:
    cui, run_id = ids.cui(), ids.run()
    async with session_scope(migrated_db) as s:
        store = SignalsStore(s)
        await store.replace_for_agent(run_id, "tax", [make.signal(cui, "TAX-TEST-01:a")])
        changed = make.signal(cui, "TAX-TEST-01:a", confidence=0.5)
        await store.replace_for_agent(run_id, "tax", [changed])
        assert await store.list_for_run(run_id) == [changed]
