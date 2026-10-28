"""Owner: @role-3-official-agents. Financials agent: 5 years of ANAF /bilant.

Flow: expected last filed year (from ctx.clock + config) -> anaf_bilant history -> pure checks
in rules.py -> signals. Every signal's `data` carries the exact figures used, so the memo and
critic can quote them. Comparing against SUBMITTED figures is the tax agent's job
(TAX-DECLARED-GAP-01), not this one.

A year the source could not be read for -> `anaf_bilant` in sources_failed (PARTIAL, or
UNAVAILABLE if nothing could be read). Never reported as clean.
Demo: Zephyria -> NET-ASSETS (high), REVENUE-JUMP, HEADCOUNT. Brunaldo -> REVENUE-DECLINE,
LOSS-TREND. Aurora -> nothing.
"""

from __future__ import annotations

import time
from datetime import date
from typing import Any

from verifirm.adapters.anaf_bilant import AnafBilantAdapter, BilantHistory
from verifirm.adapters.base import SourceUnavailable
from verifirm.agents.base import AgentContext, BaseAgent
from verifirm.agents.financials import rules
from verifirm.agents.financials.rules import RULES, FinancialsConfig, load_config
from verifirm.core.registry import register_agent
from verifirm.schema.signals import AgentResult, Component, EntityMatch, Signal, SourceRef

SOURCE = "anaf_bilant"
EXACT = EntityMatch(method="cui_exact", score=1.0)


def _ron(value: int | None) -> str:
    return "n/a" if value is None else f"{value:,} RON"


@register_agent("financials")
class FinancialsAgent(BaseAgent):
    component = Component.FINANCIALS
    sources = (SOURCE,)
    rules = RULES

    def __init__(self, config: FinancialsConfig | None = None) -> None:
        self.config = config or load_config()

    async def run(self, ctx: AgentContext) -> AgentResult:
        started = time.monotonic()
        cfg = self.config
        today = ctx.clock.today()
        last_year = rules.expected_last_year(
            today.year, today.month, cfg.filing_available_from_month
        )

        try:
            adapter = ctx.adapter(SOURCE)
            assert isinstance(adapter, AnafBilantAdapter)
            history = await adapter.get_history(ctx.cui, last_year, cfg.years_of_history)
        except SourceUnavailable as exc:
            return self.result(
                started=started,
                sources_checked=[],
                sources_failed=[SOURCE],
                signals=[],
                notes=str(exc),
            )

        if not history.years:
            return self.result(
                started=started,
                sources_checked=[],
                sources_failed=[SOURCE],
                signals=[],
                notes=f"no year could be read ({last_year - cfg.years_of_history + 1}-{last_year})",
            )

        signals = self._signals(ctx, history, last_year)
        notes = f"years not readable: {history.failed}" if history.failed else None
        return self.result(
            started=started,
            sources_checked=[SOURCE],
            sources_failed=[SOURCE] if history.failed else [],
            signals=signals,
            notes=notes,
        )

    # ------------------------------------------------------------------ signals
    def _signals(self, ctx: AgentContext, history: BilantHistory, last_year: int) -> list[Signal]:
        cfg = self.config
        filed = history.filed
        out: list[Signal] = []

        def source_for(year: int) -> SourceRef:
            return history.years[year].source

        def emit(rule_id: str, claim: str, year: int, facts: dict[str, Any], **kw: Any) -> None:
            out.append(
                self.signal(
                    ctx,
                    rule_id=rule_id,
                    claim=claim,
                    source=source_for(year),
                    evidence_date=date(year, 12, 31),
                    confidence=kw.pop("confidence", 1.0),
                    entity_match=EXACT,
                    data=facts,
                    **kw,
                )
            )

        fetched = {y: s.data for y, s in history.years.items()}
        if (f := rules.check_no_filing(fetched, last_year)) is not None:
            emit(
                "FIN-NO-FILING-01",
                f"No financial statement was found at ANAF for {last_year}.",
                last_year,
                f,
                discriminator=str(last_year),
            )

        if not filed:
            return out
        latest = filed[-1]

        if (f := rules.check_net_assets(latest, cfg.net_assets)) is not None:
            emit(
                "FIN-NET-ASSETS-01",
                f"{f['year']} equity was {_ron(f['equity'])}, below half of the "
                f"{_ron(f['share_capital'])} share capital.",
                f["year"],
                f,
                discriminator=str(f["year"]),
            )

        if (f := rules.check_revenue_jump(filed, cfg.revenue_jump)) is not None:
            emit(
                "FIN-REVENUE-JUMP-01",
                f"Turnover grew from {_ron(f['from_turnover'])} in {f['from_year']} to "
                f"{_ron(f['to_turnover'])} in {f['to_year']} (+{f['growth_pct']}%).",
                f["to_year"],
                f,
                discriminator=f"{f['from_year']}-{f['to_year']}",
            )

        if (f := rules.check_headcount(latest, ctx.identity.caen_code, cfg.headcount)) is not None:
            emit(
                "FIN-HEADCOUNT-01",
                f"{f['year']} turnover of {_ron(f['turnover'])} was reported with {f['employees']} "
                f"employees ({_ron(f['turnover_per_employee'])} per employee, {f['ratio_to_avg']}x the "
                f"estimated CAEN {f['caen_division']} average).",
                f["year"],
                f,
                discriminator=str(f["year"]),
                confidence=cfg.headcount.confidence,
            )

        if (f := rules.check_loss_trend(filed, cfg.loss_trend)) is not None:
            losses = ", ".join(f"{y} ({_ron(v)})" for y, v in f["net_profit"].items())
            emit(
                "FIN-LOSS-TREND-01",
                f"Net losses in {f['years']} consecutive years: {losses}.",
                f["to_year"],
                f,
                discriminator=f"{f['from_year']}-{f['to_year']}",
            )

        if (f := rules.check_debt_rise(filed, cfg.debt_rise)) is not None:
            a, b = str(f["from_year"]), str(f["to_year"])
            emit(
                "FIN-DEBT-RISE-01",
                f"Debts rose from {_ron(f['debts'][a])} in {a} to {_ron(f['debts'][b])} in {b} "
                f"(+{f['debt_growth_pct']}%) while turnover changed by {f['turnover_growth_pct']}%.",
                f["to_year"],
                f,
                discriminator=f"{a}-{b}",
            )

        if (f := rules.check_revenue_decline(filed, cfg.revenue_decline)) is not None:
            a, b = str(f["from_year"]), str(f["to_year"])
            emit(
                "FIN-REVENUE-DECLINE-01",
                f"Turnover fell from {_ron(f['turnover'][a])} in {a} to {_ron(f['turnover'][b])} "
                f"in {b} ({f['change_pct']}%).",
                f["to_year"],
                f,
                discriminator=f"{a}-{b}",
            )
        return out
