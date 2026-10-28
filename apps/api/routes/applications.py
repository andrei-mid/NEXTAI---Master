"""POST /applications: CUI + submitted documents -> run_id (the pipeline runs in the worker)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from apps.api.deps import get_infra
from apps.api.routes.runs import enqueue_run
from apps.wiring import Infra
from verifirm.core.cui import InvalidCUIError, validate_cui
from verifirm.schema.api import RunCreated
from verifirm.schema.runs import RunTrigger

router = APIRouter(tags=["applications"])

MAX_FILE_BYTES = 25 * 1024 * 1024


@router.post("/applications", response_model=RunCreated, status_code=202)
async def create_application(
    cui: str = Form(...),
    files: list[UploadFile] | None = File(None),
    infra: Infra = Depends(get_infra),
) -> RunCreated:
    try:
        cui = validate_cui(cui, fixture_mode=infra.settings.fixture_mode)
    except InvalidCUIError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    keys = []
    for f in files or []:
        data = await f.read()
        if len(data) > MAX_FILE_BYTES:
            raise HTTPException(status_code=413, detail=f"{f.filename} is larger than 25 MB")
        keys.append(await infra.object_store.put(data, prefix=f"submitted/{cui}"))
    return await enqueue_run(infra, cui=cui, trigger=RunTrigger.APPLICATION, document_keys=keys)
