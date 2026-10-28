"""Company read routes + recheck.

FIXTURE_MODE serves the API-shaped fixtures (contract-first). Otherwise the routes read what the
pipeline persisted, through the Repository (apps/api/read_model.py).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from apps.api.deps import _store, get_infra, valid_cui
from apps.api.read_model import RepoReadModel
from apps.api.routes.runs import enqueue_run
from apps.wiring import Infra
from verifirm.schema.api import (
    CompanyDetail,
    CompanyList,
    CompanyListItem,
    Graph,
    MemoResponse,
    RunCreated,
)
from verifirm.schema.runs import RunTrigger
from verifirm.schema.scoring import Band
from verifirm.schema.signals import Signal

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("", response_model=CompanyList)
async def list_companies(
    band: Band | None = None,
    q: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    infra: Infra = Depends(get_infra),
) -> CompanyList:
    if not infra.settings.fixture_mode:
        return await RepoReadModel(infra.repository).list_companies(
            band=band, q=q, page=page, page_size=page_size
        )
    items = [
        CompanyListItem.model_validate(i) for i in _store(infra.settings.fixtures_dir).list_items()
    ]
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
async def get_company(cui: str = Depends(valid_cui), infra: Infra = Depends(get_infra)) -> CompanyDetail:
    if not infra.settings.fixture_mode:
        return await RepoReadModel(infra.repository).detail(cui)
    return CompanyDetail.model_validate(_store(infra.settings.fixtures_dir).read(cui, "company.json"))


@router.get("/{cui}/signals", response_model=list[Signal])
async def get_signals(cui: str = Depends(valid_cui), infra: Infra = Depends(get_infra)) -> list[Signal]:
    if not infra.settings.fixture_mode:
        return await RepoReadModel(infra.repository).signals(cui)
    raw = _store(infra.settings.fixtures_dir).read(cui, "signals.json")
    return [Signal.model_validate(s) for s in raw]


@router.get("/{cui}/memo", response_model=MemoResponse)
async def get_memo(cui: str = Depends(valid_cui), infra: Infra = Depends(get_infra)) -> MemoResponse:
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
