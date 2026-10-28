"""STUB. Owner: @role-3-official-agents. MOCK of D300 VAT returns (and SAF-T D406). The real ones need the
company's certificate.

Fixture: fixtures/companies/<cui>_<slug>/d300.json
  {"fictional": true, "cui": "...", "returns": [{"period": "2025-12", "taxable_base_ron": 0,
   "vat_collected_ron": 0, "vat_deductible_ron": 0}]}
Used by TAX-EFACTURA-GAP-01 (declared sales vs e-Factura issued totals).
"""

from __future__ import annotations

from typing import Any

from verifirm.adapters.base import BaseAdapter, Sourced
from verifirm.core.registry import register_adapter
from verifirm.schema.signals import SourceType


@register_adapter("mock_d300")
class MockD300Adapter(BaseAdapter):
    source_label = "D300 VAT returns (MOCK)"
    source_type = SourceType.MOCK

    async def returns(self, cui: str) -> Sourced[list[dict[str, Any]]]:
        raise NotImplementedError
