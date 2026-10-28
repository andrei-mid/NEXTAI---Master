"""Company read routes + recheck.

FIXTURE_MODE serves the API-shaped fixtures (contract-first). Otherwise the routes read what the
pipeline persisted, through the Repository (apps/api/read_model.py).

Time travel (docs/DECISIONS.md, "Time-travel reads"): `as_of=YYYY-MM-DD` on the list, the detail
and the signals returns what the bank knew at the end of that day. `GET /{cui}/history?from=&to=`
returns the checks, the events (by evidence_date) and the decisions of a period.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from apps.api.deps import _store, get_infra, valid_cui
from apps.api.read_model import RepoReadModel, end_of
from apps.api.routes.runs import enqueue_run
from apps.wiring import Infra
from verifirm.schema.api import (
    CompanyDetail,
    CompanyHistory,
    CompanyList,
    CompanyListItem,
    Graph,
    MemoResponse,
    RunCreated,
    ScorePoint,
)
from verifirm.schema.runs import RunTrigger
from verifirm.schema.scoring import Band
from verifirm.schema.signals import Signal

router = APIRouter(prefix="/companies", tags=["companies"])

AS_OF = Query(None, description="YYYY-MM-DD: what the bank knew at the end of that day (UTC)")


def _checked_by(item: dict[str, Any], as_of: date) -> bool:
    """Fixture mode: a company counts at `as_of` only if its (single) check happened by then."""
    last = item.get("last_checked")
    return last is not None and datetime.fromisoformat(last) <= end_of(as_of)


def _fixture_company(infra: Infra, cui: str, as_of: date | None) -> dict[str, Any]:
    company: dict[str, Any] = _store(infra.settings.fixtures_dir).read(cui, "company.json")
    if as_of is not None and not _checked_by(company, as_of):
        raise HTTPException(status_code=404, detail=f"company {cui} not checked by {as_of}")
    return company


@router.get("", response_model=CompanyList)
async def list_companies(
    band: Band | None = None,
    q: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    as_of: date | None = AS_OF,
    infra: Infra = Depends(get_infra),
) -> CompanyList:
    if not infra.settings.fixture_mode:
        return await RepoReadModel(infra.repository).list_companies(
            band=band, q=q, page=page, page_size=page_size, as_of=as_of
        )
    raw = _store(infra.settings.fixtures_dir).list_items()
    if as_of is not None:
        raw = [i for i in raw if _checked_by(i, as_of)]
    items = [CompanyListItem.model_validate(i) for i in raw]
    if band is not None:
        items = [i for i in items if i.band == band]
    if q:
        needle = q.lower()
        items = [i for i in items if needle in i.name.lower() or needle in i.cui]
    start = (page - 1) * page_size
    return CompanyList(
        items=items[start : start + page_size], page=page, page_size=page_size, total=len(items)
    )


@router.get("/{cui}", response_model=CompanyDetail)
async def get_company(
    cui: str = Depends(valid_cui), as_of: date | None = AS_OF, infra: Infra = Depends(get_infra)
) -> CompanyDetail:
    if not infra.settings.fixture_mode:
        return await RepoReadModel(infra.repository).detail(cui, as_of)
    return CompanyDetail.model_validate(_fixture_company(infra, cui, as_of))


@router.get("/{cui}/signals", response_model=list[Signal])
async def get_signals(
    cui: str = Depends(valid_cui), as_of: date | None = AS_OF, infra: Infra = Depends(get_infra)
) -> list[Signal]:
    if not infra.settings.fixture_mode:
        return await RepoReadModel(infra.repository).signals(cui, as_of)
    _fixture_company(infra, cui, as_of)
    raw = _store(infra.settings.fixtures_dir).read(cui, "signals.json")
    return [Signal.model_validate(s) for s in raw]


@router.get("/{cui}/history", response_model=CompanyHistory)
async def get_history(
    cui: str = Depends(valid_cui),
    date_from: date | None = Query(None, alias="from", description="YYYY-MM-DD, inclusive"),
    date_to: date | None = Query(None, alias="to", description="YYYY-MM-DD, inclusive"),
    infra: Infra = Depends(get_infra),
) -> CompanyHistory:
    """Checks (scores) and analyst decisions made in the period, plus what happened to the
    company in the period (signals by evidence_date). Both bounds optional."""
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=422, detail="`from` is after `to`")
    if not infra.settings.fixture_mode:
        return await RepoReadModel(infra.repository).history(cui, date_from, date_to)
    store = _store(infra.settings.fixtures_dir)
    company = store.read(cui, "company.json")
    scores = []
    checked = company.get("last_checked")
    if checked and company.get("band") and company.get("coverage"):
        at = datetime.fromisoformat(checked)
        if (date_from is None or at.date() >= date_from) and (
            date_to is None or at.date() <= date_to
        ):
            scores.append(
                ScorePoint(
                    run_id=f"fixture-{cui}",
                    computed_at=at,
                    band=company["band"],
                    score=company.get("score"),
                    coverage=company["coverage"],
                )
            )
    events = [
        e
        for e in (Signal.model_validate(s) for s in store.read(cui, "signals.json"))
        if e.evidence_date is not None
        and (date_from is None or e.evidence_date >= date_from)
        and (date_to is None or e.evidence_date <= date_to)
    ]
    return CompanyHistory(
        cui=cui,
        date_from=date_from,
        date_to=date_to,
        scores=scores,
        events=sorted(events, key=lambda e: (e.evidence_date or date.min, e.signal_id)),
        decisions=[],
    )


@router.get("/{cui}/memo", response_model=MemoResponse)
async def get_memo(
    cui: str = Depends(valid_cui), infra: Infra = Depends(get_infra)
) -> MemoResponse:
    if not infra.settings.fixture_mode:
        return await RepoReadModel(infra.repository).memo(cui)
    return MemoResponse.model_validate(_store(infra.settings.fixtures_dir).read(cui, "memo.json"))


@router.get("/{cui}/graph", response_model=Graph)
async def get_graph(
    cui: str = Depends(valid_cui),
    depth: int = Query(2, ge=1, le=3),
    infra: Infra = Depends(get_infra),
) -> Graph:
    if not infra.settings.fixture_mode:
        return await RepoReadModel(infra.repository).graph(cui, depth)
    # Fixture graphs are stored at depth 2.
    return Graph.model_validate(_store(infra.settings.fixtures_dir).read(cui, "graph.json"))


@router.post("/{cui}/recheck", response_model=RunCreated, status_code=202)
async def recheck(cui: str = Depends(valid_cui), infra: Infra = Depends(get_infra)) -> RunCreated:
    return await enqueue_run(infra, cui=cui, trigger=RunTrigger.RECHECK)
