"""Run agent coroutines under a per-agent time budget.

A timeout is reported as AgentStatus.TIMEOUT, an unhandled error as UNAVAILABLE.
Neither is ever reported as clean (OK with zero signals).
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass

from verifirm.core.logging import get_logger, log_context
from verifirm.schema.signals import AgentResult, AgentStatus, Component

log = get_logger(__name__)


@dataclass(frozen=True)
class BudgetedTask:
    agent: str
    component: Component
    run: Callable[[], Awaitable[AgentResult]]
    timeout_s: float


def _failed(task: BudgetedTask, status: AgentStatus, started: float, notes: str) -> AgentResult:
    return AgentResult(
        agent=task.agent,
        component=task.component,
        status=status,
        sources_checked=[],
        sources_failed=["*"],
        signals=[],
        duration_ms=int((time.monotonic() - started) * 1000),
        notes=notes,
    )


async def run_with_budget(task: BudgetedTask) -> AgentResult:
    started = time.monotonic()
    with log_context(agent=task.agent):
        try:
            result = await asyncio.wait_for(task.run(), timeout=task.timeout_s)
        except TimeoutError:
            log.warning("agent timed out", extra={"timeout_s": task.timeout_s})
            return _failed(task, AgentStatus.TIMEOUT, started, f"exceeded {task.timeout_s}s budget")
        except NotImplementedError:
            return _failed(task, AgentStatus.UNAVAILABLE, started, "not implemented yet")
        except Exception as exc:  # an agent crash must never take the run down
            log.exception("agent failed")
            return _failed(task, AgentStatus.UNAVAILABLE, started, f"{type(exc).__name__}: {exc}")
    if result.status == AgentStatus.OK and result.sources_failed:
        # A failed source can never be reported as clean.
        result = result.model_copy(update={"status": AgentStatus.PARTIAL})
    return result


async def run_all(
    tasks: Sequence[BudgetedTask],
    on_done: Callable[[AgentResult], Awaitable[None]] | None = None,
) -> list[AgentResult]:
    """Run all tasks in parallel; `on_done` is awaited as each finishes (for SSE progress)."""

    async def one(task: BudgetedTask) -> AgentResult:
        result = await run_with_budget(task)
        if on_done is not None:
            await on_done(result)
        return result

    return list(await asyncio.gather(*(one(t) for t in tasks)))
