"""STUB. Owner: @role-3-official-agents. MOCK of BPI, the Insolvency Proceedings Bulletin (real one is paid).

Fixture: fixtures/companies/<cui>_<slug>/bpi.json
  {"fictional": true, "cui": "...", "proceedings": [{"case_no", "court", "type":
   "insolventa"|"faliment"|"reorganizare", "opened_on", "status", "publication_no"}]}
An opened procedure feeds LIT-INSOLVENCY-OPENED-01 (auto-stop).
A REQUEST to open (not yet opened) is NOT here. It comes from the court case (LIT-INSOLVENCY-REQUEST-01).
"""

from __future__ import annotations

from typing import Any

from verifirm.adapters.base import BaseAdapter, Sourced
from verifirm.core.registry import register_adapter
from verifirm.schema.signals import SourceType


@register_adapter("mock_bpi")
class MockBpiAdapter(BaseAdapter):
    source_label = "BPI insolvency bulletin (MOCK)"
    source_type = SourceType.MOCK

    async def proceedings(self, cui: str) -> Sourced[list[dict[str, Any]]]:
        raise NotImplementedError
