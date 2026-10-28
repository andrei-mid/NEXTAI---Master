"""SqlRepository end to end through the Repository port, against real Postgres."""

from typing import Any

from verifirm.persistence.repositories.sql_repository import SqlRepository
from verifirm.schema.runs import RunState
from verifirm.schema.scoring import Band


async def test_run_roundtrip_and_upsert(repo: SqlRepository, ids: Any, make: Any) -> None:
    cui, run_id = ids.cui(), ids.run()
    assert await repo.get_run(run_id) is None
    await repo.save_run(make.run(run_id, cui))
    await repo.save_run(make.run(run_id, cui, state=RunState.COMPLETED, band=Band.GREEN))
    got = await repo.get_run(run_id)
    assert got is not None
    assert got.state == RunState.COMPLETED and got.band == Band.GREEN


async def test_identity_sheet_latest_wins(repo: SqlRepository, ids: Any, make: Any) -> None:
    cui = ids.cui()
    await repo.save_identity_sheet(ids.run(1), make.sheet(cui, current_name="VECHI SRL"))
    await repo.save_identity_sheet(ids.run(2), make.sheet(cui, current_name="NOU SRL"))
    sheet = await repo.get_identity_sheet(cui)
    assert sheet is not None and sheet.current_name == "NOU SRL"
    assert await repo.get_identity_sheet(ids.cui(9)) is None


async def test_agent_results_roundtrip_idempotent(repo: SqlRepository, ids: Any, make: Any) -> None:
    cui, run_id = ids.cui(), ids.run()
    sig = make.signal(cui, "TAX-TEST-01:aaaa")
    result = make.result("tax", [sig, sig])  # duplicate signal in one result
    await repo.save_agent_result(run_id, result)
    await repo.save_agent_result(run_id, result)  # re-run of the same job
    results = await repo.list_agent_results(run_id)
    assert len(results) == 1
    assert results[0].signals == [sig]
    assert results[0].model_dump(exclude={"signals"}) == result.model_dump(exclude={"signals"})


async def test_list_signals_follows_latest_score(repo: SqlRepository, ids: Any, make: Any) -> None:
    cui = ids.cui()
    assert await repo.list_signals(cui) == []
    old, new = make.signal(cui, "TAX-TEST-01:old"), make.signal(cui, "TAX-TEST-01:new")
    await repo.save_agent_result(ids.run(1), make.result("tax", [old]))
    await repo.save_agent_result(ids.run(2), make.result("tax", [new]))
    await repo.save_score(make.score(cui, ids.run(1), minutes=0))
    await repo.save_score(make.score(cui, ids.run(2), minutes=5))
    assert await repo.list_signals(cui) == [new]


async def test_portfolio_band_and_query(repo: SqlRepository, ids: Any, make: Any) -> None:
    red, green = ids.cui(1), ids.cui(2)
    await repo.save_identity_sheet(ids.run(1), make.sheet(red, current_name=f"ROSU {ids.tag} SRL"))
    await repo.save_identity_sheet(
        ids.run(2), make.sheet(green, current_name=f"VERDE {ids.tag} SRL")
    )
    await repo.save_score(make.score(red, ids.run(1), band=Band.RED))
    await repo.save_score(make.score(green, ids.run(2), band=Band.GREEN))

    assert await repo.list_portfolio(band=None, q=ids.tag, page=1, page_size=10) == (
        [red, green],
        2,
    )
    assert await repo.list_portfolio(band=Band.RED, q=ids.tag, page=1, page_size=10) == ([red], 1)
    assert await repo.list_portfolio(band=None, q=f"verde {ids.tag}", page=1, page_size=10) == (
        [green],
        1,
    )
    assert await repo.list_portfolio(band=None, q=green, page=1, page_size=10) == ([green], 1)
    assert await repo.list_portfolio(band=None, q=ids.tag, page=2, page_size=1) == ([green], 2)


async def test_memo_latest(repo: SqlRepository, ids: Any, make: Any) -> None:
    cui = ids.cui()
    assert await repo.get_latest_memo(cui) is None
    await repo.save_memo(make.memo(cui, ids.run(2), minutes=5, markdown="# nou"))
    await repo.save_memo(make.memo(cui, ids.run(1), minutes=0, markdown="# vechi"))
    memo = await repo.get_latest_memo(cui)
    assert memo is not None and memo.markdown == "# nou"


async def test_decisions_append_only_and_ordered(repo: SqlRepository, ids: Any, make: Any) -> None:
    cui = ids.cui()
    second = make.decision(cui, f"dec_{ids.tag}_2", minutes=5)
    first = make.decision(cui, f"dec_{ids.tag}_1", minutes=0, run_id=ids.run())
    await repo.record_decision(second)
    await repo.record_decision(first)
    await repo.record_decision(first)  # retried request: no duplicate
    assert await repo.list_decisions(cui) == [first, second]
