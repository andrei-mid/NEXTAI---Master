"""STUB. Owner: @role-3-official-agents. Financials agent.

Implement `run`:
1. ctx.adapter("anaf_bilant").get_history(cui, last_year=<latest expected filing year>, years=5).
   The filing deadline is end of May / June, so derive the expected last year from ctx.clock (configurable).
2. Run the checks in rules.py on the years that were filed. Every signal's `data` carries the
   exact figures used (year, value) so the memo/critic can quote them.
3. Comparing against SUBMITTED figures is the TAX agent's job (TAX-DECLARED-GAP-01), not this one.
4. Missing years -> FIN-NO-FILING-01 and notes. If the adapter fails, the source goes into sources_failed.
Demo: Zephyria -> REVENUE-JUMP, DEBT-RISE, HEADCOUNT, NET-ASSETS (high).
      Brunaldo -> REVENUE-DECLINE, LOSS-TREND, DEBT-RISE.
      Aurora -> nothing (steady growth).
"""

from __future__ import annotations

from verifirm.agents.base import AgentContext, BaseAgent
from verifirm.agents.financials.rules import RULES
from verifirm.core.registry import register_agent
from verifirm.schema.signals import AgentResult, Component


@register_agent("financials")
class FinancialsAgent(BaseAgent):
    component = Component.FINANCIALS
    sources = ("anaf_bilant",)
    rules = RULES

    async def run(self, ctx: AgentContext) -> AgentResult:
        raise NotImplementedError
