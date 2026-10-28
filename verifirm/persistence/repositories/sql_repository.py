"""Postgres implementation of the Repository port. Owner: @role-1-database.

Selected by apps/wiring.py when REPOSITORY_BACKEND=postgres. Each method is one unit of work
(`engine.session_scope()`) delegating to the per-area stores in this package. Rules:
- Idempotent: INSERT ... ON CONFLICT DO UPDATE on (run_id, agent) and (run_id, signal_id).
- record_decision is INSERT-only (append-only audit log).
- list_portfolio reads companies_companies.latest_band, kept current by save_score.
- Every payload is round-tripped through the schema models (model_validate) on read.
"""

from __future__ import annotations

from verifirm.core.config import Settings
from verifirm.core.ports.repository import Repository
from verifirm.persistence.engine import session_scope
from verifirm.persistence.repositories.audit import AuditStore
from verifirm.persistence.repositories.companies import CompaniesStore
from verifirm.persistence.repositories.memos import MemosStore
from verifirm.persistence.repositories.runs import RunsStore
from verifirm.persistence.repositories.scores import ScoresStore
from verifirm.persistence.repositories.signals import SignalsStore
from verifirm.schema.api import DecisionRecord
from verifirm.schema.financials import SubmittedFinancials
from verifirm.schema.identity import IdentitySheet
from verifirm.schema.memo import Memo
from verifirm.schema.runs import RunStatus
from verifirm.schema.scoring import Band, Score
from verifirm.schema.signals import AgentResult, Signal


class SqlRepository(Repository):
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings

    async def save_run(self, status: RunStatus) -> None:
        async with session_scope(self.settings) as s:
            await RunsStore(s).save_run(status)

    async def get_run(self, run_id: str) -> RunStatus | None:
        async with session_scope(self.settings) as s:
            return await RunsStore(s).get_run(run_id)

    async def save_identity_sheet(self, run_id: str, sheet: IdentitySheet) -> None:
        async with session_scope(self.settings) as s:
            await CompaniesStore(s).save_identity_sheet(run_id, sheet)

    async def get_identity_sheet(self, cui: str) -> IdentitySheet | None:
        async with session_scope(self.settings) as s:
            return await CompaniesStore(s).get_latest_identity_sheet(cui)

    async def save_submitted_financials(self, run_id: str, data: SubmittedFinancials) -> None:
        async with session_scope(self.settings) as s:
            await CompaniesStore(s).save_submitted_financials(run_id, data)

    async def save_agent_result(self, run_id: str, result: AgentResult) -> None:
        async with session_scope(self.settings) as s:
            await RunsStore(s).save_agent_result(run_id, result)
            await SignalsStore(s).replace_for_agent(run_id, result.agent, result.signals)

    async def list_agent_results(self, run_id: str) -> list[AgentResult]:
        async with session_scope(self.settings) as s:
            signals = await SignalsStore(s).by_agent_for_run(run_id)
            return await RunsStore(s).list_agent_results(run_id, signals)

    async def list_signals(self, cui: str) -> list[Signal]:
        async with session_scope(self.settings) as s:
            score = await ScoresStore(s).get_latest_score(cui)
            if score is None:
                return []
            return await SignalsStore(s).list_for_run(score.run_id)

    async def save_score(self, score: Score) -> None:
        async with session_scope(self.settings) as s:
            await ScoresStore(s).save_score(score)
            await CompaniesStore(s).upsert_from_score(score)

    async def get_latest_score(self, cui: str) -> Score | None:
        async with session_scope(self.settings) as s:
            return await ScoresStore(s).get_latest_score(cui)

    async def save_memo(self, memo: Memo) -> None:
        async with session_scope(self.settings) as s:
            await MemosStore(s).save_memo(memo)

    async def get_latest_memo(self, cui: str) -> Memo | None:
        async with session_scope(self.settings) as s:
            return await MemosStore(s).get_latest_memo(cui)

    async def list_portfolio(
        self, *, band: Band | None, q: str | None, page: int, page_size: int
    ) -> tuple[list[str], int]:
        async with session_scope(self.settings) as s:
            return await CompaniesStore(s).list_portfolio(
                band=band, q=q, page=page, page_size=page_size
            )

    async def record_decision(self, record: DecisionRecord) -> None:
        async with session_scope(self.settings) as s:
            await AuditStore(s).record_decision(record)

    async def list_decisions(self, cui: str) -> list[DecisionRecord]:
        async with session_scope(self.settings) as s:
            return await AuditStore(s).list_decisions(cui)
