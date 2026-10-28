"""Memos after the critic pass. Owner: @role-1-database.

memos_memos: one memo per run, payload = schema.memo.Memo. Latest per cui = ORDER BY generated_at DESC.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Index, String
from sqlalchemy.orm import Mapped, mapped_column

from verifirm.persistence.models.base import Base, CreatedAtMixin


class MemoRow(CreatedAtMixin, Base):
    __tablename__ = "memos_memos"
    __table_args__ = (Index("ix_memos_memos_cui_generated_at", "cui", "generated_at"),)

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    cui: Mapped[str] = mapped_column(String(16))
    generated_at: Mapped[datetime]
    model: Mapped[str | None] = mapped_column(String(128))
    verifier_passed: Mapped[bool | None]  # None when the critic has not run
    payload: Mapped[dict[str, Any]]
