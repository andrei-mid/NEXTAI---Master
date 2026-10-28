"""STUB. Owner: @role-3-official-agents. MOCK of shareholders (ONRC open data has none. The real
source is a paid ONRC extract).

Fixture: fixtures/companies/<cui>_<slug>/shareholders.json
  {"fictional": true, "cui": "...", "shareholders": [{"name", "is_company", "cui",
   "share_pct", "since"}]}
Becomes IdentitySheet.shareholders (Person.source.type == MOCK). Feeds NET-PARTNER-INACTIVE-01.

Local-first (docs/LOCAL_DATA.md): mocks read fixtures/ only, in every mode. No sync, no network.
"""

from __future__ import annotations

from typing import Any

from verifirm.adapters.base import BaseAdapter, Sourced
from verifirm.core.registry import register_adapter
from verifirm.schema.signals import SourceType


@register_adapter("mock_shareholders")
class MockShareholdersAdapter(BaseAdapter):
    source_label = "Shareholders (MOCK)"
    source_type = SourceType.MOCK

    async def shareholders(self, cui: str) -> Sourced[list[dict[str, Any]]]:
        raise NotImplementedError
