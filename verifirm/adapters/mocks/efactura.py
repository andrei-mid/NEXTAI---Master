"""STUB. Owner: @role-3-official-agents. MOCK of RO e-Factura invoice flows (real one needs the
company's digital certificate).

Fixture: fixtures/companies/<cui>_<slug>/efactura.json
  {"fictional": true, "cui": "...", "period": {"from", "to"},
   "issued_total_ron": 0, "received_total_ron": 0,
   "flows": [{"from_cui", "to_cui", "total_ron", "n_invoices", "period"}]}
Used by TAX-EFACTURA-GAP-01 (vs D300) and NET-CIRCULAR-INVOICE-01 (cycles in `flows`).

Local-first (docs/LOCAL_DATA.md): mocks read fixtures/ only, in every mode. No sync, no network.
"""

from __future__ import annotations

from typing import Any

from verifirm.adapters.base import BaseAdapter, Sourced
from verifirm.core.registry import register_adapter
from verifirm.schema.signals import SourceType


@register_adapter("mock_efactura")
class MockEfacturaAdapter(BaseAdapter):
    source_label = "RO e-Factura invoices (MOCK)"
    source_type = SourceType.MOCK

    async def invoice_flows(self, cui: str) -> Sourced[dict[str, Any]]:
        raise NotImplementedError
