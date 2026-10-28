"""APPEND-ONLY audit log of analyst decisions (the AI never decides). Owner: @role-1-database.

audit_decisions: one row per DecisionRecord. The migration installs a trigger that rejects
UPDATE and DELETE for every role, owner included.
Retention period: PENDING in docs/DECISIONS.md (GDPR). A retention job will need to bypass the
trigger explicitly, which is the point.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from verifirm.persistence.models.base import Base, CreatedAtMixin


class DecisionRow(CreatedAtMixin, Base):
    __tablename__ = "audit_decisions"

    decision_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    cui: Mapped[str] = mapped_column(String(16), index=True)
    run_id: Mapped[str | None] = mapped_column(String(64))
    decision: Mapped[str] = mapped_column(String(32))
    comment: Mapped[str] = mapped_column(Text)
    analyst: Mapped[str] = mapped_column(Text)
    band_at_decision: Mapped[str | None] = mapped_column(String(16))
    recorded_at: Mapped[datetime]
