"""AI analyst opinions (docs/DECISIONS.md, "AI analyst opinion"). Owner: @role-1-database.

analyst_opinions: one opinion per run. payload = schema.analyst.AnalystOpinion, dossier =
schema.analyst.CompanyDossier: exactly what the model saw (audit and replay). The opinion never
changes the official score, which lives in scores_scores.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Index, String
from sqlalchemy.orm import Mapped, mapped_column

from verifirm.persistence.models.base import Base, CreatedAtMixin


class AnalystOpinionRow(CreatedAtMixin, Base):
    __tablename__ = "analyst_opinions"
    __table_args__ = (Index("ix_analyst_opinions_cui_generated_at", "cui", "generated_at"),)

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    cui: Mapped[str] = mapped_column(String(16))
    generated_at: Mapped[datetime]
    model: Mapped[str | None] = mapped_column(String(128))
    opinion_score: Mapped[int | None]
    n_flags: Mapped[int]
    n_rejected: Mapped[int]
    payload: Mapped[dict[str, Any]]
    dossier: Mapped[dict[str, Any]]
