"""Signals produced by agents (after entity resolution). Owner: @role-1-database.

signals_signals: (run_id, signal_id) PK, so re-saving a run never duplicates. The indexed columns
mirror the Signal fields we filter on; payload = schema.signals.Signal is the source of truth.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import Index, String
from sqlalchemy.orm import Mapped, mapped_column

from verifirm.persistence.models.base import Base, CreatedAtMixin


class SignalRow(CreatedAtMixin, Base):
    __tablename__ = "signals_signals"
    __table_args__ = (Index("ix_signals_signals_cui_run_id", "cui", "run_id"),)

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    signal_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    cui: Mapped[str] = mapped_column(String(16))
    agent: Mapped[str] = mapped_column(String(32))
    component: Mapped[str] = mapped_column(String(16))
    rule_id: Mapped[str] = mapped_column(String(64), index=True)
    severity: Mapped[str] = mapped_column(String(16), index=True)
    validated: Mapped[bool]
    auto_stop_candidate: Mapped[bool]
    confidence: Mapped[float]
    evidence_date: Mapped[date | None]
    payload: Mapped[dict[str, Any]]
