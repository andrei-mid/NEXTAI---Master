"""HTTP API response/request models (docs/SOLUTION.md section "API contract").

FROZEN. Changing anything here needs a DECIDED entry in docs/DECISIONS.md first.
The frontend builds against these; JSON Schemas are exported to docs/schema/.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from verifirm.schema.identity import IdentitySheet
from verifirm.schema.memo import ClientQuestion, VerifierReport
from verifirm.schema.scoring import Band, ComponentScore, Coverage
from verifirm.schema.signals import Severity, SourceRef


class Health(BaseModel):
    status: str  # "ok"
    fixture_mode: bool
    version: str


class TopSignal(BaseModel):
    rule_id: str
    claim: str
    severity: Severity


class CompanyListItem(BaseModel):
    cui: str
    name: str
    band: Band | None  # None = never checked yet
    score: float | None
    coverage: Coverage | None
    last_checked: datetime | None
    top_signal: TopSignal | None
    fictional: bool


class CompanyList(BaseModel):
    items: list[CompanyListItem]
    page: int
    page_size: int
    total: int


class CompanyDetail(BaseModel):
    identity_sheet: IdentitySheet
    score: float | None
    band: Band | None
    components: list[ComponentScore]
    coverage: Coverage | None
    sources: list[SourceRef]
    last_checked: datetime | None


class MemoResponse(BaseModel):
    markdown: str
    questions: list[ClientQuestion]
    generated_at: datetime
    verifier_report: VerifierReport | None


class NodeType(str, Enum):
    COMPANY = "company"
    PERSON = "person"


class GraphNode(BaseModel):
    id: str  # "company:<cui>" or "person:<slug>"
    type: NodeType
    label: str
    status: str | None = None  # CompanyStatus value for companies
    fictional: bool = False


class GraphEdge(BaseModel):
    source: str
    target: str
    role: str  # administrator | shareholder | invoices (circular-invoicing edge) ...


class Graph(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class RunCreated(BaseModel):
    run_id: str


class DecisionKind(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    ESCALATE = "escalate"  # to human review / risk committee
    REQUEST_INFO = "request_info"


class DecisionRequest(BaseModel):
    decision: DecisionKind
    comment: str = Field(min_length=1)
    analyst: str  # analyst id/name from the (demo) auth


class DecisionRecord(BaseModel):
    """Append-only audit-log entry. The analyst decides, the AI never does."""

    decision_id: str
    cui: str
    decision: DecisionKind
    comment: str
    analyst: str
    run_id: str | None  # the run whose memo/score the analyst looked at
    band_at_decision: Band | None
    recorded_at: datetime
