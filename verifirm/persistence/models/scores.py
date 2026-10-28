"""Deterministic scores per run. Owner: @role-1-database.

scores_scores: one score per run, payload = schema.scoring.Score.
Latest score per cui = ORDER BY computed_at DESC (index on (cui, computed_at)).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Index, String
from sqlalchemy.orm import Mapped, mapped_column

from verifirm.persistence.models.base import Base, CreatedAtMixin


class ScoreRow(CreatedAtMixin, Base):
    __tablename__ = "scores_scores"
    __table_args__ = (Index("ix_scores_scores_cui_computed_at", "cui", "computed_at"),)

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    cui: Mapped[str] = mapped_column(String(16))
    trust_score: Mapped[float | None]
    band: Mapped[str] = mapped_column(String(16), index=True)
    coverage_pct: Mapped[float]
    config_version: Mapped[str] = mapped_column(String(64))
    computed_at: Mapped[datetime]
    payload: Mapped[dict[str, Any]]
