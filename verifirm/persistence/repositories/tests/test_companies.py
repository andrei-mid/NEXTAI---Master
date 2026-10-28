"""CompaniesStore: latest_* only moves forward; LIKE wildcards in `q` are literal."""

from typing import Any

from verifirm.core.config import Settings
from verifirm.persistence.engine import session_scope
from verifirm.persistence.models.companies import Company
from verifirm.persistence.repositories.sql_repository import SqlRepository
from verifirm.schema.scoring import Band


async def test_late_old_score_does_not_overwrite_latest_band(
    repo: SqlRepository, migrated_db: Settings, ids: Any, make: Any
) -> None:
    cui = ids.cui()
    await repo.save_score(make.score(cui, ids.run(2), band=Band.RED, minutes=10))
    await repo.save_score(make.score(cui, ids.run(1), band=Band.GREEN, minutes=0))
    async with session_scope(migrated_db) as s:
        row = await s.get(Company, cui)
    assert row is not None
    assert (row.latest_band, row.latest_run_id) == ("red", ids.run(2))
    latest = await repo.get_latest_score(cui)
    assert latest is not None and latest.band == Band.RED


async def test_sheet_after_score_keeps_band(repo: SqlRepository, ids: Any, make: Any) -> None:
    cui = ids.cui()
    await repo.save_score(make.score(cui, ids.run(), band=Band.STOP))
    await repo.save_identity_sheet(ids.run(), make.sheet(cui, current_name=f"X {ids.tag}"))
    assert await repo.list_portfolio(band=Band.STOP, q=ids.tag, page=1, page_size=5) == ([cui], 1)


async def test_query_wildcards_are_escaped(repo: SqlRepository, ids: Any, make: Any) -> None:
    await repo.save_identity_sheet(ids.run(), make.sheet(ids.cui(), current_name=f"A {ids.tag}"))
    assert await repo.list_portfolio(band=None, q=f"%{ids.tag}_", page=1, page_size=5) == ([], 0)
