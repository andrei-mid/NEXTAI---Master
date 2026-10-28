"""STUB. Owner: @role-3-official-agents. Identity agent.

Implement `run`:
1. Inputs: ctx.identity (already built from official sources by consolidation/identity_sheet),
   plus ctx.adapter("anaf_v9") and ctx.adapter("onrc_bulk") for details the sheet lacks
   (office-sharing count, CAEN authorization, reactivation dates).
2. Run every check in rules.py. Each hit -> self.signal(ctx, rule_id=..., claim=<one
   factual sentence>, source=<SourceRef from the adapter's Sourced>, evidence_date=...,
   confidence=..., entity_match=EntityMatch(method="cui_exact", score=1.0), data=<facts>).
3. Wrap every adapter call in try/except SourceUnavailable -> sources_failed.
4. Return self.result(...). Signals: ID-INACTIVE-01, ID-REACTIVATED-01, ID-ADMIN-CHANGE-01,
   ID-OFFICE-CHANGE-01, ID-SHARED-OFFICE-01, ID-CAEN-UNAUTH-01, ID-STATUS-01, ID-NATURAL-PERSON-01.
Demo: Zephyria -> ID-ADMIN-CHANGE-01 + ID-SHARED-OFFICE-01 (63 companies).
"""

from __future__ import annotations

from verifirm.agents.base import AgentContext, BaseAgent
from verifirm.agents.identity.rules import RULES
from verifirm.core.registry import register_agent
from verifirm.schema.signals import AgentResult, Component


@register_agent("identity")
class IdentityAgent(BaseAgent):
    component = Component.IDENTITY
    sources = ("anaf_v9", "onrc_bulk")
    rules = RULES

    async def run(self, ctx: AgentContext) -> AgentResult:
        raise NotImplementedError
