"""Queries for the `runs_*` tables (see models/runs.py). Owner: @role-1-database."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from verifirm.persistence.models.runs import AgentResultRow, Run
from verifirm.schema.runs import RunRequest, RunState, RunStatus
from verifirm.schema.signals import AgentResult, Signal


class RunsStore:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save_run(self, status: RunStatus) -> None:
        values = {
            "cui": status.cui,
            "state": status.state.value,
            "started_at": status.started_at,
            "finished_at": status.finished_at,
            "band": status.band.value if status.band else None,
            "error": status.error,
        }
        stmt = insert(Run).values(run_id=status.run_id, **values)
        stmt = stmt.on_conflict_do_update(index_elements=[Run.run_id], set_=values)
        await self.session.execute(stmt)

    async def save_request(self, request: RunRequest) -> None:
        """Record what was asked (trigger, documents, disabled sources) without touching state."""
        values = {
            "trigger": request.trigger.value,
            "requested_at": request.requested_at,
            "request": request.model_dump(mode="json"),
        }
        stmt = insert(Run).values(
            run_id=request.run_id, cui=request.cui, state=RunState.QUEUED.value, **values
        )
        stmt = stmt.on_conflict_do_update(index_elements=[Run.run_id], set_=values)
        await self.session.execute(stmt)

    async def get_run(self, run_id: str) -> RunStatus | None:
        row = await self.session.get(Run, run_id)
        if row is None:
            return None
        return RunStatus.model_validate(
            {
                "run_id": row.run_id,
                "cui": row.cui,
                "state": row.state,
                "started_at": row.started_at,
                "finished_at": row.finished_at,
                "band": row.band,
                "error": row.error,
            }
        )

    async def save_agent_result(self, run_id: str, result: AgentResult) -> None:
        """Upsert the result row. Signals are stored separately (SignalsStore)."""
        values = {
            "component": result.component.value,
            "status": result.status.value,
            "duration_ms": result.duration_ms,
            "sources_checked": result.sources_checked,
            "sources_failed": result.sources_failed,
            "notes": result.notes,
            "payload": result.model_dump(mode="json", exclude={"signals"}),
        }
        stmt = insert(AgentResultRow).values(run_id=run_id, agent=result.agent, **values)
        stmt = stmt.on_conflict_do_update(
            index_elements=[AgentResultRow.run_id, AgentResultRow.agent], set_=values
        )
        await self.session.execute(stmt)

    async def list_agent_results(
        self, run_id: str, signals_by_agent: dict[str, list[Signal]]
    ) -> list[AgentResult]:
        rows = await self.session.scalars(
            select(AgentResultRow)
            .where(AgentResultRow.run_id == run_id)
            .order_by(AgentResultRow.created_at, AgentResultRow.agent)
        )
        return [
            AgentResult.model_validate(
                {**row.payload, "signals": signals_by_agent.get(row.agent, [])}
            )
            for row in rows
        ]
