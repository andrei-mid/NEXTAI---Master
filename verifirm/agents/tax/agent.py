"""STUB. Owner: @role-3-official-agents. Tax agent.

Implement `run`:
1. Submitted vs official: ctx.submitted (SubmittedFinancials from adapters/documents, or None
   for portfolio re-checks) vs ctx.adapter("anaf_bilant"). Source of the gap signal: the
   OFFICIAL SourceRef. Put the submitted value in data["submitted"] and the official one in data["official"].
2. Arrears: ctx.adapter("mock_restante"). VAT history: ctx.adapter("anaf_v9").
   D300 vs e-Factura: ctx.adapter("mock_d300") + ctx.adapter("mock_efactura").
   Registration: ctx.adapter("anaf_efactura_registry").
3. MOCK sources produce signals whose source.type == MOCK (the UI shows a badge).
4. Rule ids: TAX-DECLARED-GAP-01, TAX-ARREARS-01, TAX-VAT-CANCELLED-01, TAX-EFACTURA-GAP-01, TAX-EFACTURA-REG-01.
Demo: Zephyria -> DECLARED-GAP (high). Brunaldo -> ARREARS, VAT-CANCELLED, EFACTURA-GAP, DECLARED-GAP.
"""

from __future__ import annotations

from verifirm.agents.base import AgentContext, BaseAgent
from verifirm.agents.tax.rules import RULES
from verifirm.core.registry import register_agent
from verifirm.schema.signals import AgentResult, Component


@register_agent("tax")
class TaxAgent(BaseAgent):
    component = Component.TAX
    sources = (
        "documents",
        "anaf_bilant",
        "anaf_v9",
        "mock_restante",
        "mock_d300",
        "mock_efactura",
        "anaf_efactura_registry",
    )
    rules = RULES

    async def run(self, ctx: AgentContext) -> AgentResult:
        raise NotImplementedError
