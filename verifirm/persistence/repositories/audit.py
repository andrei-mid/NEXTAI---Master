"""Queries for the `audit_*` tables (see models/audit.py). Owner: @role-1-database.

INSERT and SELECT only: the table is append-only (trigger in the audit migration).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from verifirm.persistence.models.audit import DecisionRow
from verifirm.schema.api import DecisionRecord


class AuditStore:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record_decision(self, record: DecisionRecord) -> None:
        """Re-sending the same decision_id is a no-op (never an update)."""
        stmt = insert(DecisionRow).values(
            decision_id=record.decision_id,
            cui=record.cui,
            run_id=record.run_id,
            decision=record.decision.value,
            comment=record.comment,
            analyst=record.analyst,
            band_at_decision=record.band_at_decision.value if record.band_at_decision else None,
            recorded_at=record.recorded_at,
        )
        await self.session.execute(stmt.on_conflict_do_nothing(index_elements=["decision_id"]))

    async def list_decisions(
        self, cui: str, since: datetime | None = None, until: datetime | None = None
    ) -> list[DecisionRecord]:
        """Oldest first. `since` / `until` (inclusive) filter on recorded_at."""
        stmt = select(DecisionRow).where(DecisionRow.cui == cui)
        if since is not None:
            stmt = stmt.where(DecisionRow.recorded_at >= since)
        if until is not None:
            stmt = stmt.where(DecisionRow.recorded_at <= until)
        rows = await self.session.scalars(
            stmt.order_by(DecisionRow.recorded_at, DecisionRow.decision_id)
        )
        return [
            DecisionRecord.model_validate(
                {
                    "decision_id": r.decision_id,
                    "cui": r.cui,
                    "decision": r.decision,
                    "comment": r.comment,
                    "analyst": r.analyst,
                    "run_id": r.run_id,
                    "band_at_decision": r.band_at_decision,
                    "recorded_at": r.recorded_at,
                }
            )
            for r in rows
        ]
