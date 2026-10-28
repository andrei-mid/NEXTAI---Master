"""Financial figures: what ANAF /bilant publishes and what the client submitted.

FROZEN. Changing anything here needs a DECIDED entry in docs/DECISIONS.md first.
Amounts are RON, as integers (ANAF publishes whole RON).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from verifirm.schema.signals import SourceRef


class FinancialYear(BaseModel):
    """One fiscal year. Any field can be None if the source does not publish it."""

    year: int
    turnover: int | None = None  # cifra de afaceri netă
    net_profit: int | None = None  # profit net (negative = loss)
    total_debts: int | None = None  # datorii
    equity: int | None = None  # capitaluri proprii / capitaluri - total
    share_capital: int | None = None  # capital subscris vărsat
    employees: int | None = None  # număr mediu de salariați
    extra: dict[str, int | None] = Field(default_factory=dict)  # other indicators by label
    source: SourceRef


class SubmittedFinancials(BaseModel):
    """Figures extracted from the documents the applicant submitted (PDF -> JSON).

    Produced by adapters/documents.py. The PDF text is UNTRUSTED: only these
    numbers ever leave the adapter.
    """

    cui: str
    years: list[FinancialYear]
    document_names: list[str] = Field(default_factory=list)
    extracted_at: datetime
