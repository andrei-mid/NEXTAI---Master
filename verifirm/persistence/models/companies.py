"""Portfolio companies and their identity sheets. Owner: @role-1-database.

- companies_companies: one row per CUI. latest_run_id / latest_band are denormalised from the
  newest score (guarded by last_checked_at) so the portfolio list is a single indexed scan.
- companies_identity_sheets: one sheet per run, payload = schema.identity.IdentitySheet.
- companies_submitted_financials: one per run, payload = schema.financials.SubmittedFinancials.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, ForeignKey, Identity, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from verifirm.persistence.models.base import Base, CreatedAtMixin


class Company(CreatedAtMixin, Base):
    __tablename__ = "companies_companies"

    cui: Mapped[str] = mapped_column(String(16), primary_key=True)
    current_name: Mapped[str | None] = mapped_column(Text)  # None until an identity sheet exists
    fictional: Mapped[bool] = mapped_column(server_default="false")
    in_portfolio: Mapped[bool] = mapped_column(server_default="false")
    last_checked_at: Mapped[datetime | None]
    latest_run_id: Mapped[str | None] = mapped_column(String(64))
    latest_band: Mapped[str | None] = mapped_column(String(16), index=True)


class IdentitySheetRow(CreatedAtMixin, Base):
    __tablename__ = "companies_identity_sheets"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    cui: Mapped[str] = mapped_column(ForeignKey("companies_companies.cui"), index=True)
    run_id: Mapped[str] = mapped_column(String(64), unique=True)
    payload: Mapped[dict[str, Any]]


class SubmittedFinancialsRow(CreatedAtMixin, Base):
    __tablename__ = "companies_submitted_financials"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), unique=True)
    cui: Mapped[str] = mapped_column(String(16), index=True)
    payload: Mapped[dict[str, Any]]
