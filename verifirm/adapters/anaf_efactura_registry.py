"""Is the company enrolled in RO e-Factura? (OFFICIAL) Owner: @role-3-official-agents.

Derived from the ANAF v9 record (`date_generale.statusRO_e_Factura`), so there is NO extra
call and NO sync of its own: anaf_v9's sync / sweep already put the record in the mirror.
- This is NOT the invoices themselves. Invoices need the company's certificate -> mocks/efactura.py.
- e-Factura is mandatory for B2B invoices since 2024, so "not enrolled" is unusual. What the
  v9 flag still means after the mandate is TO VERIFY on live data (docs/SOURCES.md).
"""

from __future__ import annotations

from verifirm.adapters.anaf_v9 import AnafV9Adapter
from verifirm.adapters.base import BaseAdapter, Sourced
from verifirm.core.registry import register_adapter
from verifirm.schema.signals import SourceType


@register_adapter("anaf_efactura_registry")
class AnafEfacturaRegistryAdapter(BaseAdapter):
    source_label = "ANAF RO e-Factura registry"
    source_type = SourceType.OFFICIAL

    async def is_registered(self, cui: str) -> Sourced[bool | None]:
        """True/False if v9 says so, None if v9 doesn't publish the flag or the CUI is notFound.
        SourceUnavailable when the v9 entry can't be read. Rule: TAX-EFACTURA-REG-01."""
        v9 = await AnafV9Adapter(self.deps).lookup(cui, self.deps.clock.today())
        flag = (v9.data or {}).get("date_generale", {}).get("statusRO_e_Factura")
        registered = flag if isinstance(flag, bool) else None
        return Sourced(data=registered, source=v9.source, stale=v9.stale)
