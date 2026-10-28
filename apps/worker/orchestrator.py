"""Pipeline flow. The skeleton is real: each step calls its owner's (possibly stub) function.

    CUI gate -> identity sheet -> submitted docs -> 8 agents in parallel (time budget)
    -> entity resolution -> scoring (no LLM) -> memo -> critic -> persist

Agents are DISCOVERED (registry). Adding an agent never edits this file.
A step that is not implemented yet ends the run as FAILED with a clear error, never as clean.
Owner: @role-2-core.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from functools import partial

from apps.wiring import Infra
from apps.worker.sync import sync_company
from verifirm.adapters.base import SourceUnavailable
from verifirm.agents.base import AgentContext, BaseAgent
from verifirm.consolidation.critic.agent import verify_memo
from verifirm.consolidation.entity_resolution import resolve
from verifirm.consolidation.identity_sheet import build_identity_sheet
from verifirm.consolidation.memo.agent import write_memo
from verifirm.core.cui import InvalidCUIError, validate_cui
from verifirm.core.logging import get_logger, log_context
from verifirm.core.registry import discover_agents
from verifirm.core.timebudget import BudgetedTask, run_all
from verifirm.schema.memo import ConsolidatedReport
from verifirm.schema.runs import AgentProgressEvent, RunRequest, RunState, RunStatus, RunTrigger
from verifirm.schema.signals import AgentResult
from verifirm.scoring.engine import load_scoring_config, score

log = get_logger(__name__)

Publish = Callable[[AgentProgressEvent], Awaitable[None]]


async def _noop(_: AgentProgressEvent) -> None:
    return None


def select_agents(request: RunRequest) -> dict[str, type[BaseAgent]]:
    agents: dict[str, type[BaseAgent]] = discover_agents()
    if request.agents is not None:
        agents = {name: cls for name, cls in agents.items() if name in request.agents}
    return agents


async def run_pipeline(request: RunRequest, infra: Infra, publish: Publish = _noop) -> RunStatus:
    repo, clock, settings = infra.repository, infra.clock, infra.settings
    status = RunStatus(
        run_id=request.run_id, cui=request.cui, state=RunState.RUNNING, started_at=clock.now()
    )

    async def finish(state: RunState, **extra: object) -> RunStatus:
        final = status.model_copy(update={"state": state, "finished_at": clock.now(), **extra})
        await repo.save_run(final)
        await publish(AgentProgressEvent(run_id=request.run_id, agent="pipeline", done=True))
        return final

    with log_context(run_id=request.run_id, cui=request.cui):
        # 1. CUI gate
        try:
            cui = validate_cui(request.cui, fixture_mode=settings.fixture_mode)
        except InvalidCUIError as exc:
            return await finish(RunState.REJECTED, error=str(exc))
        await repo.save_run(status)

        # 1b. Local-first: download this company's data into the mirror ONCE, before any agent
        # runs. Agents never call external APIs (docs/LOCAL_DATA.md). Sweep runs skip this:
        # the portfolio is kept fresh by apps/worker/jobs/sync_portfolio.py.
        if settings.sync_on_application and request.trigger != RunTrigger.SWEEP:
            await sync_company(cui, infra, skip=request.disabled_sources)
            await publish(AgentProgressEvent(run_id=request.run_id, agent="sync"))

        try:
            # 2. Identity sheet (official sources only)
            identity = await build_identity_sheet(cui, infra.adapters, clock)
            await repo.save_identity_sheet(request.run_id, identity)
            await publish(AgentProgressEvent(run_id=request.run_id, agent="identity_sheet"))

            # 3. Submitted documents (applications only)
            submitted = None
            if request.document_keys:
                documents = infra.adapters["documents"]
                extracted = await documents.extract(cui, request.document_keys)  # type: ignore[attr-defined]
                submitted = extracted.data
                if submitted is not None:
                    await repo.save_submitted_financials(request.run_id, submitted)

            # 4. Agents in parallel, each under its own time budget
            ctx = AgentContext(
                run_id=request.run_id,
                cui=cui,
                identity=identity,
                settings=settings,
                clock=clock,
                adapters=infra.adapters,
                llm=infra.llm,
                web_search=infra.web_search,
                submitted=submitted,
                disabled_sources=frozenset(request.disabled_sources),
            )

            async def on_done(result: AgentResult) -> None:
                await repo.save_agent_result(request.run_id, result)
                await publish(
                    AgentProgressEvent(
                        run_id=request.run_id,
                        agent=result.agent,
                        status=result.status,
                        n_signals=len(result.signals),
                        elapsed_ms=result.duration_ms,
                    )
                )

            tasks = [
                BudgetedTask(
                    agent=name,
                    component=cls.component,
                    run=partial(cls().run, ctx),
                    timeout_s=cls.timeout_s or settings.timeout_for(name),
                )
                for name, cls in select_agents(request).items()
            ]
            results = await run_all(tasks, on_done=on_done)

            # 5. Entity resolution
            resolved = resolve(identity, results)
            for result in resolved:
                await repo.save_agent_result(request.run_id, result)

            # 6. Deterministic scoring (no LLM)
            config = load_scoring_config(settings.scoring_config_path)
            run_score = score(
                cui=cui,
                run_id=request.run_id,
                identity=identity,
                results=resolved,
                config=config,
                now=clock.now(),
            )
            await repo.save_score(run_score)
            await publish(AgentProgressEvent(run_id=request.run_id, agent="scoring"))

            # 7. Memo (only from the consolidated JSON) + 8. critic
            report = ConsolidatedReport(
                cui=cui,
                run_id=request.run_id,
                identity=identity,
                results=resolved,
                signals=[s for r in resolved for s in r.signals],
                score=run_score,
                generated_at=clock.now(),
            )
            # The score is deterministic and already saved: a memo failure (LLM down, invalid
            # output, no API key) must not throw it away. The run completes without a memo.
            try:
                memo = await write_memo(report, infra.llm, settings.model_for("memo"))
                await publish(AgentProgressEvent(run_id=request.run_id, agent="memo"))
                memo = await verify_memo(memo, report, infra.llm, settings.model_for("critic"))
                await repo.save_memo(memo)
                await publish(AgentProgressEvent(run_id=request.run_id, agent="critic"))
            except NotImplementedError:
                raise
            except Exception as exc:
                log.warning("memo step failed, run completes without a memo", exc_info=True)
                return await finish(
                    RunState.COMPLETED,
                    band=run_score.band,
                    error=f"memo not generated: {type(exc).__name__}: {exc}"[:500],
                )
        except NotImplementedError:
            log.warning("pipeline step not implemented yet", exc_info=True)
            return await finish(RunState.FAILED, error="a pipeline step is not implemented yet")
        except SourceUnavailable as exc:
            return await finish(RunState.FAILED, error=f"required source unavailable: {exc}")
        except Exception as exc:  # never leave a run hanging: the SSE stream needs its `done`
            log.exception("pipeline step crashed")
            return await finish(RunState.FAILED, error=f"{type(exc).__name__}: {exc}"[:500])

        return await finish(RunState.COMPLETED, band=run_score.band)
