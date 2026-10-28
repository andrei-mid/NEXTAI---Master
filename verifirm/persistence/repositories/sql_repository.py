"""STUB. Owner: @role-1-database. Postgres implementation of the Repository port.

Selected by apps/wiring.py when REPOSITORY_BACKEND=postgres. Implement each method by opening
`engine.session_scope()` and delegating to the per-area stores in this package
(companies, runs, signals, scores, memos, audit). Rules:
- Idempotent: INSERT ... ON CONFLICT DO UPDATE on (run_id, agent) and (run_id, signal_id).
- record_decision is INSERT-only (append-only audit log).
- list_portfolio: latest score per cui (DISTINCT ON), filter by band, `q` with ILIKE on name/cui.
- Round-trip every payload through the schema models (model_validate) on read.
Integration tests run against the Docker Postgres (no SQLite, not even in tests). See
persistence/tests/conftest.py for the skip-if-unreachable fixture.
"""

from __future__ import annotations

from verifirm.core.ports.repository import Repository
from verifirm.schema.api import DecisionRecord
from verifirm.schema.financials import SubmittedFinancials
from verifirm.schema.identity import IdentitySheet
from verifirm.schema.memo import Memo
from verifirm.schema.runs import RunStatus
from verifirm.schema.scoring import Band, Score
from verifirm.schema.signals import AgentResult, Signal


class SqlRepository(Repository):
    async def save_run(self, status: RunStatus) -> None:
        raise NotImplementedError

    async def get_run(self, run_id: str) -> RunStatus | None:
        raise NotImplementedError

    async def save_identity_sheet(self, run_id: str, sheet: IdentitySheet) -> None:
        raise NotImplementedError

    async def get_identity_sheet(self, cui: str) -> IdentitySheet | None:
        raise NotImplementedError

    async def save_submitted_financials(self, run_id: str, data: SubmittedFinancials) -> None:
        raise NotImplementedError

    async def save_agent_result(self, run_id: str, result: AgentResult) -> None:
        raise NotImplementedError

    async def list_agent_results(self, run_id: str) -> list[AgentResult]:
        raise NotImplementedError

    async def list_signals(self, cui: str) -> list[Signal]:
        raise NotImplementedError

    async def save_score(self, score: Score) -> None:
        raise NotImplementedError

    async def get_latest_score(self, cui: str) -> Score | None:
        raise NotImplementedError

    async def save_memo(self, memo: Memo) -> None:
        raise NotImplementedError

    async def get_latest_memo(self, cui: str) -> Memo | None:
        raise NotImplementedError

    async def list_portfolio(
        self, *, band: Band | None, q: str | None, page: int, page_size: int
    ) -> tuple[list[str], int]:
        raise NotImplementedError

    async def record_decision(self, record: DecisionRecord) -> None:
        raise NotImplementedError

    async def list_decisions(self, cui: str) -> list[DecisionRecord]:
        raise NotImplementedError
