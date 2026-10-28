"""STUB. Owner: @role-5-ai-api. Critic / verifier: rejects any memo sentence with a claim or number
that is not in the ConsolidatedReport.

Implement `verify_memo` in two passes:
1. Deterministic (no LLM, always runs): extract every number/date from each sentence
   (Romanian formats too: 1.900.000, 1,9 mil., 18%, 2025-11-02, 12.04.2026) and check that it
   appears in the cited signals' data/claim or in the score. Check that every cited signal_id
   exists. Any failure -> RejectedSentence.
2. LLM pass (prompts/critic.md, settings.model_for("critic")): per remaining sentence, "is
   every claim supported by the cited signals?" -> verdicts. Unsupported -> rejected.
Rejected sentences are REMOVED from the memo (demo step 5: "the critic removes an unsourced
sentence"). passed = no rejections. Return the cleaned Memo with verifier_report set.
"""

from __future__ import annotations

from verifirm.core.ports.llm import LLMClient
from verifirm.schema.memo import ConsolidatedReport, Memo


async def verify_memo(
    memo: Memo, report: ConsolidatedReport, llm: LLMClient | None, model: str
) -> Memo:
    raise NotImplementedError
