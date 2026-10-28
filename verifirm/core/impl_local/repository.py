from __future__ import annotations

from collections import defaultdict

from verifirm.core.ports.repository import Repository
from verifirm.schema.api import DecisionRecord
from verifirm.schema.financials import SubmittedFinancials
from verifirm.schema.identity import IdentitySheet
from verifirm.schema.memo import Memo
from verifirm.schema.runs import RunStatus
from verifirm.schema.scoring import Band, Score
from verifirm.schema.signals import AgentResult, Signal


class MemoryRepository(Repository):
    def __init__(self) -> None:
        self._runs: dict[str, RunStatus] = {}
        self._sheets: dict[str, IdentitySheet] = {}  # by cui (latest)
        self._submitted: dict[str, SubmittedFinancials] = {}  # by run_id
        self._results: dict[str, dict[str, AgentResult]] = defaultdict(
            dict
        )  # run_id -> agent -> result
        self._scores: dict[str, Score] = {}  # by cui (latest)
        self._memos: dict[str, Memo] = {}  # by cui (latest)
        self._decisions: dict[str, list[DecisionRecord]] = defaultdict(list)

    async def save_run(self, status: RunStatus) -> None:
        self._runs[status.run_id] = status

    async def get_run(self, run_id: str) -> RunStatus | None:
        return self._runs.get(run_id)

    async def save_identity_sheet(self, run_id: str, sheet: IdentitySheet) -> None:
        self._sheets[sheet.cui] = sheet

    async def get_identity_sheet(self, cui: str) -> IdentitySheet | None:
        return self._sheets.get(cui)

    async def save_submitted_financials(self, run_id: str, data: SubmittedFinancials) -> None:
        self._submitted[run_id] = data

    async def save_agent_result(self, run_id: str, result: AgentResult) -> None:
        unique = {s.signal_id: s for s in result.signals}
        self._results[run_id][result.agent] = result.model_copy(
            update={"signals": list(unique.values())}
        )

    async def list_agent_results(self, run_id: str) -> list[AgentResult]:
        return list(self._results.get(run_id, {}).values())

    async def list_signals(self, cui: str) -> list[Signal]:
        score = self._scores.get(cui)
        if score is None:
            return []
        results = await self.list_agent_results(score.run_id)
        return [s for r in results for s in r.signals]

    async def save_score(self, score: Score) -> None:
        self._scores[score.cui] = score

    async def get_latest_score(self, cui: str) -> Score | None:
        return self._scores.get(cui)

    async def save_memo(self, memo: Memo) -> None:
        self._memos[memo.cui] = memo

    async def get_latest_memo(self, cui: str) -> Memo | None:
        return self._memos.get(cui)

    async def list_portfolio(
        self, *, band: Band | None, q: str | None, page: int, page_size: int
    ) -> tuple[list[str], int]:
        cuis = sorted(set(self._sheets) | set(self._scores))
        if band is not None:
            cuis = [c for c in cuis if (s := self._scores.get(c)) is not None and s.band == band]
        if q:
            needle = q.lower()
            cuis = [
                c
                for c in cuis
                if needle in c
                or needle in (getattr(self._sheets.get(c), "current_name", "") or "").lower()
            ]
        start = (page - 1) * page_size
        return cuis[start : start + page_size], len(cuis)

    async def record_decision(self, record: DecisionRecord) -> None:
        self._decisions[record.cui].append(record)

    async def list_decisions(self, cui: str) -> list[DecisionRecord]:
        return list(self._decisions.get(cui, []))
