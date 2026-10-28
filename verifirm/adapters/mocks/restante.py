"""Owner: @role-3-official-agents. MOCK of ANAF's quarterly list of tax arrears (real one is behind a captcha).

Fixture: fixtures/companies/<cui>_<slug>/restante.json
  {"fictional": true, "cui": "...", "list_period": "2026-Q2",
   "obligations": [{"type": "principal"|"accesorii", "amount_ron": 0}]}
A file with an empty `obligations` list = checked and clean. A missing file = UNAVAILABLE.
Feeds TAX-ARREARS-01.

Local-first (docs/LOCAL_DATA.md): mocks read fixtures/ only, in every mode. No sync, no network.
"""

from __future__ import annotations

from typing import Any, cast

from verifirm.adapters.base import Sourced
from verifirm.adapters.mocks import MockAdapter
from verifirm.core.registry import register_adapter


@register_adapter("mock_restante")
class MockRestanteAdapter(MockAdapter):
    source_label = "ANAF tax arrears list (MOCK)"

    async def arrears(self, cui: str) -> Sourced[dict[str, Any]]:
        """The company's entry in the latest list (empty `obligations` = checked, clean).
        Optional `on_white_list` (bool): ANAF's list of companies WITHOUT arrears."""
        result = await self.read_company(
            cui, "restante.json", {"list_period": str, "obligations": list}
        )
        return cast(Sourced[dict[str, Any]], result)
