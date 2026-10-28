"""SqlRepository end to end through the Repository port, against real Postgres."""

from datetime import UTC, date, datetime
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


# ---------------------------------------------------------------------- time-travel reads
def _at(month: int, day: int = 15) -> datetime:
    return datetime(2026, month, day, 12, 0, tzinfo=UTC)


async def _three_checkpoints(repo: SqlRepository, ids: Any, make: Any) -> str:
    """One company checked in January (green), June (yellow) and September (red)."""
    cui = ids.cui()
    await repo.save_identity_sheet(
        ids.run(1), make.sheet(cui, current_name=f"ISTORIC {ids.tag} SRL")
    )
    for n, (month, band) in enumerate(((1, Band.GREEN), (6, Band.YELLOW), (9, Band.RED)), start=1):
        await repo.save_agent_result(
            ids.run(n),
            make.result(
                "tax",
                [
                    make.signal(cui, f"TAX-TEST-01:{m}", evidence_date=date(2026, m, 1))
                    for m in range(1, month + 1)
                ],
            ),
        )
        await repo.save_score(make.score(cui, ids.run(n), band=band, computed_at=_at(month)))
    return cui


async def test_score_as_of_is_what_the_bank_knew(repo: SqlRepository, ids: Any, make: Any) -> None:
    cui = await _three_checkpoints(repo, ids, make)
    assert await repo.get_score_as_of(cui, _at(1, 1)) is None  # not checked yet
    bands = [
        (s.band if (s := await repo.get_score_as_of(cui, _at(m))) else None) for m in (1, 3, 6, 10)
    ]
    assert bands == [Band.GREEN, Band.GREEN, Band.YELLOW, Band.RED]


async def test_score_history_between_x_and_y(repo: SqlRepository, ids: Any, make: Any) -> None:
    cui = await _three_checkpoints(repo, ids, make)
    history = await repo.list_score_history(cui, since=_at(2, 1), until=_at(9))  # inclusive
    assert [(s.run_id, s.band) for s in history] == [
        (ids.run(2), Band.YELLOW),
        (ids.run(3), Band.RED),
    ]
    assert len(await repo.list_score_history(cui)) == 3


async def test_signals_as_of_follow_the_run_known_then(
    repo: SqlRepository, ids: Any, make: Any
) -> None:
    cui = await _three_checkpoints(repo, ids, make)
    assert len(await repo.list_signals_as_of(cui, _at(7))) == 6  # June run: Jan..Jun
    assert len(await repo.list_signals_as_of(cui, _at(12))) == 9
    assert await repo.list_signals_as_of(cui, _at(1, 1)) == []


async def test_events_between_dates(repo: SqlRepository, ids: Any, make: Any) -> None:
    cui = await _three_checkpoints(repo, ids, make)
    events = await repo.list_events(cui, since=date(2026, 3, 1), until=date(2026, 5, 1))
    assert [e.evidence_date for e in events] == [
        date(2026, 3, 1),
        date(2026, 4, 1),
        date(2026, 5, 1),
    ]
    assert len(await repo.list_events(cui)) == 9


async def test_portfolio_as_of(repo: SqlRepository, ids: Any, make: Any) -> None:
    cui = await _three_checkpoints(repo, ids, make)
    later = ids.cui(7)
    await repo.save_identity_sheet(ids.run(7), make.sheet(later, current_name=f"NOU {ids.tag} SRL"))
    await repo.save_score(make.score(later, ids.run(7), band=Band.GREEN, computed_at=_at(8)))

    def page(as_of: datetime, band: Band | None = None) -> Any:
        return repo.list_portfolio_as_of(as_of=as_of, band=band, q=ids.tag, page=1, page_size=10)

    assert await page(_at(1, 1)) == ([], 0)
    assert await page(_at(7)) == ([cui], 1)  # the second company is checked only in August
    assert await page(_at(10)) == ([cui, later], 2)
    assert await page(_at(7), Band.YELLOW) == ([cui], 1)
    assert await page(_at(10), Band.YELLOW) == ([], 0)  # red by then
    assert await page(_at(10), Band.GREEN) == ([later], 1)


async def test_decisions_between(repo: SqlRepository, ids: Any, make: Any) -> None:
    cui = ids.cui()
    jan = make.decision(cui, f"dec_{ids.tag}_1", recorded_at=_at(1))
    jun = make.decision(cui, f"dec_{ids.tag}_2", recorded_at=_at(6))
    await repo.record_decision(jan)
    await repo.record_decision(jun)
    assert await repo.list_decisions_between(cui, since=_at(2, 1)) == [jun]
    assert await repo.list_decisions_between(cui, until=_at(1)) == [jan]
