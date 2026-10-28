"""Runs: enqueue helper + GET /runs/{run_id}/events (SSE progress per agent).

FIXTURE_MODE replays fixtures/companies/<cui>_<slug>/api/run_events.json with a small delay
(FIXTURE_SSE_DELAY_S), so the frontend can build the live-progress view before the worker exists.
Live mode streams AgentProgressEvent messages that the worker publishes on the
`run-events:<run_id>` queue topic.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from apps.api.deps import FixtureStore, _store, get_infra
from apps.api.sse import format_event, sse_response
from apps.wiring import RUNS_TOPIC, Infra, run_events_topic
from verifirm.schema.api import RunCreated
from verifirm.schema.runs import AgentProgressEvent, RunRequest, RunState, RunStatus, RunTrigger

router = APIRouter(prefix="/runs", tags=["runs"])


async def enqueue_run(
    infra: Infra, *, cui: str, trigger: RunTrigger, document_keys: list[str] | None = None
) -> RunCreated:
    now = infra.clock.now()
    request = RunRequest(
        run_id=f"run_{uuid.uuid4().hex}",
        cui=cui,
        trigger=trigger,
        document_keys=document_keys or [],
        requested_at=now,
    )
    await infra.repository.save_run(
        RunStatus(run_id=request.run_id, cui=cui, state=RunState.QUEUED)
    )
    await infra.queue.enqueue(
        RUNS_TOPIC, request.model_dump(mode="json"), dedupe_key=request.run_id
    )
    return RunCreated(run_id=request.run_id)


async def _fixture_events(
    store: FixtureStore, run_id: str, cui: str, delay_s: float
) -> AsyncIterator[str]:
    for i, raw in enumerate(store.read(cui, "run_events.json")):
        await asyncio.sleep(delay_s)
        event = AgentProgressEvent.model_validate({**raw, "run_id": run_id})
        yield format_event(event, event_id=str(i))


async def _live_events(infra: Infra, run_id: str) -> AsyncIterator[str]:
    i = 0
    while True:
        msg = await infra.queue.dequeue(run_events_topic(run_id), wait_s=15)
        if msg is None:
            yield ": keep-alive\n\n"
            continue
        await infra.queue.ack(msg)
        event = AgentProgressEvent.model_validate(msg.body)
        yield format_event(event, event_id=str(i))
        i += 1
        if event.done:
            return


@router.get("/{run_id}/events")
async def run_events(run_id: str, infra: Infra = Depends(get_infra)) -> StreamingResponse:
    run = await infra.repository.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="unknown run_id")
    if infra.settings.fixture_mode:
        store = _store(infra.settings.fixtures_dir)
        return sse_response(
            _fixture_events(store, run_id, run.cui, infra.settings.fixture_sse_delay_s)
        )
    return sse_response(_live_events(infra, run_id))
