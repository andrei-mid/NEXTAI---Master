"""Server-Sent Events helpers (no extra dependency: StreamingResponse + text/event-stream)."""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi.responses import StreamingResponse
from pydantic import BaseModel


def format_event(data: BaseModel, *, event: str = "progress", event_id: str | None = None) -> str:
    lines = [f"event: {event}"]
    if event_id is not None:
        lines.append(f"id: {event_id}")
    lines.append(f"data: {data.model_dump_json()}")
    return "\n".join(lines) + "\n\n"


def sse_response(stream: AsyncIterator[str]) -> StreamingResponse:
    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
