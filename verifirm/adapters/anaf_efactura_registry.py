"""STUB. Owner: @role-3-official-agents. Is the company enrolled in RO e-Factura? (OFFICIAL)

Facts / to confirm before implementing:
- The v9 VAT response already exposes `date_generale.statusRO_e_Factura` (bool), plus the
  registration date. Prefer deriving it from anaf_v9 (no extra call) if that is enough.
- If the separate "Registrul RO e-Factura" listing is needed, document its URL, auth and
  limits in docs/SOURCES.md first (open a PENDING entry in DECISIONS.md).
- This is NOT the invoices themselves. Invoices need the company's certificate -> mocks/efactura.py.

Local-first (docs/LOCAL_DATA.md): prefer deriving the answer from the anaf_v9 mirror entry (no extra download). If a separate source is needed, implement sync(cui) + a mirror-only READ method.
"""

from __future__ import annotations

from verifirm.adapters.base import BaseAdapter, Sourced
from verifirm.core.ports.rate_limiter import RateLimit
from verifirm.core.registry import register_adapter
from verifirm.schema.signals import SourceType


@register_adapter("anaf_efactura_registry")
class AnafEfacturaRegistryAdapter(BaseAdapter):
    source_label = "ANAF RO e-Factura registry"
    source_type = SourceType.OFFICIAL
    rate_limit = RateLimit.per_second(1)
    rate_limit_key = "anaf_webservicesp"

    async def is_registered(self, cui: str) -> Sourced[bool | None]:
        """True/False if known, None if the source does not say. Rule: TAX-EFACTURA-REG-01."""
        raise NotImplementedError
