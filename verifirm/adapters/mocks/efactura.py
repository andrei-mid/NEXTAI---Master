"""Owner: @role-3-official-agents. MOCK of RO e-Factura invoice flows (real one needs the
company's digital certificate).

Fixture: fixtures/companies/<cui>_<slug>/efactura.json
  {"fictional": true, "cui": "...", "period": {"from", "to"},
   "issued_total_ron": 0, "received_total_ron": 0,
   "flows": [{"from_cui", "to_cui", "total_ron", "n_invoices", "period"}]}
Used by TAX-EFACTURA-GAP-01 (vs D300) and NET-CIRCULAR-INVOICE-01 (cycles in `flows`).

Local-first (docs/LOCAL_DATA.md): mocks read fixtures/ only, in every mode. No sync, no network.
"""

from __future__ import annotations

from typing import Any, cast

from verifirm.adapters.base import Sourced
from verifirm.adapters.mocks import MockAdapter
from verifirm.core.registry import register_adapter


@register_adapter("mock_efactura")
class MockEfacturaAdapter(MockAdapter):
    source_label = "RO e-Factura invoices (MOCK)"

    async def invoice_flows(self, cui: str) -> Sourced[dict[str, Any]]:
        """Totals issued / received over `period`, plus the company-to-company `flows`."""
        result = await self.read_company(
            cui,
            "efactura.json",
            {"period": dict, "issued_total_ron": int, "received_total_ron": int, "flows": list},
        )
        return cast(Sourced[dict[str, Any]], result)
