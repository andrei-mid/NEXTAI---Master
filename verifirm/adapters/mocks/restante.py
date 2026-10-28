"""STUB. Owner: @role-3-official-agents. MOCK of ANAF's quarterly list of tax arrears (real one is behind a captcha).

Fixture: fixtures/companies/<cui>_<slug>/restante.json
  {"fictional": true, "cui": "...", "list_period": "2026-Q2",
   "obligations": [{"type": "principal"|"accesorii", "amount_ron": 0}]}
A file with an empty `obligations` list = checked and clean. A missing file = UNAVAILABLE.
Feeds TAX-ARREARS-01.

Local-first (docs/LOCAL_DATA.md): mocks read fixtures/ only, in every mode. No sync, no network.
"""

from __future__ import annotations

from typing import Any

from verifirm.adapters.base import BaseAdapter, Sourced
from verifirm.core.registry import register_adapter
from verifirm.schema.signals import SourceType


@register_adapter("mock_restante")
class MockRestanteAdapter(BaseAdapter):
    source_label = "ANAF tax arrears list (MOCK)"
    source_type = SourceType.MOCK

    async def arrears(self, cui: str) -> Sourced[dict[str, Any]]:
        raise NotImplementedError
