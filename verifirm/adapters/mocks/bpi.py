"""Owner: @role-3-official-agents. MOCK of BPI, the Insolvency Proceedings Bulletin (real one is paid).

Fixture: fixtures/companies/<cui>_<slug>/bpi.json
  {"fictional": true, "cui": "...", "proceedings": [{"case_no", "court", "type":
   "insolventa"|"faliment"|"reorganizare", "opened_on", "status", "publication_no"}]}
An opened procedure feeds LIT-INSOLVENCY-OPENED-01 (auto-stop).
A REQUEST to open (not yet opened) is NOT here. It comes from the court case (LIT-INSOLVENCY-REQUEST-01).

Local-first (docs/LOCAL_DATA.md): mocks read fixtures/ only, in every mode. No sync, no network.
"""

from __future__ import annotations

from typing import Any

from verifirm.adapters.base import Sourced
from verifirm.adapters.mocks import MockAdapter
from verifirm.core.registry import register_adapter


@register_adapter("mock_bpi")
class MockBpiAdapter(MockAdapter):
    source_label = "BPI insolvency bulletin (MOCK)"

    async def proceedings(self, cui: str) -> Sourced[list[dict[str, Any]]]:
        """Published insolvency proceedings (empty list = checked, none published)."""
        result = await self.read_company(cui, "bpi.json", {"proceedings": list})
        return Sourced(data=result.data["proceedings"], source=result.source)
