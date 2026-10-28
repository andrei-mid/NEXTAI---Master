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


async def test_missing_llm_key_still_runs_the_agents(monkeypatch: pytest.MonkeyPatch) -> None:
    """LLM_PROVIDER=anthropic without ANTHROPIC_API_KEY: agents and score still run."""
    _fixture_identity(monkeypatch)
    infra = build_infra(
        Settings(fixture_mode=True, llm_provider="anthropic", anthropic_api_key=None)
    )
    status = await run_pipeline(_request("99000025"), infra)
    results = await infra.repository.list_agent_results("t-99000025")
    await infra.aclose()
    assert status.state == RunState.COMPLETED and status.band is not None
    assert (status.error or "").startswith("memo not generated")
    assert {r.agent for r in results if r.status.value == "ok"} >= {"financials"}


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


# ---------------------------------------------------------------------- AI analyst step
ZEPHYRIA_DRAFT = {
    "flags": [
        {
            "title": "Negative equity on a growing turnover",
            "claim": "Equity was -111000 RON in 2025 while turnover was 18600000 RON.",
            "category": "financial_inconsistency",
            "severity": "high",
            "evidence": [
                {"path": "financials.2025.equity", "value": "-111000"},
                {"path": "financials.2025.turnover", "value": "18600000"},
            ],
        }
    ],
    "opinion_score": 30,
    "explanation": "Turnover of 18600000 RON in 2025 sits on negative equity.",
}


async def test_analyst_opinion_is_saved_next_to_the_unchanged_score(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from verifirm.core.impl_local.llm import FakeLLMClient

    _fixture_identity(monkeypatch)
    events: list[AgentProgressEvent] = []

    async def publish(e: AgentProgressEvent) -> None:
        events.append(e)

    infra = build_infra(Settings(fixture_mode=True, llm_provider="fake"))
    infra.llm = FakeLLMClient(json_responses={"AnalystDraft": ZEPHYRIA_DRAFT})
    status = await run_pipeline(_request("99000025"), infra, publish)
    score = await infra.repository.get_latest_score("99000025")
    opinion = await infra.repository.get_latest_analyst_opinion("99000025")
    await infra.aclose()
    assert status.state == RunState.COMPLETED and score is not None and opinion is not None
    assert [f.title for f in opinion.flags] == ["Negative equity on a growing turnover"]
    assert opinion.official_band == score.band == status.band  # the opinion changes nothing
    assert opinion.opinion_score == 30 and opinion.run_id == "t-99000025"
    assert "analyst" in {e.agent for e in events}
    # No canned memo: the memo fails on its own, the analyst still ran.
    assert (status.error or "").startswith("memo not generated")
    assert "analyst" not in (status.error or "")


async def test_analyst_failure_keeps_the_score(monkeypatch: pytest.MonkeyPatch) -> None:
    _fixture_identity(monkeypatch)
    infra = build_infra(Settings(fixture_mode=True, llm_provider="fake"))
    status = await run_pipeline(_request("99000025"), infra)
    score = await infra.repository.get_latest_score("99000025")
    opinion = await infra.repository.get_latest_analyst_opinion("99000025")
    await infra.aclose()
    assert status.state == RunState.COMPLETED and score is not None and opinion is None
    assert "analyst opinion not generated" in (status.error or "")


async def test_analyst_can_be_switched_off(monkeypatch: pytest.MonkeyPatch) -> None:
    _fixture_identity(monkeypatch)
    infra = build_infra(Settings(fixture_mode=True, llm_provider="fake", analyst_enabled=False))
    status = await run_pipeline(_request("99000025"), infra)
    opinion = await infra.repository.get_latest_analyst_opinion("99000025")
    await infra.aclose()
    assert opinion is None and "analyst" not in (status.error or "")
