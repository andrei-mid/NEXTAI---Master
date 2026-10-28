"""Run lifecycle contracts. Every pipeline execution has a `run_id`; jobs are idempotent.

FROZEN. Changing anything here needs a DECIDED entry in docs/DECISIONS.md first.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from verifirm.schema.scoring import Band
from verifirm.schema.signals import AgentStatus


class RunTrigger(str, Enum):
    APPLICATION = "application"  # new credit application (CUI + documents)
    RECHECK = "recheck"  # manual re-check from the UI
    SWEEP = "sweep"  # background portfolio change detection


class RunState(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"  # e.g. CUI failed the checksum gate


class RunRequest(BaseModel):
    run_id: str
    cui: str
    trigger: RunTrigger
    document_keys: list[str] = Field(default_factory=list)  # ObjectStore keys of submitted files
    agents: list[str] | None = None  # None = all registered agents
    disabled_sources: list[str] = Field(default_factory=list)  # demo: "switch a source off"
    requested_at: datetime


class RunStatus(BaseModel):
    run_id: str
    cui: str
    state: RunState
    started_at: datetime | None = None
    finished_at: datetime | None = None
    band: Band | None = None
    error: str | None = None


class AgentProgressEvent(BaseModel):
    """One SSE event on GET /runs/{run_id}/events."""

    run_id: str
    agent: str  # agent name, or a pipeline step: identity_sheet | scoring | memo | critic
    status: AgentStatus | None = None  # None while running
    n_signals: int = 0
    elapsed_ms: int = 0
    done: bool = False  # True on the final event of the run
