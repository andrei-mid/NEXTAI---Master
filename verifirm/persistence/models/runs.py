"""Pipeline runs (idempotent by run_id). Owner: @role-1-database.

- runs_runs: one row per run, upserted on every state change (schema.runs.RunStatus).
  trigger / requested_at / request (schema.runs.RunRequest) are filled when the request is known.
- runs_agent_results: one row per (run_id, agent). payload = schema.signals.AgentResult
  WITHOUT its signals: those live in signals_signals and are joined back on read.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from verifirm.persistence.models.base import Base, CreatedAtMixin


class Run(CreatedAtMixin, Base):
    __tablename__ = "runs_runs"

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    cui: Mapped[str] = mapped_column(String(16), index=True)
    trigger: Mapped[str | None] = mapped_column(String(16))
    state: Mapped[str] = mapped_column(String(16))
    requested_at: Mapped[datetime | None]
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]
    band: Mapped[str | None] = mapped_column(String(16))
    error: Mapped[str | None] = mapped_column(Text)
    request: Mapped[dict[str, Any] | None]


class AgentResultRow(CreatedAtMixin, Base):
    __tablename__ = "runs_agent_results"

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    agent: Mapped[str] = mapped_column(String(32), primary_key=True)
    component: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16))
    duration_ms: Mapped[int]
    sources_checked: Mapped[list[str]] = mapped_column(ARRAY(Text))
    sources_failed: Mapped[list[str]] = mapped_column(ARRAY(Text))
    notes: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict[str, Any]]
