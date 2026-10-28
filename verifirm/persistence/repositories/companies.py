"""Queries for the `companies_*` tables (see models/companies.py). Owner: @role-1-database."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from verifirm.persistence.models.companies import (
    Company,
    IdentitySheetRow,
    SubmittedFinancialsRow,
)
from verifirm.persistence.repositories.scores import ScoresStore
from verifirm.schema.financials import SubmittedFinancials
from verifirm.schema.identity import IdentitySheet
from verifirm.schema.scoring import Band, Score


class CompaniesStore:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert_from_sheet(self, sheet: IdentitySheet) -> None:
        stmt = insert(Company).values(
            cui=sheet.cui, current_name=sheet.current_name, fictional=sheet.fictional
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[Company.cui],
            set_={"current_name": stmt.excluded.current_name, "fictional": stmt.excluded.fictional},
        )
        await self.session.execute(stmt)

    async def upsert_from_score(self, score: Score) -> None:
        """Move latest_* forward only: an older score saved late never overwrites a newer one."""
        stmt = insert(Company).values(
            cui=score.cui,
            last_checked_at=score.computed_at,
            latest_run_id=score.run_id,
            latest_band=score.band.value,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[Company.cui],
            set_={
                "last_checked_at": stmt.excluded.last_checked_at,
                "latest_run_id": stmt.excluded.latest_run_id,
                "latest_band": stmt.excluded.latest_band,
            },
            where=or_(
                Company.last_checked_at.is_(None),
                Company.last_checked_at <= stmt.excluded.last_checked_at,
            ),
        )
        await self.session.execute(stmt)

    async def save_identity_sheet(self, run_id: str, sheet: IdentitySheet) -> None:
        await self.upsert_from_sheet(sheet)
        stmt = insert(IdentitySheetRow).values(
            cui=sheet.cui, run_id=run_id, payload=sheet.model_dump(mode="json")
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[IdentitySheetRow.run_id],
            set_={"cui": stmt.excluded.cui, "payload": stmt.excluded.payload},
        )
        await self.session.execute(stmt)

    async def get_latest_identity_sheet(self, cui: str) -> IdentitySheet | None:
        payload = await self.session.scalar(
            select(IdentitySheetRow.payload)
            .where(IdentitySheetRow.cui == cui)
            .order_by(IdentitySheetRow.created_at.desc(), IdentitySheetRow.id.desc())
            .limit(1)
        )
        return None if payload is None else IdentitySheet.model_validate(payload)

    async def save_submitted_financials(self, run_id: str, data: SubmittedFinancials) -> None:
        stmt = insert(SubmittedFinancialsRow).values(
            run_id=run_id, cui=data.cui, payload=data.model_dump(mode="json")
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[SubmittedFinancialsRow.run_id],
            set_={"cui": stmt.excluded.cui, "payload": stmt.excluded.payload},
        )
        await self.session.execute(stmt)

    async def list_portfolio(
        self,
        *,
        band: Band | None,
        q: str | None,
        page: int,
        page_size: int,
        as_of: datetime | None = None,
    ) -> tuple[list[str], int]:
        """CUIs ordered by cui. `q` matches the CUI or the current name (ILIKE).

        `as_of`: the portfolio as the bank saw it then. Only companies already scored at
        `as_of`, and `band` filters on the band of their newest score at that moment.
        """
        where = []
        base = select(Company.cui)
        if as_of is None:
            if band is not None:
                where.append(Company.latest_band == band.value)
        else:
            latest = ScoresStore(self.session).latest_per_cui(as_of)
            base = base.join(latest, latest.c.cui == Company.cui)
            if band is not None:
                where.append(latest.c.band == band.value)
        if q:
            pattern = f"%{_escape_like(q)}%"
            where.append(
                or_(
                    Company.cui.ilike(pattern, escape="\\"),
                    Company.current_name.ilike(pattern, escape="\\"),
                )
            )
        filtered = base.where(*where)
        total = await self.session.scalar(select(func.count()).select_from(filtered.subquery()))
        rows = await self.session.scalars(
            filtered.order_by(Company.cui).offset((page - 1) * page_size).limit(page_size)
        )
        return list(rows), int(total or 0)


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
