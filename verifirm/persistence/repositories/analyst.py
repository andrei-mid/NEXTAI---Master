"""Queries for the `analyst_*` tables (see models/analyst.py). Owner: @role-1-database."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from verifirm.persistence.models.analyst import AnalystOpinionRow
from verifirm.schema.analyst import AnalystOpinion, CompanyDossier


class AnalystStore:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save_opinion(self, opinion: AnalystOpinion, dossier: CompanyDossier) -> None:
        values = {
            "cui": opinion.cui,
            "generated_at": opinion.generated_at,
            "model": opinion.model,
            "opinion_score": opinion.opinion_score,
            "n_flags": len(opinion.flags),
            "n_rejected": len(opinion.rejected),
            "payload": opinion.model_dump(mode="json"),
            "dossier": dossier.model_dump(mode="json"),
        }
        stmt = insert(AnalystOpinionRow).values(run_id=opinion.run_id, **values)
        stmt = stmt.on_conflict_do_update(index_elements=[AnalystOpinionRow.run_id], set_=values)
        await self.session.execute(stmt)

    async def get_latest_opinion(self, cui: str) -> AnalystOpinion | None:
        payload = await self.session.scalar(
            select(AnalystOpinionRow.payload)
            .where(AnalystOpinionRow.cui == cui)
            .order_by(AnalystOpinionRow.generated_at.desc(), AnalystOpinionRow.run_id.desc())
            .limit(1)
        )
        return None if payload is None else AnalystOpinion.model_validate(payload)

    async def get_dossier(self, run_id: str) -> CompanyDossier | None:
        """What the model saw for one run (audit / replay)."""
        dossier = await self.session.scalar(
            select(AnalystOpinionRow.dossier).where(AnalystOpinionRow.run_id == run_id)
        )
        return None if dossier is None else CompanyDossier.model_validate(dossier)
