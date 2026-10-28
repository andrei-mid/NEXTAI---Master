"""STUB. Owner: @role-4-external-agents. Sanctions + PEP screening agent.

Implement `run`:
1. Names to screen: company current + historical names, every administrator, mock shareholders.
2. Entries: the locally ingested EU FSF, UN and OFAC lists (bulk, jobs/ingest_sanctions.py).
   In fixture mode: fixtures/sources/sanctions/*. PEP: ctx.adapter("mock_pep").
3. matching.best_matches(...) -> rules.classify_match(...). Only a CONFIRMED match is an
   auto-stop candidate. Possible matches are medium and go to human review.
4. Sanctions must be AVAILABLE for GREEN. If any list can't be read, put it in sources_failed (never clean).
Demo: no sanctions hits for any demo company (all lists screened -> OK with 0 signals).
"""

from __future__ import annotations

from verifirm.agents.base import AgentContext, BaseAgent
from verifirm.agents.sanctions.rules import RULES
from verifirm.core.registry import register_agent
from verifirm.schema.signals import AgentResult, Component


@register_agent("sanctions")
class SanctionsAgent(BaseAgent):
    component = Component.SANCTIONS
    sources = ("sanctions_eu", "sanctions_un", "sanctions_ofac", "mock_pep")
    rules = RULES

    async def run(self, ctx: AgentContext) -> AgentResult:
        raise NotImplementedError
