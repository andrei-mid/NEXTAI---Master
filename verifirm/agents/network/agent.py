"""STUB. Owner: @role-3-official-agents. Network agent (administrators -> their other companies).

Implement `run`:
1. For each administrator in ctx.identity (current AND recent former):
   ctx.adapter("onrc_bulk").companies_of_person(name) -> affiliates. Matching is by person
   name only, so use EntityMatch(method="person_name", score, ambiguous=True when the name is
   common or county differs).
2. Status of each affiliate: anaf_v9 (inactive), onrc_bulk (deregistered), mock_bpi (insolvency).
   Cap the fan-out (config: max affiliates, depth 1 for signals; depth 2 only for the graph).
3. Circular invoicing: ctx.adapter("mock_efactura").invoice_flows(cui) -> rules.find_invoice_cycles.
4. Partners: ctx.identity.shareholders (MOCK) -> status lookup -> NET-PARTNER-INACTIVE-01.
5. Put the graph (nodes/edges) in the signal data so GET /companies/{cui}/graph can render it
   (schema.api.Graph shape).
Demo: Zephyria -> SERIAL-ADMIN (4 failed affiliates), CIRCULAR-INVOICE (2.1M), PARTNER-INACTIVE.
      Brunaldo -> PARTNER-INACTIVE (Calbrona).
"""

from __future__ import annotations

from verifirm.agents.base import AgentContext, BaseAgent
from verifirm.agents.network.rules import RULES
from verifirm.core.registry import register_agent
from verifirm.schema.signals import AgentResult, Component


@register_agent("network")
class NetworkAgent(BaseAgent):
    component = Component.NETWORK
    sources = ("onrc_bulk", "anaf_v9", "mock_bpi", "mock_efactura", "mock_shareholders")
    rules = RULES

    async def run(self, ctx: AgentContext) -> AgentResult:
        raise NotImplementedError
