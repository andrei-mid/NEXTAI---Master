"""Signal contract: the only currency agents use to talk to the rest of the system.

FROZEN. Changing anything here needs a DECIDED entry in docs/DECISIONS.md first.

Agents communicate only via these schema-validated models. Free text never crosses
agent boundaries (prompt-injection defense): `claim` is one factual sentence written
by our own code/LLM from structured facts, and `data` holds the facts themselves.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, HttpUrl, model_validator


class Severity(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


SEVERITY_ORDER: dict[Severity, int] = {
    Severity.INFO: 0,
    Severity.LOW: 1,
    Severity.MEDIUM: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}


class SourceType(str, Enum):
    OFFICIAL = "official"
    AGGREGATOR = "aggregator"
    WEB = "web"
    MOCK = "mock"
    SUBMITTED = "submitted"


class Component(str, Enum):
    IDENTITY = "identity"
    FINANCIALS = "financials"
    TAX = "tax"
    LITIGATION = "litigation"
    NETWORK = "network"
    SANCTIONS = "sanctions"
    MEDIA = "media"
    PRESENCE = "presence"


class SourceRef(BaseModel):
    name: str
    type: SourceType
    url: HttpUrl | None = None
    retrieved_at: datetime
    raw_ref: str | None = None  # ObjectStore key of the archived raw response
    content_hash: str | None = None  # sha256 of the raw response


class EntityMatch(BaseModel):
    method: str  # cui_exact | name+county | name_fuzzy | person_name
    score: float = Field(ge=0, le=1)
    ambiguous: bool = False


class Signal(BaseModel):
    signal_id: str  # deterministic (see agents.base.make_signal_id) so re-runs never duplicate
    cui: str
    agent: str
    component: Component
    rule_id: str  # e.g. NET-SERIAL-ADMIN-01, documented in docs/RULES.md
    claim: str  # one factual sentence, no opinion
    source: SourceRef
    evidence_date: date | None
    confidence: float = Field(ge=0, le=1)
    severity: Severity
    validated: bool = True  # False for web/media
    auto_stop_candidate: bool = False
    entity_match: EntityMatch
    data: dict[str, Any] = Field(default_factory=dict)  # structured facts the memo/critic may use

    @model_validator(mode="after")
    def _unvalidated_is_capped(self) -> Signal:
        """Unvalidated signals (web/media) can never trigger STOP and are capped at medium."""
        if not self.validated:
            self.auto_stop_candidate = False
            if SEVERITY_ORDER[self.severity] > SEVERITY_ORDER[Severity.MEDIUM]:
                self.severity = Severity.MEDIUM
        return self


class AgentStatus(str, Enum):
    OK = "ok"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"
    TIMEOUT = "timeout"
    SKIPPED = "skipped"


class AgentResult(BaseModel):
    agent: str
    component: Component
    status: AgentStatus
    sources_checked: list[str]
    sources_failed: list[str]
    signals: list[Signal]
    duration_ms: int
    notes: str | None = None
