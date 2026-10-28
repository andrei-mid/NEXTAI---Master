"""RunsStore: the request and the status are written independently."""

from typing import Any

from verifirm.core.config import Settings
from verifirm.persistence.engine import session_scope
from verifirm.persistence.models.runs import Run
from verifirm.persistence.repositories.runs import RunsStore
from verifirm.persistence.repositories.sql_repository import SqlRepository
from verifirm.schema.runs import RunRequest, RunState, RunTrigger


async def test_request_then_status_keeps_both(
    repo: SqlRepository, migrated_db: Settings, ids: Any, make: Any
) -> None:
    cui, run_id = ids.cui(), ids.run()
    request = RunRequest(
        run_id=run_id,
        cui=cui,
        trigger=RunTrigger.APPLICATION,
        disabled_sources=["anaf_v9"],
        requested_at=make.run(run_id, cui).started_at,
    )
    async with session_scope(migrated_db) as s:
        await RunsStore(s).save_request(request)
    await repo.save_run(make.run(run_id, cui, state=RunState.RUNNING))
    async with session_scope(migrated_db) as s:
        await RunsStore(s).save_request(request)  # replayed message must not reset the state
        row = await s.get(Run, run_id)
    assert row is not None
    assert row.state == "running" and row.trigger == "application"
    assert RunRequest.model_validate(row.request) == request
