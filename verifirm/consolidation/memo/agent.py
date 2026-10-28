"""STUB. Owner: @role-5-ai-api. Memo agent: writes ONLY from the ConsolidatedReport JSON.

Implement `write_memo`:
- Input: ConsolidatedReport (identity, resolved signals, score, coverage). Nothing else.
- LLM via verifirm.llm.json_output -> MemoDraft (sections + questions). Prompt: prompts/memo.md.
  Model: settings.model_for("memo").
- Sections: summary, red signals (high/critical), yellow signals (medium/low), coverage
  (unavailable / timed-out sources, MOCK sources used), next steps.
- Every sentence lists the signal_ids it is based on. Unvalidated (media) claims are labelled
  "unvalidated". Numbers are copied from signal.data, never computed by the model.
- Questions to ask the client, each tied to signal ids (e.g. Brunaldo: ask for a tax compliance
  certificate (certificat de atestare fiscală). Explain that the band becomes STOP if insolvency is opened).
- The memo NEVER recommends approve/reject. The analyst decides.
- Render markdown from sections AFTER the critic pass (critic/agent.py), not before.
"""

from __future__ import annotations

from pydantic import BaseModel

from verifirm.core.ports.llm import LLMClient
from verifirm.schema.memo import ClientQuestion, ConsolidatedReport, Memo, MemoSection


class MemoDraft(BaseModel):
    """LLM output schema."""

    sections: list[MemoSection]
    questions: list[ClientQuestion]


async def write_memo(report: ConsolidatedReport, llm: LLMClient, model: str) -> Memo:
    raise NotImplementedError


def render_markdown(memo: Memo) -> str:
    """Deterministic markdown rendering of the sections + questions (no LLM)."""
    raise NotImplementedError
