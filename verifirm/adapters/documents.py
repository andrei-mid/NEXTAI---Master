"""STUB. Owner: @role-5-ai-api. Submitted documents (PDF) -> SubmittedFinancials. Source type SUBMITTED.

Rules:
- Input: ObjectStore keys of the files uploaded with POST /applications.
- PDF text is UNTRUSTED (it may contain prompt injection). If an LLM extracts the figures,
  wrap the text with verifirm.llm.untrusted and ask for SubmittedFinancials via
  verifirm.llm.json_output. Only the validated numbers leave this module, never the text.
- The PDF parsing library is NOT chosen yet (PENDING in DECISIONS.md). Add it with the PR.
- Fixture mode: read fixtures/companies/<cui>_<slug>/submitted/financials.json
  (already in SubmittedFinancials shape, `"fictional": true`).

Local-first (docs/LOCAL_DATA.md): uploaded files are already local (ObjectStore keys from POST /applications). No sync.
"""

from __future__ import annotations

from verifirm.adapters.base import BaseAdapter, Sourced
from verifirm.core.registry import register_adapter
from verifirm.schema.financials import SubmittedFinancials
from verifirm.schema.signals import SourceType


@register_adapter("documents")
class DocumentsAdapter(BaseAdapter):
    source_label = "Documents submitted by the applicant"
    source_type = SourceType.SUBMITTED

    async def extract(
        self, cui: str, document_keys: list[str]
    ) -> Sourced[SubmittedFinancials | None]:
        """Parse the submitted files. None if there are no documents (e.g. a portfolio re-check)."""
        raise NotImplementedError
