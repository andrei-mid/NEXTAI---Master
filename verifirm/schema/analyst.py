"""AI analyst contracts: the company dossier the LLM reads and the opinion it returns.

FROZEN. Changing anything here needs a DECIDED entry in docs/DECISIONS.md first
("AI analyst opinion").

The dossier is built by code (consolidation/dossier.py), never by the LLM: every comparison and
every ratio is computed before the model sees it. Collections are keyed (year, date, field,
signal_id) so a flag can cite a stable path such as `financials.2024.equity`.

The opinion never decides and never changes the official (deterministic) score or band.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from verifirm.schema.scoring import Band
from verifirm.schema.signals import Severity

DISCLAIMER = (
    "This is my educated opinion, but I am not legally responsible: the analyst must confirm."
)


# ---------------------------------------------------------------------- dossier (input)
class CrossCheck(BaseModel):
    """One identity fact as each official source publishes it."""

    anaf: str | None
    onrc: str | None
    match: bool | None  # None = can't compare (a source is missing or uses another vocabulary)
    note: str | None = None


class SourceState(BaseModel):
    status: str  # ok | partial | unavailable
    retrieved_at: datetime | None = None
    note: str | None = None


class AnafSnapshot(BaseModel):
    """ANAF v9 as it was on one date (today + the last quarter-ends)."""

    name: str | None
    address: str | None
    caen_code: str | None
    registration_status: str | None
    vat_payer: bool | None
    inactive: bool | None
    found: bool = True  # False = ANAF did not know the CUI on that date


class SnapshotChange(BaseModel):
    field: str
    date_from: date  # the earlier snapshot
    date_to: date  # the later snapshot
    old: str | None
    new: str | None


class DossierYear(BaseModel):
    """One /bilant year. filed=False: nothing filed. filed=None: the year could not be read."""

    filed: bool | None
    turnover: int | None = None
    net_profit: int | None = None
    total_debts: int | None = None
    equity: int | None = None
    share_capital: int | None = None
    employees: int | None = None


class YearIndicators(BaseModel):
    """Computed in code from DossierYear (rounded as shown), None when not computable."""

    turnover_growth_pct: float | None = None  # vs the previous filed year, 1 decimal
    net_margin_pct: float | None = None  # net_profit / turnover, 1 decimal
    equity_to_share_capital: float | None = None  # 2 decimals; < 0.5 is the legal threshold
    turnover_per_employee: int | None = None
    debts_to_turnover: float | None = None  # 2 decimals


class DossierPerson(BaseModel):
    alias: str  # "Administrator A": the real name is never sent to the LLM
    role: str
    valid_from: date | None
    valid_to: date | None  # None = current


class DossierSignal(BaseModel):
    rule_id: str
    agent: str
    severity: Severity
    claim: str
    evidence_date: date | None
    validated: bool
    source_type: str
    data: dict[str, Any] = Field(default_factory=dict)


class OfficialScore(BaseModel):
    trust_score: float | None
    band: Band
    coverage: str  # e.g. "7/8 sources"


class CompanyDossier(BaseModel):
    cui: str
    fictional: bool
    run_id: str
    generated_at: datetime
    name: str
    legal_form: str | None
    cross_checks: dict[str, CrossCheck]  # name, address, county, caen_code, ...
    anaf_snapshots: dict[str, AnafSnapshot]  # ISO date -> snapshot, oldest first
    anaf_changes: list[SnapshotChange]
    financials: dict[str, DossierYear]  # year -> figures, oldest first
    indicators: dict[str, YearIndicators]  # year -> ratios
    administrators: list[DossierPerson]
    sources: dict[str, SourceState]  # anaf_v9, anaf_bilant, onrc_bulk
    agents: dict[str, str]  # agent -> status
    signals: dict[str, DossierSignal]  # signal_id -> signal
    official_score: OfficialScore


# ---------------------------------------------------------------------- opinion (output)
class FlagCategory(str, Enum):
    CROSS_SOURCE_MISMATCH = "cross_source_mismatch"
    FINANCIAL_INCONSISTENCY = "financial_inconsistency"
    SUSPICIOUS_CHANGE = "suspicious_change"
    DATA_GAP = "data_gap"
    OTHER = "other"


class Citation(BaseModel):
    path: str  # dotted path into the dossier JSON, e.g. "financials.2024.equity"
    value: str  # the value at that path, copied as text ("120000", "true", "null")


class AnalystFlag(BaseModel):
    title: str
    claim: str  # one or two factual sentences, numbers copied from the evidence
    category: FlagCategory
    severity: Severity
    evidence: list[Citation] = Field(min_length=1)


class AnalystDraft(BaseModel):
    """What the LLM returns (validated). Everything else is added by code."""

    flags: list[AnalystFlag]
    opinion_score: int = Field(ge=0, le=100)  # 100 = no concern, same direction as trust_score
    explanation: str


class RejectedFlag(BaseModel):
    flag: AnalystFlag
    reason: str


class AnalystOpinion(BaseModel):
    cui: str
    run_id: str
    generated_at: datetime
    model: str | None
    flags: list[AnalystFlag]  # only the flags whose evidence checked out
    rejected: list[RejectedFlag] = Field(default_factory=list)
    opinion_score: int | None = Field(default=None, ge=0, le=100)
    explanation: str
    disclaimer: str = DISCLAIMER
    official_band: Band  # unchanged by the opinion
    official_score: float | None
