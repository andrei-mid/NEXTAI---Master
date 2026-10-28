"""Live read model: builds the API responses from the Repository (outside FIXTURE_MODE).

Everything here is derived from what the pipeline persisted. No scoring logic lives here:
score, band and components are passed through exactly as stored.
"""

from __future__ import annotations

import asyncio
import re
import unicodedata
from datetime import UTC, date, datetime, time

from fastapi import HTTPException

from verifirm.core.ports.repository import Repository
from verifirm.schema.api import (
    CompanyDetail,
    CompanyHistory,
    CompanyList,
    CompanyListItem,
    Graph,
    GraphEdge,
    GraphNode,
    MemoResponse,
    NodeType,
    ScorePoint,
    TopSignal,
)
from verifirm.schema.identity import IdentitySheet, Person, PersonRole
from verifirm.schema.scoring import Band, Score
from verifirm.schema.signals import SEVERITY_ORDER, Signal, SourceRef


def _slug(name: str) -> str:
    folded = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", folded.lower()).strip("-")


def top_signal(signals: list[Signal]) -> TopSignal | None:
    """The most severe signal (ties: higher confidence). Unvalidated media never leads."""
    candidates = [s for s in signals if s.validated] or signals
    if not candidates:
        return None
    best = max(candidates, key=lambda s: (SEVERITY_ORDER[s.severity], s.confidence))
    return TopSignal(rule_id=best.rule_id, claim=best.claim, severity=best.severity)


def _sources(identity: IdentitySheet, signals: list[Signal]) -> list[SourceRef]:
    seen: set[tuple[str, str | None]] = set()
    out: list[SourceRef] = []
    for ref in [*identity.sources, *[s.source for s in signals]]:
        key = (ref.name, str(ref.url) if ref.url else None)
        if key not in seen:
            seen.add(key)
            out.append(ref)
    return out


def start_of(day: date) -> datetime:
    return datetime.combine(day, time.min, UTC)


def end_of(day: date) -> datetime:
    """`as_of=2026-09-15` means everything known by the end of that day (UTC)."""
    return datetime.combine(day, time.max, UTC)


def score_point(score: Score) -> ScorePoint:
    return ScorePoint(
        run_id=score.run_id,
        computed_at=score.computed_at,
        band=score.band,
        score=score.trust_score,
        coverage=score.coverage,
    )


# How many companies the list loads at once. Each repository call is one database round trip
# (~0.1 s from a laptop to a hosted Postgres): one after another, a page of companies took
# ~13 s. Concurrent, it costs about one company. Kept modest for small hosted Postgres plans.
LIST_CONCURRENCY = 8


def _edge_role(person: Person) -> str | None:
    if person.role in (PersonRole.ADMINISTRATOR, PersonRole.LEGAL_REPRESENTATIVE):
        return "administrator" if person.valid_to is None else "former_administrator"
    if person.role is PersonRole.SHAREHOLDER:
        return "shareholder"
    return None


class RepoReadModel:
    def __init__(self, repository: Repository) -> None:
        self.repo = repository

    async def _identity(self, cui: str) -> IdentitySheet:
        identity = await self.repo.get_identity_sheet(cui)
        if identity is None:
            raise HTTPException(status_code=404, detail=f"unknown company {cui}")
        return identity

    async def _score(self, cui: str, as_of: date | None) -> Score | None:
        if as_of is None:
            return await self.repo.get_latest_score(cui)
        return await self.repo.get_score_as_of(cui, end_of(as_of))

    async def _signals(self, cui: str, as_of: date | None) -> list[Signal]:
        if as_of is None:
            return await self.repo.list_signals(cui)
        return await self.repo.list_signals_as_of(cui, end_of(as_of))

    async def list_companies(
        self,
        *,
        band: Band | None,
        q: str | None,
        page: int,
        page_size: int,
        as_of: date | None = None,
    ) -> CompanyList:
        if as_of is None:
            cuis, total = await self.repo.list_portfolio(
                band=band, q=q, page=page, page_size=page_size
            )
        else:
            cuis, total = await self.repo.list_portfolio_as_of(
                as_of=end_of(as_of), band=band, q=q, page=page, page_size=page_size
            )
        gate = asyncio.Semaphore(LIST_CONCURRENCY)

        async def item(cui: str) -> CompanyListItem:
            async with gate:  # identity, score and signals at the same time
                identity, score, signals = await asyncio.gather(
                    self.repo.get_identity_sheet(cui),
                    self._score(cui, as_of),
                    self._signals(cui, as_of),
                )
            return CompanyListItem(
                cui=cui,
                name=identity.current_name if identity else cui,
                band=score.band if score else None,
                score=score.trust_score if score else None,
                coverage=score.coverage if score else None,
                last_checked=score.computed_at if score else None,
                top_signal=top_signal(signals) if score else None,
                fictional=identity.fictional if identity else False,
            )

        items = list(await asyncio.gather(*(item(cui) for cui in cuis)))  # keeps page order
        return CompanyList(items=items, page=page, page_size=page_size, total=total)

    async def detail(self, cui: str, as_of: date | None = None) -> CompanyDetail:
        """`as_of`: the score and signals the bank had at the end of that day. The identity
        sheet is the current one (sheets are not versioned by date)."""
        identity, score, all_signals = await asyncio.gather(
            self._identity(cui), self._score(cui, as_of), self._signals(cui, as_of)
        )
        if as_of is not None and score is None:
            raise HTTPException(status_code=404, detail=f"company {cui} not checked by {as_of}")
        signals = all_signals if score else []
        return CompanyDetail(
            identity_sheet=identity,
            score=score.trust_score if score else None,
            band=score.band if score else None,
            components=score.components if score else [],
            coverage=score.coverage if score else None,
            sources=_sources(identity, signals),
            last_checked=score.computed_at if score else None,
        )

    async def signals(self, cui: str, as_of: date | None = None) -> list[Signal]:
        await self._identity(cui)
        return await self._signals(cui, as_of)

    async def history(
        self, cui: str, date_from: date | None, date_to: date | None
    ) -> CompanyHistory:
        await self._identity(cui)
        since = start_of(date_from) if date_from else None
        until = end_of(date_to) if date_to else None
        return CompanyHistory(
            cui=cui,
            date_from=date_from,
            date_to=date_to,
            scores=[score_point(s) for s in await self.repo.list_score_history(cui, since, until)],
            events=await self.repo.list_events(cui, date_from, date_to),
            decisions=await self.repo.list_decisions_between(cui, since, until),
        )

    async def memo(self, cui: str) -> MemoResponse:
        memo = await self.repo.get_latest_memo(cui)
        if memo is None:
            raise HTTPException(status_code=404, detail=f"no memo for company {cui}")
        return MemoResponse(
            markdown=memo.markdown,
            questions=memo.questions,
            generated_at=memo.generated_at,
            verifier_report=memo.verifier_report,
        )

    async def graph(self, cui: str, depth: int) -> Graph:
        """One hop around the company, from its identity sheet.

        Deeper hops need the persisted graph tables (role 1), so `depth` > 1 returns the same
        one-hop graph until those exist.
        """
        identity = await self._identity(cui)
        root = f"company:{identity.cui}"
        nodes = {
            root: GraphNode(
                id=root,
                type=NodeType.COMPANY,
                label=identity.current_name,
                status=identity.status.value,
                fictional=identity.fictional,
            )
        }
        edges: list[GraphEdge] = []
        for person in [*identity.administrators, *identity.shareholders]:
            role = _edge_role(person)
            if role is None:
                continue
            if person.is_company and person.cui:
                node_id, node_type = f"company:{person.cui}", NodeType.COMPANY
            else:
                node_id, node_type = f"person:{_slug(person.name)}", NodeType.PERSON
            if node_id == root:
                continue
            nodes.setdefault(
                node_id,
                GraphNode(
                    id=node_id, type=node_type, label=person.name, fictional=identity.fictional
                ),
            )
            edge = GraphEdge(source=node_id, target=root, role=role)
            if edge not in edges:
                edges.append(edge)
        return Graph(nodes=list(nodes.values()), edges=edges)
