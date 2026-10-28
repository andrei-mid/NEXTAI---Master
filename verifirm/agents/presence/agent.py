"""STUB. Owner: @role-4-external-agents. Public-footprint agent.

Implement `run`:
1. Footprint: website (search ctx.web_search for the official site and check the domain mentions the
   CUI/name), job postings (web search), ctx.adapter("seap").contracts_for(cui),
   ctx.adapter("kohesio").projects_for(name, cui).
   Fixture mode: fixtures/companies/<cui>_<slug>/presence.json holds all four parts.
2. Turnover for PRE-NO-FOOTPRINT-01 comes from ctx.adapter("anaf_bilant") (the latest year).
   Agents never import other agents.
3. Website/job evidence is WEB (validated=False). SEAP/Kohesio evidence is OFFICIAL.
Demo: Zephyria -> PRE-NO-FOOTPRINT-01. Aurora -> website + jobs (no signal).
"""

from __future__ import annotations

from verifirm.agents.base import AgentContext, BaseAgent
from verifirm.agents.presence.rules import RULES
from verifirm.core.registry import register_agent
from verifirm.schema.signals import AgentResult, Component


@register_agent("presence")
class PresenceAgent(BaseAgent):
    component = Component.PRESENCE
    sources = ("web_search", "seap", "kohesio", "anaf_bilant")
    rules = RULES

    async def run(self, ctx: AgentContext) -> AgentResult:
        raise NotImplementedError
