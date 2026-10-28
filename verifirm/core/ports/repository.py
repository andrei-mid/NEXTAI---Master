"""Repository port. All state that matters goes through here, so API and workers stay stateless.

Writes are idempotent: saving the same AgentResult twice for one run never duplicates
signals (they are keyed by signal_id).
Local: in-memory. Real: Postgres via SQLAlchemy (verifirm/persistence, D5).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

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
