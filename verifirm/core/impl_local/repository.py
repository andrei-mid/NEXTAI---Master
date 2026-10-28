from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime

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
        self._score_history: dict[str, dict[str, Score]] = defaultdict(
            dict
        )  # cui -> run_id -> score
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
        self._score_history[score.cui][score.run_id] = score

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

    # --- time-travel reads
    def _history(
        self, cui: str, since: datetime | None = None, until: datetime | None = None
    ) -> list[Score]:
        scores = sorted(
            self._score_history.get(cui, {}).values(), key=lambda s: (s.computed_at, s.run_id)
        )
        return [
            s
            for s in scores
            if (since is None or s.computed_at >= since)
            and (until is None or s.computed_at <= until)
        ]

    async def get_score_as_of(self, cui: str, as_of: datetime) -> Score | None:
        history = self._history(cui, until=as_of)
        return history[-1] if history else None

    async def list_score_history(
        self, cui: str, since: datetime | None = None, until: datetime | None = None
    ) -> list[Score]:
        return self._history(cui, since, until)

    async def list_signals_as_of(self, cui: str, as_of: datetime) -> list[Signal]:
        score = await self.get_score_as_of(cui, as_of)
        if score is None:
            return []
        return [s for r in await self.list_agent_results(score.run_id) for s in r.signals]

    async def list_events(
        self, cui: str, since: date | None = None, until: date | None = None
    ) -> list[Signal]:
        score = self._scores.get(cui)
        if score is None:
            return []
        signals = [s for r in await self.list_agent_results(score.run_id) for s in r.signals]
        events = [
            s
            for s in signals
            if s.evidence_date is not None
            and (since is None or s.evidence_date >= since)
            and (until is None or s.evidence_date <= until)
        ]
        return sorted(events, key=lambda s: (s.evidence_date or date.min, s.signal_id))

    async def list_portfolio_as_of(
        self, *, as_of: datetime, band: Band | None, q: str | None, page: int, page_size: int
    ) -> tuple[list[str], int]:
        cuis = []
        for cui in sorted(self._score_history):
            score = await self.get_score_as_of(cui, as_of)
            if score is None or (band is not None and score.band != band):
                continue
            name = (getattr(self._sheets.get(cui), "current_name", "") or "").lower()
            if q and q.lower() not in cui and q.lower() not in name:
                continue
            cuis.append(cui)
        start = (page - 1) * page_size
        return cuis[start : start + page_size], len(cuis)

    async def list_decisions_between(
        self, cui: str, since: datetime | None = None, until: datetime | None = None
    ) -> list[DecisionRecord]:
        decisions = sorted(
            self._decisions.get(cui, []), key=lambda d: (d.recorded_at, d.decision_id)
        )
        return [
            d
            for d in decisions
            if (since is None or d.recorded_at >= since)
            and (until is None or d.recorded_at <= until)
        ]
