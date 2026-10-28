"""Owner: @role-3-official-agents. MOCK of shareholders (ONRC open data has none. The real
source is a paid ONRC extract).

Fixture: fixtures/companies/<cui>_<slug>/shareholders.json
  {"fictional": true, "cui": "...", "shareholders": [{"name", "is_company", "cui",
   "share_pct", "since"}]}
Becomes IdentitySheet.shareholders (Person.source.type == MOCK). Feeds NET-PARTNER-INACTIVE-01.

Local-first (docs/LOCAL_DATA.md): mocks read fixtures/ only, in every mode. No sync, no network.
"""

from __future__ import annotations

from typing import Any

from verifirm.adapters.base import Sourced
from verifirm.adapters.mocks import MockAdapter
from verifirm.core.registry import register_adapter


@register_adapter("mock_shareholders")
class MockShareholdersAdapter(MockAdapter):
    source_label = "Shareholders (MOCK)"

    async def shareholders(self, cui: str) -> Sourced[list[dict[str, Any]]]:
        """[{name, is_company, cui, share_pct, since}]."""
        result = await self.read_company(cui, "shareholders.json", {"shareholders": list})
        return Sourced(data=result.data["shareholders"], source=result.source)
