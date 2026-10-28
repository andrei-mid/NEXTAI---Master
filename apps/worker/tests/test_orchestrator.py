from datetime import UTC, datetime

from apps.wiring import build_infra
from apps.worker.orchestrator import run_pipeline
from verifirm.core.config import Settings
from verifirm.schema.runs import AgentProgressEvent, RunRequest, RunState, RunTrigger


def _request(cui: str) -> RunRequest:
    return RunRequest(
        run_id=f"t-{cui}", cui=cui, trigger=RunTrigger.APPLICATION, requested_at=datetime.now(UTC)
    )


async def test_invalid_cui_is_rejected_at_the_gate() -> None:
    infra = build_infra(Settings(fixture_mode=False, llm_provider="fake"))
    status = await run_pipeline(_request("99000025"), infra)  # fictional CUI outside fixture mode
    await infra.aclose()
    assert status.state == RunState.REJECTED


async def test_pipeline_never_reports_unfinished_work_as_clean() -> None:
    events: list[AgentProgressEvent] = []

    async def publish(e: AgentProgressEvent) -> None:
        events.append(e)

    infra = build_infra(Settings(fixture_mode=True, llm_provider="fake"))
    status = await run_pipeline(_request("99000025"), infra, publish)
    await infra.aclose()
    assert status.state in {RunState.FAILED, RunState.COMPLETED}
    if status.state == RunState.FAILED:
        assert status.error and status.band is None
    assert events and events[-1].done
