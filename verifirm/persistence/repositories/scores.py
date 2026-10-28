"""Queries for the `scores_*` tables (see models/scores.py). Owner: @role-1-database."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from verifirm.persistence.models.scores import ScoreRow
from verifirm.schema.scoring import Score


class ScoresStore:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save_score(self, score: Score) -> None:
        values = {
            "cui": score.cui,
            "trust_score": score.trust_score,
            "band": score.band.value,
            "coverage_pct": score.coverage.weight_pct,
            "config_version": score.config_version,
            "computed_at": score.computed_at,
            "payload": score.model_dump(mode="json"),
        }
        stmt = insert(ScoreRow).values(run_id=score.run_id, **values)
        stmt = stmt.on_conflict_do_update(index_elements=[ScoreRow.run_id], set_=values)
        await self.session.execute(stmt)

    async def get_latest_score(self, cui: str) -> Score | None:
        payload = await self.session.scalar(
            select(ScoreRow.payload)
            .where(ScoreRow.cui == cui)
            .order_by(ScoreRow.computed_at.desc(), ScoreRow.run_id.desc())
            .limit(1)
        )
        return None if payload is None else Score.model_validate(payload)
