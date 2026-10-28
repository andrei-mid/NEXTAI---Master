"""Queries for the `scores_*` tables (see models/scores.py). Owner: @role-1-database.

`as_of` / `since` / `until` filter on computed_at: when the bank knew it (docs/DECISIONS.md,
"Time-travel reads").
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Subquery, select
from sqlalchemy.dialects.postgresql import distinct_on, insert
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

    async def get_latest_score(self, cui: str, as_of: datetime | None = None) -> Score | None:
        """Newest score, or the newest one computed at or before `as_of` (what the bank knew)."""
        stmt = select(ScoreRow.payload).where(ScoreRow.cui == cui)
        if as_of is not None:
            stmt = stmt.where(ScoreRow.computed_at <= as_of)
        payload = await self.session.scalar(
            stmt.order_by(ScoreRow.computed_at.desc(), ScoreRow.run_id.desc()).limit(1)
        )
        return None if payload is None else Score.model_validate(payload)

    async def list_history(
        self, cui: str, since: datetime | None = None, until: datetime | None = None
    ) -> list[Score]:
        """Every score computed in [since, until] (both inclusive, open when None), oldest first."""
        stmt = select(ScoreRow.payload).where(ScoreRow.cui == cui)
        if since is not None:
            stmt = stmt.where(ScoreRow.computed_at >= since)
        if until is not None:
            stmt = stmt.where(ScoreRow.computed_at <= until)
        payloads = await self.session.scalars(stmt.order_by(ScoreRow.computed_at, ScoreRow.run_id))
        return [Score.model_validate(p) for p in payloads]

    def latest_per_cui(self, as_of: datetime) -> Subquery:
        """(cui, run_id, band) of each company's newest score at `as_of` (DISTINCT ON)."""
        return (
            select(ScoreRow.cui, ScoreRow.run_id, ScoreRow.band)
            .where(ScoreRow.computed_at <= as_of)
            .ext(distinct_on(ScoreRow.cui))
            .order_by(ScoreRow.cui, ScoreRow.computed_at.desc(), ScoreRow.run_id.desc())
            .subquery("latest_scores")
        )
