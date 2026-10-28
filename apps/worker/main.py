"""Worker process: consume RunRequests from the queue and run the pipeline. Stateless: run N of them.

Run: `make run-worker` (python -m apps.worker.main). Owner: @role-2-core.
"""

from __future__ import annotations

import asyncio

from apps.wiring import RUNS_TOPIC, Infra, build_infra, run_events_topic
from apps.worker.orchestrator import run_pipeline
from verifirm.core.config import get_settings
from verifirm.core.logging import configure_logging, get_logger
from verifirm.schema.runs import AgentProgressEvent, RunRequest

log = get_logger(__name__)
MAX_ATTEMPTS = 3


async def consume_forever(infra: Infra) -> None:
    while True:
        msg = await infra.queue.dequeue(RUNS_TOPIC, wait_s=5)
        if msg is None:
            continue
        request = RunRequest.model_validate(msg.body)

        async def publish(event: AgentProgressEvent, run_id: str = request.run_id) -> None:
            await infra.queue.enqueue(run_events_topic(run_id), event.model_dump(mode="json"))

        try:
            await run_pipeline(request, infra, publish)
        except Exception:
            log.exception("run crashed", extra={"run_id": request.run_id})
            await infra.queue.nack(msg, retry=msg.attempts < MAX_ATTEMPTS)
        else:
            await infra.queue.ack(msg)


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_json)
    infra = build_infra(settings)
    log.info(
        "worker started",
        extra={"queue": settings.queue_backend, "fixture_mode": settings.fixture_mode},
    )
    try:
        await consume_forever(infra)
    finally:
        await infra.aclose()


if __name__ == "__main__":
    asyncio.run(main())
