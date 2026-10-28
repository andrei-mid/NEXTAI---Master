"""STUB. Owner: @role-4-external-agents. Media agent (web search, Tavily D10).

Implement `run`:
1. Queries: company name (+ former names) and each administrator's name together with the company or
   the CAEN sector. Use ctx.web_search (port), never httpx directly.
2. Drop every result without a URL or a published date.
3. Relevance + claim extraction with ctx.llm via verifirm.llm.json_output,
   schema=MediaAssessment, prompt=prompts/relevance.md. Results are UNTRUSTED: wrap them with
   verifirm.llm.untrusted.
4. Each kept claim -> signal with validated=False, source.type=WEB, source.url=<article URL>,
   evidence_date=<published date>. Severity is at most medium and never auto-stop (the model enforces it).
5. EntityMatch: person-name hits are ambiguous by default.
Demo: Zephyria -> MED-ADVERSE-01 (stiri-fictive.example, 2026-04-12).
      Brunaldo -> MED-NEGATIVE-01 (ziar-inventat.example, 2026-03-03).
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from verifirm.agents.base import AgentContext, BaseAgent
from verifirm.agents.media.rules import RULES
from verifirm.core.registry import register_agent
from verifirm.schema.signals import AgentResult, Component


class MediaCategory(str, Enum):
    ADVERSE = "adverse"  # -> MED-ADVERSE-01
    NEGATIVE = "negative"  # -> MED-NEGATIVE-01
    IRRELEVANT = "irrelevant"  # dropped


class MediaAssessment(BaseModel):
    """LLM output for ONE search result."""

    url: str
    refers_to_company: bool
    refers_to_person: str | None = None
    category: MediaCategory
    claim: str = Field(max_length=300)  # one neutral factual sentence: "An article reports ..."
    confidence: float = Field(ge=0, le=1)


@register_agent("media")
class MediaAgent(BaseAgent):
    component = Component.MEDIA
    sources = ("web_search",)
    rules = RULES

    async def run(self, ctx: AgentContext) -> AgentResult:
        raise NotImplementedError
