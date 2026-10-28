"""ScoresStore: latest is by computed_at, not by insertion order; re-save is an upsert."""

from typing import Any

from verifirm.persistence.repositories.sql_repository import SqlRepository
from verifirm.schema.scoring import Band


async def test_latest_by_computed_at(repo: SqlRepository, ids: Any, make: Any) -> None:
    cui = ids.cui()
    assert await repo.get_latest_score(cui) is None
    newer = make.score(cui, ids.run(2), band=Band.RED, minutes=10)
    await repo.save_score(newer)
    await repo.save_score(make.score(cui, ids.run(1), band=Band.GREEN, minutes=0))
    assert await repo.get_latest_score(cui) == newer


async def test_resave_same_run_updates(repo: SqlRepository, ids: Any, make: Any) -> None:
    cui, run_id = ids.cui(), ids.run()
    await repo.save_score(make.score(cui, run_id, band=Band.GREY, trust_score=None))
    updated = make.score(cui, run_id, band=Band.YELLOW)
    await repo.save_score(updated)
    assert await repo.get_latest_score(cui) == updated
