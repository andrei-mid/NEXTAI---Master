"""Repository port. All state that matters goes through here, so API and workers stay stateless.

Writes are idempotent: saving the same AgentResult twice for one run never duplicates
signals (they are keyed by signal_id).
Local: in-memory. Real: Postgres via SQLAlchemy (verifirm/persistence, D5).

Time-travel reads (docs/DECISIONS.md, "Time-travel reads") use two time axes, never mixed:
- known-at: `as_of` / `since` / `until` (datetimes) on Score.computed_at and
  DecisionRecord.recorded_at: what the bank knew at that moment (replay).
- happened-at: `list_events` on Signal.evidence_date (dates): when the fact occurred.
All bounds are inclusive. None = open.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, datetime

from verifirm.schema.api import DecisionRecord
from verifirm.schema.financials import SubmittedFinancials
from verifirm.schema.identity import IdentitySheet
from verifirm.schema.memo import Memo
from verifirm.schema.runs import RunStatus
from verifirm.schema.scoring import Band, Score
from verifirm.schema.signals import AgentResult, Signal


class Repository(ABC):
    # --- runs
    @abstractmethod
    async def save_run(self, status: RunStatus) -> None: ...

    @abstractmethod
    async def get_run(self, run_id: str) -> RunStatus | None: ...

    # --- pipeline outputs
    @abstractmethod
    async def save_identity_sheet(self, run_id: str, sheet: IdentitySheet) -> None: ...

    @abstractmethod
    async def get_identity_sheet(self, cui: str) -> IdentitySheet | None:
        """Latest identity sheet for the company."""

    @abstractmethod
    async def save_submitted_financials(self, run_id: str, data: SubmittedFinancials) -> None: ...

    @abstractmethod
    async def save_agent_result(self, run_id: str, result: AgentResult) -> None:
        """Upsert by (run_id, agent). Signals are upserted by signal_id."""

    @abstractmethod
    async def list_agent_results(self, run_id: str) -> list[AgentResult]: ...

    @abstractmethod
    async def list_signals(self, cui: str) -> list[Signal]:
        """Signals of the latest scored run for the company."""

    @abstractmethod
    async def save_score(self, score: Score) -> None: ...

    @abstractmethod
    async def get_latest_score(self, cui: str) -> Score | None: ...

    @abstractmethod
    async def save_memo(self, memo: Memo) -> None: ...

    @abstractmethod
    async def get_latest_memo(self, cui: str) -> Memo | None: ...

    # --- portfolio
    @abstractmethod
    async def list_portfolio(
        self, *, band: Band | None, q: str | None, page: int, page_size: int
    ) -> tuple[list[str], int]:
        """Return (CUIs on this page, total count)."""

    # --- audit log (append-only)
    @abstractmethod
    async def record_decision(self, record: DecisionRecord) -> None: ...

    @abstractmethod
    async def list_decisions(self, cui: str) -> list[DecisionRecord]: ...

    # --- time-travel reads
    @abstractmethod
    async def get_score_as_of(self, cui: str, as_of: datetime) -> Score | None:
        """The newest score computed at or before `as_of`."""

    @abstractmethod
    async def list_score_history(
        self, cui: str, since: datetime | None = None, until: datetime | None = None
    ) -> list[Score]:
        """Every score computed in [since, until], oldest first."""

    @abstractmethod
    async def list_signals_as_of(self, cui: str, as_of: datetime) -> list[Signal]:
        """Signals of the newest run scored at or before `as_of`."""

    @abstractmethod
    async def list_events(
        self, cui: str, since: date | None = None, until: date | None = None
    ) -> list[Signal]:
        """Signals of the newest scored run whose evidence_date is in [since, until], oldest
        first. Signals without an evidence_date are left out."""

    @abstractmethod
    async def list_portfolio_as_of(
        self, *, as_of: datetime, band: Band | None, q: str | None, page: int, page_size: int
    ) -> tuple[list[str], int]:
        """The portfolio at `as_of`: companies scored by then, `band` = their band at that time."""

    @abstractmethod
    async def list_decisions_between(
        self, cui: str, since: datetime | None = None, until: datetime | None = None
    ) -> list[DecisionRecord]:
        """Analyst decisions recorded in [since, until], oldest first."""
