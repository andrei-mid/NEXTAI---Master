import asyncio

from verifirm.core.timebudget import BudgetedTask, run_all, run_with_budget
from verifirm.schema.signals import AgentResult, AgentStatus, Component


def _ok(sources_failed: list[str] | None = None) -> AgentResult:
    return AgentResult(
        agent="x",
        component=Component.IDENTITY,
        status=AgentStatus.OK,
        sources_checked=["a"],
        sources_failed=sources_failed or [],
        signals=[],
        duration_ms=1,
    )


async def test_timeout_is_reported_not_clean() -> None:
    async def slow() -> AgentResult:
        await asyncio.sleep(5)
        return _ok()

    result = await run_with_budget(BudgetedTask("x", Component.IDENTITY, slow, timeout_s=0.05))
    assert result.status == AgentStatus.TIMEOUT
    assert result.sources_failed


async def test_crash_is_unavailable() -> None:
    async def boom() -> AgentResult:
        raise RuntimeError("source down")

    result = await run_with_budget(BudgetedTask("x", Component.TAX, boom, timeout_s=1))
    assert result.status == AgentStatus.UNAVAILABLE
    assert "source down" in (result.notes or "")


async def test_ok_with_failed_source_is_downgraded_to_partial() -> None:
    async def partial() -> AgentResult:
        return _ok(sources_failed=["anaf_bilant"])

    result = await run_with_budget(BudgetedTask("x", Component.FINANCIALS, partial, timeout_s=1))
    assert result.status == AgentStatus.PARTIAL


async def test_run_all_is_parallel_and_reports_progress() -> None:
    seen: list[str] = []

    async def fast() -> AgentResult:
        await asyncio.sleep(0.05)
        return _ok()

    async def on_done(r: AgentResult) -> None:
        seen.append(r.agent)

    tasks = [BudgetedTask(f"a{i}", Component.MEDIA, fast, timeout_s=1) for i in range(8)]
    loop = asyncio.get_running_loop()
    start = loop.time()
    results = await run_all(tasks, on_done=on_done)
    assert len(results) == 8 and len(seen) == 8
    assert loop.time() - start < 0.3  # 8 x 50 ms in parallel, not in series
