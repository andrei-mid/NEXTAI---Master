from datetime import UTC, date, datetime

import pytest
from fastapi import HTTPException

from apps.api.read_model import RepoReadModel, top_signal
from apps.api.routes.runs import _live_events
from apps.wiring import build_infra
from verifirm.core.config import Settings
from verifirm.core.impl_local.repository import MemoryRepository
from verifirm.schema.identity import CompanyStatus, IdentitySheet, Person, PersonRole
from verifirm.schema.memo import Memo
from verifirm.schema.runs import RunState, RunStatus
from verifirm.schema.scoring import Band, ComponentScore, Coverage, Score
from verifirm.schema.signals import (
    AgentResult,
    AgentStatus,
    Component,
    EntityMatch,
    Severity,
    Signal,
    SourceRef,
    SourceType,
)

NOW = datetime(2026, 10, 28, 8, 0, tzinfo=UTC)
CUI = "99000033"


def src(name: str = "ANAF") -> SourceRef:
    return SourceRef(
        name=name, type=SourceType.OFFICIAL, url="https://anaf.example/x", retrieved_at=NOW
    )


def sig(sid: str, severity: Severity, *, validated: bool = True, confidence: float = 0.9) -> Signal:
    return Signal(
        signal_id=sid,
        cui=CUI,
        agent="tax",
        component=Component.TAX,
        rule_id=sid.split(":")[0],
        claim=f"claim {sid}",
        source=src(),
        evidence_date=date(2026, 1, 1),
        confidence=confidence,
        severity=severity,
        validated=validated,
        entity_match=EntityMatch(method="cui_exact", score=1.0),
    )


def identity() -> IdentitySheet:
    return IdentitySheet(
        cui=CUI,
        fictional=True,
        current_name="BRUNALDO TRADE IMPEX SRL",
        status=CompanyStatus.ACTIVE,
        administrators=[
            Person(name="Sorin Imaginescu", role=PersonRole.ADMINISTRATOR, source=src("ONRC")),
            Person(
                name="Ana Veche",
                role=PersonRole.ADMINISTRATOR,
                valid_to=date(2020, 1, 1),
                source=src("ONRC"),
            ),
        ],
        shareholders=[
            Person(
                name="CALBRONA HOLDING FICTIV SRL",
                role=PersonRole.SHAREHOLDER,
                is_company=True,
                cui="99000090",
                source=src("Shareholders"),
            )
        ],
        sources=[src("ONRC")],
    )


def score() -> Score:
    return Score(
        cui=CUI,
        run_id="run_1",
        trust_score=64.8,
        band=Band.RED,
        components=[
            ComponentScore(
                component=Component.TAX, status=AgentStatus.OK, available=True, score=40, weight=0.2
            )
        ],
        coverage=Coverage(weight_pct=100.0, available=8, total=8),
        config_version="t",
        computed_at=NOW,
    )


async def seeded() -> RepoReadModel:
    repo = MemoryRepository()
    await repo.save_identity_sheet("run_1", identity())
    await repo.save_agent_result(
        "run_1",
        AgentResult(
            agent="tax",
            component=Component.TAX,
            status=AgentStatus.OK,
            sources_checked=["anaf"],
            sources_failed=[],
            signals=[sig("A-01:1", Severity.MEDIUM), sig("TAX-ARREARS-01:2", Severity.HIGH)],
            duration_ms=1,
        ),
    )
    await repo.save_score(score())
    return RepoReadModel(repo)


def test_top_signal_prefers_severity_and_ignores_media_when_others_exist() -> None:
    media = sig("MED-01:m", Severity.MEDIUM, validated=False)
    low = sig("L-01:l", Severity.LOW)
    assert top_signal([media, low]).rule_id == "L-01"  # type: ignore[union-attr]
    assert top_signal([]) is None
    assert top_signal([media]).rule_id == "MED-01"  # type: ignore[union-attr]


async def test_list_and_detail_are_passed_through_from_the_repository() -> None:
    model = await seeded()
    listing = await model.list_companies(band=None, q=None, page=1, page_size=10)
    (item,) = listing.items
    assert (item.cui, item.band, item.score, item.fictional) == (CUI, Band.RED, 64.8, True)
    assert item.top_signal is not None and item.top_signal.rule_id == "TAX-ARREARS-01"
    assert item.coverage is not None and item.coverage.label == "8/8 sources"

    detail = await model.detail(CUI)
    assert detail.band is Band.RED and detail.score == 64.8 and len(detail.components) == 1
    assert [s.name for s in detail.sources] == ["ONRC", "ANAF"]  # deduped, identity first


async def test_company_never_checked_has_null_band() -> None:
    repo = MemoryRepository()
    await repo.save_identity_sheet("r", identity())
    detail = await RepoReadModel(repo).detail(CUI)
    assert detail.band is None and detail.score is None and detail.coverage is None
    (item,) = (
        await RepoReadModel(repo).list_companies(band=None, q=None, page=1, page_size=5)
    ).items
    assert item.band is None and item.top_signal is None


async def test_unknown_company_and_missing_memo_are_404() -> None:
    model = RepoReadModel(MemoryRepository())
    for call in (model.detail("99000041"), model.signals("99000041"), model.memo("99000041")):
        with pytest.raises(HTTPException) as err:
            await call
        assert err.value.status_code == 404


async def test_memo_response_comes_from_the_stored_memo() -> None:
    model = await seeded()
    await model.repo.save_memo(
        Memo(cui=CUI, run_id="run_1", sections=[], markdown="## x\n", generated_at=NOW)
    )
    response = await model.memo(CUI)
    assert response.markdown == "## x\n" and response.verifier_report is None


async def test_graph_has_company_people_and_roles() -> None:
    graph = await (await seeded()).graph(CUI, depth=2)
    ids = {n.id for n in graph.nodes}
    assert ids == {
        f"company:{CUI}",
        "person:sorin-imaginescu",
        "person:ana-veche",
        "company:99000090",
    }
    roles = {(e.source, e.role) for e in graph.edges}
    assert roles == {
        ("person:sorin-imaginescu", "administrator"),
        ("person:ana-veche", "former_administrator"),
        ("company:99000090", "shareholder"),
    }
    assert all(e.target == f"company:{CUI}" for e in graph.edges)


async def test_live_sse_closes_when_the_run_already_ended() -> None:
    infra = build_infra(Settings(_env_file=None, fixture_mode=False))
    await infra.repository.save_run(RunStatus(run_id="run_x", cui=CUI, state=RunState.REJECTED))

    async def nothing_queued(*_: object, **__: object) -> None:
        return None

    infra.queue.dequeue = nothing_queued  # type: ignore[method-assign]
    events = [chunk async for chunk in _live_events(infra, "run_x")]
    assert len(events) == 1 and '"done":true' in events[0]
    await infra.aclose()


# ---------------------------------------------------------------------- time travel
def checkpoint(month: int) -> datetime:
    return datetime(2026, month, 15, 9, 0, tzinfo=UTC)


async def seeded_history() -> RepoReadModel:
    """Brunaldo checked in January (green), June (yellow) and September (red). Each run knows
    one more fact, dated the 1st of its month."""
    repo = MemoryRepository()
    await repo.save_identity_sheet("run_1", identity())
    facts: list[Signal] = []
    for n, (month, band) in enumerate(((1, Band.GREEN), (6, Band.YELLOW), (9, Band.RED)), start=1):
        facts.append(
            sig(f"TAX-ARREARS-01:{month}", Severity.HIGH).model_copy(
                update={"evidence_date": date(2026, month, 1)}
            )
        )
        await repo.save_agent_result(
            f"run_{n}",
            AgentResult(
                agent="tax",
                component=Component.TAX,
                status=AgentStatus.OK,
                sources_checked=["anaf"],
                sources_failed=[],
                signals=list(facts),
                duration_ms=1,
            ),
        )
        await repo.save_score(
            score().model_copy(
                update={"run_id": f"run_{n}", "band": band, "computed_at": checkpoint(month)}
            )
        )
    return RepoReadModel(repo)


async def test_list_as_of_shows_the_band_known_that_day() -> None:
    rm = await seeded_history()
    before = await rm.list_companies(
        band=None, q=None, page=1, page_size=10, as_of=date(2026, 1, 1)
    )
    assert before.items == [] and before.total == 0
    march = await rm.list_companies(band=None, q=None, page=1, page_size=10, as_of=date(2026, 3, 1))
    assert [(i.band, i.last_checked) for i in march.items] == [(Band.GREEN, checkpoint(1))]
    july = await rm.list_companies(
        band=Band.YELLOW, q=None, page=1, page_size=10, as_of=date(2026, 7, 1)
    )
    assert july.total == 1
    assert (await rm.list_companies(band=None, q=None, page=1, page_size=10)).items[
        0
    ].band == Band.RED


async def test_as_of_is_inclusive_of_the_whole_day() -> None:
    rm = await seeded_history()
    detail = await rm.detail(CUI, as_of=date(2026, 6, 15))  # checked at 09:00 that day
    assert detail.band == Band.YELLOW


async def test_detail_and_signals_as_of() -> None:
    rm = await seeded_history()
    assert len(await rm.signals(CUI, as_of=date(2026, 7, 1))) == 2
    assert len(await rm.signals(CUI)) == 3
    with pytest.raises(HTTPException) as err:
        await rm.detail(CUI, as_of=date(2025, 12, 31))
    assert err.value.status_code == 404


async def test_history_between_two_dates() -> None:
    rm = await seeded_history()
    history = await rm.history(CUI, date(2026, 2, 1), date(2026, 9, 30))
    assert [(p.run_id, p.band) for p in history.scores] == [
        ("run_2", Band.YELLOW),
        ("run_3", Band.RED),
    ]
    assert [e.evidence_date for e in history.events] == [date(2026, 6, 1), date(2026, 9, 1)]
    whole = await rm.history(CUI, None, None)
    assert len(whole.scores) == 3 and len(whole.events) == 3


async def test_list_loads_companies_concurrently_and_keeps_the_page_order() -> None:
    """One database round trip per call: loaded one after another, a page took ~13 s on Neon."""
    import asyncio
    import time

    class SlowRepo(MemoryRepository):
        async def get_identity_sheet(self, cui: str) -> IdentitySheet | None:
            await asyncio.sleep(0.05)
            return await super().get_identity_sheet(cui)

        async def get_latest_score(self, cui: str) -> Score | None:
            await asyncio.sleep(0.05)
            return await super().get_latest_score(cui)

        async def list_signals(self, cui: str) -> list[Signal]:
            await asyncio.sleep(0.05)
            return await super().list_signals(cui)

    repo = SlowRepo()
    cuis = [f"9900{i:04d}" for i in range(8)]
    for cui in cuis:
        await repo.save_identity_sheet("r", identity().model_copy(update={"cui": cui}))
        await repo.save_run(
            RunStatus(run_id=f"run-{cui}", cui=cui, state=RunState.COMPLETED, started_at=NOW)
        )
    started = time.perf_counter()
    page = await RepoReadModel(repo).list_companies(band=None, q=None, page=1, page_size=50)
    elapsed = time.perf_counter() - started

    expected, _ = await repo.list_portfolio(band=None, q=None, page=1, page_size=50)
    assert [i.cui for i in page.items] == expected  # the repository's page order, unchanged
    assert len(page.items) == len(cuis)
    assert elapsed < 0.05 * 3 * len(cuis) / 2  # well below one-after-another (1.2 s)
