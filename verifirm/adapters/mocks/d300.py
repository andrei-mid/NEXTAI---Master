"""Owner: @role-3-official-agents. MOCK of D300 VAT returns (and SAF-T D406). The real ones need the
company's certificate.

Fixture: fixtures/companies/<cui>_<slug>/d300.json
  {"fictional": true, "cui": "...", "returns": [{"period": "2025-12", "taxable_base_ron": 0,
   "vat_collected_ron": 0, "vat_deductible_ron": 0}]}
Used by TAX-EFACTURA-GAP-01 (declared sales vs e-Factura issued totals).

Local-first (docs/LOCAL_DATA.md): mocks read fixtures/ only, in every mode. No sync, no network.
"""

from __future__ import annotations

from typing import Any

from verifirm.adapters.base import Sourced
from verifirm.adapters.mocks import MockAdapter
from verifirm.core.registry import register_adapter


@register_adapter("mock_d300")
class MockD300Adapter(MockAdapter):
    source_label = "D300 VAT returns (MOCK)"

    async def returns(self, cui: str) -> Sourced[list[dict[str, Any]]]:
        """The VAT returns, one per period ("2025-Q1" or "2025-03")."""
        result = await self.read_company(cui, "d300.json", {"returns": list})
        return Sourced(data=result.data["returns"], source=result.source)
