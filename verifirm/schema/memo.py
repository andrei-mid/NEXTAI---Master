"""Memo + verifier contracts.

FROZEN. Changing anything here needs a DECIDED entry in docs/DECISIONS.md first.

The memo agent writes ONLY from `ConsolidatedReport`. The critic rejects any sentence
whose claims or numbers are not traceable to it. The AI never decides.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from verifirm.schema.identity import IdentitySheet
from verifirm.schema.scoring import Score
from verifirm.schema.signals import AgentResult, Signal


class ConsolidatedReport(BaseModel):
    """Everything the memo may talk about. Nothing else exists for the memo agent."""

    cui: str
    run_id: str
    identity: IdentitySheet
    results: list[AgentResult]  # after entity resolution
    signals: list[Signal]  # flattened, deduplicated
    score: Score
    generated_at: datetime


class SectionKind(str, Enum):
    SUMMARY = "summary"
    RED_SIGNALS = "red_signals"
    YELLOW_SIGNALS = "yellow_signals"
    COVERAGE = "coverage"  # which sources were unavailable / timed out
    NEXT_STEPS = "next_steps"


class MemoSentence(BaseModel):
    text: str
    signal_ids: list[str] = Field(default_factory=list)  # every claim cites its signals


class MemoSection(BaseModel):
    kind: SectionKind
    title: str
    sentences: list[MemoSentence]


class ClientQuestion(BaseModel):
    question: str
    reason_signal_ids: list[str]


class RejectedSentence(BaseModel):
    text: str
    reason: str  # e.g. "number 25.400.000 not in consolidated JSON"


class VerifierReport(BaseModel):
    passed: bool
    checked_sentences: int
    rejected: list[RejectedSentence] = Field(default_factory=list)
    verified_at: datetime


class Memo(BaseModel):
    cui: str
    run_id: str
    sections: list[MemoSection]
    questions: list[ClientQuestion] = Field(default_factory=list)
    markdown: str  # rendered from sections AFTER the critic pass
    generated_at: datetime
    model: str | None = None
    verifier_report: VerifierReport | None = None
