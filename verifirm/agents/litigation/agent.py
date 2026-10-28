"""STUB. Owner: @role-4-external-agents. Litigation agent.

Implement `run`:
1. Cases: ctx.adapter("portal_just").search_cases(<every current + historical name>) and
   ctx.adapter("scj").search_cases(...) (cached nightly batch only). Insolvency status:
   ctx.adapter("mock_bpi").proceedings(cui).
2. Parties have NO CUI: keep only cases whose party name matches a company name. Set
   EntityMatch(method="name+county" or "name_fuzzy", score, ambiguous) honestly.
3. Classify each case with ctx.llm via verifirm.llm.json_output, schema=CaseClassification,
   prompt=prompts/classify_case.md. Case text is UNTRUSTED: wrap it with verifirm.llm.untrusted.
   If ctx.llm is None or fails -> fall back to keyword rules and lower the confidence. Never drop a case.
4. rules.rule_for_case(...) -> signals. Put case_no, court, stage and next hearing in data.
5. Portal Just's 1,000-result cap reached -> PARTIAL + notes.
Demo: Brunaldo -> INSOLVENCY-REQUEST (high, NOT stop), MATERIAL-CLAIM, MINOR.
      Pelinor (affiliate) -> INSOLVENCY-OPENED in its own fixture (used by the network agent).
"""

from __future__ import annotations

from verifirm.agents.base import AgentContext, BaseAgent
from verifirm.agents.litigation.rules import RULES
from verifirm.core.registry import register_agent
from verifirm.schema.signals import AgentResult, Component


@register_agent("litigation")
class LitigationAgent(BaseAgent):
    component = Component.LITIGATION
    sources = ("portal_just", "scj", "mock_bpi")
    rules = RULES

    async def run(self, ctx: AgentContext) -> AgentResult:
        raise NotImplementedError
