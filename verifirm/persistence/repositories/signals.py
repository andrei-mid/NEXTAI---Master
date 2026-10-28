"""Queries for the `signals_*` tables (see models/signals.py). Owner: @role-1-database."""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from verifirm.persistence.models.signals import SignalRow
from verifirm.schema.signals import Signal


class SignalsStore:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def replace_for_agent(self, run_id: str, agent: str, signals: list[Signal]) -> None:
        """Make the stored signals of (run_id, agent) equal to `signals`, idempotently.

        Upsert by (run_id, signal_id) and drop the ones a re-run of the agent no longer reports.
        """
        unique = {s.signal_id: s for s in signals}
        stale = delete(SignalRow).where(SignalRow.run_id == run_id, SignalRow.agent == agent)
        if unique:
            stale = stale.where(SignalRow.signal_id.not_in(list(unique)))
        await self.session.execute(stale)
        if not unique:
            return
        rows = [
            {
                "run_id": run_id,
                "signal_id": s.signal_id,
                "cui": s.cui,
                "agent": s.agent,
                "component": s.component.value,
                "rule_id": s.rule_id,
                "severity": s.severity.value,
                "validated": s.validated,
                "auto_stop_candidate": s.auto_stop_candidate,
                "confidence": s.confidence,
                "evidence_date": s.evidence_date,
                "payload": s.model_dump(mode="json"),
            }
            for s in unique.values()
        ]
        stmt = insert(SignalRow).values(rows)
        updatable = [c for c in rows[0] if c not in ("run_id", "signal_id")]
        stmt = stmt.on_conflict_do_update(
            index_elements=[SignalRow.run_id, SignalRow.signal_id],
            set_={c: stmt.excluded[c] for c in updatable},
        )
        await self.session.execute(stmt)

    async def list_for_run(self, run_id: str) -> list[Signal]:
        payloads = await self.session.scalars(
            select(SignalRow.payload)
            .where(SignalRow.run_id == run_id)
            .order_by(SignalRow.agent, SignalRow.signal_id)
        )
        return [Signal.model_validate(p) for p in payloads]

    async def list_events(
        self, run_id: str, since: date | None = None, until: date | None = None
    ) -> list[Signal]:
        """Signals of one run whose fact happened in [since, until] (evidence_date, inclusive),
        oldest first: the timeline of what occurred. Signals without an evidence_date have no
        place on a timeline and are left out."""
        stmt = select(SignalRow.payload).where(
            SignalRow.run_id == run_id, SignalRow.evidence_date.is_not(None)
        )
        if since is not None:
            stmt = stmt.where(SignalRow.evidence_date >= since)
        if until is not None:
            stmt = stmt.where(SignalRow.evidence_date <= until)
        payloads = await self.session.scalars(
            stmt.order_by(SignalRow.evidence_date, SignalRow.signal_id)
        )
        return [Signal.model_validate(p) for p in payloads]

    async def by_agent_for_run(self, run_id: str) -> dict[str, list[Signal]]:
        grouped: dict[str, list[Signal]] = defaultdict(list)
        for signal in await self.list_for_run(run_id):
            grouped[signal.agent].append(signal)
        return dict(grouped)
