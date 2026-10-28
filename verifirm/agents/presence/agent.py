"""Owner: @role-4-external-agents (built by role 3 with the human's approval). Public-footprint agent.

Does the company leave the public trace a business of its size normally leaves?
1. Footprint, each part from its own source (one failing never hides the others):
   website + job postings  -> ctx.adapter("web_search").footprint(cui, name)   (WEB)
   SEAP contracts          -> ctx.adapter("seap").contracts_for(cui)            (OFFICIAL)
   EU-funded projects      -> ctx.adapter("kohesio").projects_for(name, cui)    (OFFICIAL)
   Fixture mode: fixtures/companies/<cui>_<slug>/presence.json holds all four parts.
2. Turnover for PRE-NO-FOOTPRINT-01: ctx.adapter("anaf_bilant"), the latest filed year.
   Agents never import other agents.
3. PRE-NO-FOOTPRINT-01 needs ALL four parts checked: one unknown part means no conclusion
   ("we couldn't look" is never "there is nothing"). If NO footprint source could be read, the
   agent is UNAVAILABLE (turnover alone is not a presence check, so it never inflates coverage).
4. Website evidence is WEB: the address check is validated=False. SEAP/Kohesio are OFFICIAL.
Demo: Zephyria -> PRE-NO-FOOTPRINT-01. Aurora -> website + jobs (no signal).
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any, cast

from verifirm.adapters.anaf_bilant import AnafBilantAdapter
from verifirm.adapters.base import Sourced, SourceUnavailable
from verifirm.adapters.kohesio import KohesioAdapter
from verifirm.adapters.seap import SeapAdapter
from verifirm.adapters.web_search import TavilyWebSearch
from verifirm.agents.base import AgentContext, BaseAgent
from verifirm.agents.presence import rules
from verifirm.agents.presence.rules import RULES, PresenceConfig, load_config
from verifirm.core.logging import get_logger
from verifirm.core.registry import register_agent
from verifirm.schema.financials import FinancialYear
from verifirm.schema.signals import (
    AgentResult,
    Component,
    EntityMatch,
    Signal,
    SourceRef,
    SourceType,
)

log = get_logger(__name__)

EXACT = EntityMatch(method="cui_exact", score=1.0)
FOOTPRINT_SOURCE = "Public footprint (web, SEAP, Kohesio)"


def _statement(cui: str, year: int) -> Callable[[Any], Awaitable[Sourced[FinancialYear | None]]]:
    def call(adapter: Any) -> Awaitable[Sourced[FinancialYear | None]]:
        return cast(AnafBilantAdapter, adapter).get_year(cui, year)

    return call


@register_agent("presence")
class PresenceAgent(BaseAgent):
    component = Component.PRESENCE
    sources = ("web_search", "seap", "kohesio", "anaf_bilant")
    rules = RULES

    def __init__(self, config: PresenceConfig | None = None) -> None:
        self.config = config or load_config()

    async def run(self, ctx: AgentContext) -> AgentResult:
        cfg = self.config
        started = time.monotonic()
        name = ctx.identity.current_name
        checked: list[str] = []
        failed: list[str] = []
        notes: list[str] = []
        signals: list[Signal] = []

        def fail(source: str, reason: str) -> None:
            if source not in failed:
                failed.append(source)
            if source in checked:
                checked.remove(source)
            notes.append(f"{source}: {reason}")
            log.info("presence source not checked", extra={"source": source, "reason": reason})

        async def read[T](
            source: str, call: Callable[[Any], Awaitable[Sourced[T]]]
        ) -> Sourced[T] | None:
            try:
                result = await call(ctx.adapter(source))
            except SourceUnavailable as exc:
                fail(source, exc.reason)
                return None
            except NotImplementedError:
                fail(source, "adapter not implemented yet")
                return None
            if source not in failed and source not in checked:
                checked.append(source)
            if result.stale:
                notes.append(f"{source}: stale mirror copy (older than mirror_max_age_s)")
            return result

        def emit(
            rule_id: str,
            claim: str,
            source: SourceRef,
            conf: float,
            data: dict[str, Any],
            **kwargs: Any,
        ) -> None:
            facts = {"fictional": True, **data} if ctx.identity.fictional else data
            signals.append(
                self.signal(
                    ctx,
                    rule_id=rule_id,
                    claim=claim,
                    source=source,
                    evidence_date=None,
                    confidence=conf,
                    entity_match=EXACT,
                    data=facts,
                    **kwargs,
                )
            )

        # --- 1. The footprint, part by part.
        web = await read("web_search", lambda a: cast(TavilyWebSearch, a).footprint(ctx.cui, name))
        seap = await read("seap", lambda a: cast(SeapAdapter, a).contracts_for(ctx.cui))
        kohesio = await read(
            "kohesio", lambda a: cast(KohesioAdapter, a).projects_for(name, ctx.cui)
        )
        if web is None and seap is None and kohesio is None:
            notes.append("no footprint source could be read: nothing to conclude")
            return self.result(
                started=started,
                sources_checked=[],
                sources_failed=failed,
                signals=[],
                notes="; ".join(notes),
            )

        # --- 2. PRE-NO-FOOTPRINT-01: only when all four parts are known, plus the turnover.
        if web is not None and seap is not None and kohesio is not None:
            filed = await self._latest_turnover(ctx, read)
            footprint = {**web.data, "seap": seap.data, "kohesio": kohesio.data}
            if filed is None:
                notes.append("no filed statement found: turnover unknown, no footprint conclusion")
            else:
                gap = rules.check_no_footprint(filed.turnover, footprint, cfg.min_turnover_ron)
                if gap:
                    source = SourceRef(
                        name=FOOTPRINT_SOURCE,
                        type=SourceType.WEB,
                        retrieved_at=web.source.retrieved_at,
                        raw_ref=web.source.raw_ref,
                        content_hash=web.source.content_hash,
                    )
                    emit(
                        "PRE-NO-FOOTPRINT-01",
                        "No website, job postings, SEAP contracts or EU-funded projects were "
                        f"found despite {gap['turnover']:,} RON {filed.year} turnover.",
                        source,
                        cfg.no_footprint_confidence,
                        gap,
                    )
        else:
            notes.append("footprint incomplete: PRE-NO-FOOTPRINT-01 not concluded")

        # --- 3. PRE-ADDRESS-MISMATCH-01: the website's address vs the registered office.
        website = web.data.get("website") if web is not None else None
        office = ctx.identity.registered_office
        if web is not None and isinstance(website, dict) and office is not None:
            mismatch = rules.check_address_mismatch(
                website.get("address_on_site"), office.raw, cfg.address_min_similarity
            )
            if mismatch:
                emit(
                    "PRE-ADDRESS-MISMATCH-01",
                    f'The company website gives the address "{mismatch["website_address"]}", '
                    f'while ONRC lists "{mismatch["onrc_address"]}".',
                    web.source,
                    cfg.address_mismatch_confidence,
                    {**mismatch, "website": website.get("url")},
                    validated=False,
                )

        # --- 4. PRE-PUBLIC-CONTRACTS-01 (info): a positive, official footprint.
        public = rules.check_public_contracts(
            seap.data if seap else None, kohesio.data if kohesio else None
        )
        if public:
            official = seap if seap is not None and seap.data else kohesio
            assert official is not None
            parts = []
            if public["seap_contracts"]:
                parts.append(
                    f"{public['seap_contracts']} SEAP contract(s) worth "
                    f"{public['seap_value_ron']:,} RON"
                )
            if public["kohesio_projects"]:
                parts.append(
                    f"{public['kohesio_projects']} EU-funded project(s) with "
                    f"{public['eu_contribution_eur']:,} EUR EU contribution"
                )
            emit(
                "PRE-PUBLIC-CONTRACTS-01",
                f"The company has {' and '.join(parts)}.",
                official.source,
                1.0,
                public,
            )

        return self.result(
            started=started,
            sources_checked=checked,
            sources_failed=failed,
            signals=signals,
            notes="; ".join(notes) or None,
        )

    async def _latest_turnover(
        self,
        ctx: AgentContext,
        read: Callable[..., Awaitable[Sourced[FinancialYear | None] | None]],
    ) -> FinancialYear | None:
        """The most recent filed statement within `turnover_years_back` years (mirror only)."""
        this_year = ctx.clock.today().year
        for year in range(this_year - 1, this_year - 1 - self.config.turnover_years_back, -1):
            statement = await read("anaf_bilant", _statement(ctx.cui, year))
            if statement is not None and statement.data is not None:
                return statement.data
        return None
