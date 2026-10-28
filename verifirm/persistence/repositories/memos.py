"""Queries for the `memos_*` tables (see models/memos.py). Owner: @role-1-database."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from verifirm.persistence.models.memos import MemoRow
from verifirm.schema.memo import Memo


class MemosStore:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save_memo(self, memo: Memo) -> None:
        values = {
            "cui": memo.cui,
            "generated_at": memo.generated_at,
            "model": memo.model,
            "verifier_passed": memo.verifier_report.passed if memo.verifier_report else None,
            "payload": memo.model_dump(mode="json"),
        }
        stmt = insert(MemoRow).values(run_id=memo.run_id, **values)
        stmt = stmt.on_conflict_do_update(index_elements=[MemoRow.run_id], set_=values)
        await self.session.execute(stmt)

    async def get_latest_memo(self, cui: str) -> Memo | None:
        payload = await self.session.scalar(
            select(MemoRow.payload)
            .where(MemoRow.cui == cui)
            .order_by(MemoRow.generated_at.desc(), MemoRow.run_id.desc())
            .limit(1)
        )
        return None if payload is None else Memo.model_validate(payload)
