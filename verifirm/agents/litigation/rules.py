"""Litigation rules. Severities are PROPOSALS (docs/RULES.md).

The LLM CLASSIFIES each case (role, subject, stage, materiality) into `CaseClassification`.
The rules below are deterministic and decide which signal (if any) a classified case produces.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from verifirm.agents.base import RuleSpec
from verifirm.schema.signals import Component, Severity

C = Component.LITIGATION

RULES: dict[str, RuleSpec] = {
    r.rule_id: r
    for r in [
        RuleSpec(
            "LIT-INSOLVENCY-OPENED-01",
            C,
            Severity.CRITICAL,
            "Insolvency/bankruptcy proceedings OPENED against the company",
            "mock_bpi, portal_just",
            auto_stop=True,
        ),
        RuleSpec(
            "LIT-INSOLVENCY-REQUEST-01",
            C,
            Severity.HIGH,
            "Pending request to open insolvency against the company (not yet opened)",
            "portal_just",
        ),
        RuleSpec(
            "LIT-CRIMINAL-01",
            C,
            Severity.CRITICAL,
            "Criminal case with the company as defendant",
            "portal_just, scj",
            auto_stop=True,
        ),
        RuleSpec(
            "LIT-MATERIAL-CLAIM-01",
            C,
            Severity.HIGH,
            "Claim against the company > 10% of last turnover, pending",
            "portal_just, scj",
        ),
        RuleSpec(
            "LIT-MINOR-01",
            C,
            Severity.LOW,
            "Other pending case against the company (labour, small claims...)",
            "portal_just, scj",
        ),
    ]
}


class CaseRole(str, Enum):
    DEFENDANT = "defendant"  # pârât / debitor / inculpat
    CLAIMANT = "claimant"  # reclamant / creditor
    OTHER = "other"


class CaseSubject(str, Enum):
    INSOLVENCY = "insolvency"
    CRIMINAL = "criminal"
    COMMERCIAL_CLAIM = "commercial_claim"
    LABOUR = "labour"
    TAX = "tax"
    OTHER = "other"


class CaseStage(str, Enum):
    FIRST_INSTANCE = "first_instance"  # fond
    APPEAL = "appeal"  # apel
    SECOND_APPEAL = "second_appeal"  # recurs
    FINAL = "final"  # definitiv
    UNKNOWN = "unknown"


class CaseClassification(BaseModel):
    """LLM output for ONE case (schema-constrained, re-validated). No free text leaves the agent."""

    case_no: str
    role: CaseRole
    subject: CaseSubject
    stage: CaseStage
    insolvency_opened: bool = False  # True only if the case shows an opening decision
    claim_amount_ron: int | None = None
    next_hearing: str | None = None  # ISO date
    confidence: float = Field(ge=0, le=1)


def rule_for_case(
    case: CaseClassification, last_turnover_ron: int | None
) -> tuple[str, dict[str, Any]] | None:
    """Map one classified case to (rule_id, facts) or None.

    Brunaldo: 9101/99/2026 (ANAF insolvency request, first instance, hearing 2026-11-20)
    -> LIT-INSOLVENCY-REQUEST-01 (NOT opened, so NOT auto-stop).
    9102/99/2025 (1.8M claim, appeal) -> LIT-MATERIAL-CLAIM-01. 9103/99/2025 labour -> LIT-MINOR-01.
    Only cases where the company is the DEFENDANT produce signals."""
    raise NotImplementedError
