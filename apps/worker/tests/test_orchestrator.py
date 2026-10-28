import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from apps.wiring import build_infra
from apps.worker import orchestrator
from apps.worker.orchestrator import run_pipeline
from verifirm.core.config import Settings
from verifirm.schema.identity import IdentitySheet
from verifirm.schema.runs import AgentProgressEvent, RunRequest, RunState, RunTrigger

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"


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


def _fixture_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    """Identity sheet from the fixtures, so the test doesn't depend on consolidation's status."""

    async def from_fixture(cui: str, adapters: object, clock: object) -> IdentitySheet:
        folder = next((FIXTURES / "companies").glob(f"{cui}_*"))
        data = json.loads((folder / "api" / "company.json").read_text(encoding="utf-8"))
        return IdentitySheet.model_validate(data["identity_sheet"])

    monkeypatch.setattr(orchestrator, "build_identity_sheet", from_fixture)


async def test_memo_failure_keeps_the_score(monkeypatch: pytest.MonkeyPatch) -> None:
    """The fake LLM has no canned memo, like a real LLM that is down: the run must still
    complete with its deterministic score saved, and the SSE stream must get `done`."""
    _fixture_identity(monkeypatch)
    events: list[AgentProgressEvent] = []

    async def publish(e: AgentProgressEvent) -> None:
        events.append(e)

    infra = build_infra(Settings(fixture_mode=True, llm_provider="fake"))
    status = await run_pipeline(_request("99000025"), infra, publish)
    score = await infra.repository.get_latest_score("99000025")
    await infra.aclose()
    assert status.state == RunState.COMPLETED and status.band is not None
    assert status.error and status.error.startswith("memo not generated")
    assert score is not None and score.run_id == "t-99000025"
    assert events[-1].done


async def test_unexpected_crash_fails_the_run_instead_of_hanging(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fixture_identity(monkeypatch)

    def boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("scoring exploded")

    monkeypatch.setattr(orchestrator, "score", boom)
    infra = build_infra(Settings(fixture_mode=True, llm_provider="fake"))
    status = await run_pipeline(_request("99000025"), infra)
    await infra.aclose()
    assert status.state == RunState.FAILED and "scoring exploded" in (status.error or "")
