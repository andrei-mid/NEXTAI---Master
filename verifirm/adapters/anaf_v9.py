"""STUB. Owner: @role-3-official-agents. ANAF VAT registry web service, version 9 (OFFICIAL, free).

Facts:
- POST https://webservicesp.anaf.ro/api/PlatitorTvaRest/v9/tva
- Body: [{"cui": 123, "data": "YYYY-MM-DD"}, ...]. The CUI is an int, the date is the reference date.
- Max 100 CUIs per request. Max 1 request/second (declared below, enforced globally).
- Response: {"found": [...], "notFound": [...]}. Each found item has `date_generale`
  (denumire, adresa, nrRegCom, cod_CAEN, forma_juridica, stare_inregistrare,
  statusRO_e_Factura, ...), `inregistrare_scop_Tva` (scpTVA + perioade_TVA history),
  `stare_inactiv` (statusInactivi, dataInactivare, dataReactivare, dataRadiere),
  `inregistrare_RTVAI`, `adresa_sediu_social`, `adresa_domiciliu_fiscal`.
- There is NO cod/message wrapper on live 200 responses. Don't expect one.
- Fixture: fixtures/companies/<cui>_<slug>/anaf_v9.json, the exact response shape.

Used by: identity sheet (official), identity agent (inactive/reactivated), tax agent
(VAT cancelled), and the background sweep (batches of 100: cheap change detection).

Local-first (docs/LOCAL_DATA.md): batch per company: the sweep_anaf_v9 job downloads 100 CUIs per call and calls store_in_mirror(f"{cui}:{date}", <that company's found[] record>) once per CUI. sync(cui) downloads a single applicant. READ methods (lookup) never call ANAF.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from verifirm.adapters.base import BaseAdapter, Sourced
from verifirm.core.ports.rate_limiter import RateLimit
from verifirm.core.registry import register_adapter
from verifirm.schema.signals import SourceType

URL = "https://webservicesp.anaf.ro/api/PlatitorTvaRest/v9/tva"
MAX_BATCH = 100


@register_adapter("anaf_v9")
class AnafV9Adapter(BaseAdapter):
    source_label = "ANAF VAT registry v9"
    source_type = SourceType.OFFICIAL
    rate_limit = RateLimit.per_second(1)
    rate_limit_key = "anaf_webservicesp"  # same host as /bilant, so they share one limit

    async def lookup(self, cui: str, on_date: date) -> Sourced[dict[str, Any] | None]:
        """One company: the `found[0]` record, or None if ANAF lists it in `notFound`.

        Implement via `lookup_batch([cui], on_date)`.
        """
        raise NotImplementedError

    async def lookup_batch(
        self, cuis: list[str], on_date: date
    ) -> Sourced[dict[str, dict[str, Any] | None]]:
        """Up to 100 CUIs per call -> {cui: found record or None}.

        - Split into chunks of MAX_BATCH. Each chunk is one `self.fetch(...)` (rate limit,
          cache, retry and archive all come from BaseAdapter).
        - cache_key = f"{sorted cuis}:{on_date}". fixture = self.company_fixture(cui, "anaf_v9.json")
          (for batches in fixture mode, merge the per-company fixtures).
        - Never treat a missing response as "not inactive". Raise SourceUnavailable instead.
        """
        raise NotImplementedError
