"""Scoring output. Produced by the deterministic scoring engine (no LLM).

FROZEN. Changing anything here needs a DECIDED entry in docs/DECISIONS.md first.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from verifirm.schema.signals import AgentStatus, Component


class Band(str, Enum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"
    STOP = "stop"
    GREY = "grey"  # not enough coverage to say anything


class ComponentScore(BaseModel):
    component: Component
    status: AgentStatus
    available: bool  # True only for OK / PARTIAL
    score: float | None = Field(default=None, ge=0, le=100)  # None when not available
    weight: float = Field(ge=0)  # configured weight (before re-normalization)
    effective_weight: float = Field(default=0, ge=0)  # after re-normalization over available
    signal_ids: list[str] = Field(default_factory=list)


class Coverage(BaseModel):
    weight_pct: float = Field(ge=0, le=100)  # sum of weights of available components
    available: int  # e.g. 7
    total: int  # e.g. 8
    missing: list[Component] = Field(default_factory=list)

    @property
    def label(self) -> str:
        return f"{self.available}/{self.total} sources"


class Score(BaseModel):
    cui: str
    run_id: str
    trust_score: float | None = Field(default=None, ge=0, le=100)  # None if nothing available
    band: Band
    band_reasons: list[str] = Field(
        default_factory=list
    )  # rule-style reasons, e.g. "AUTO_STOP:ID-INACTIVE-01"
    components: list[ComponentScore]
    coverage: Coverage
    auto_stop_signal_ids: list[str] = Field(default_factory=list)
    natural_person_flow: bool = False  # PFA/II/IF -> separate flow (AI Act)
    config_version: str  # version string from scoring/config/weights.yaml
    computed_at: datetime
