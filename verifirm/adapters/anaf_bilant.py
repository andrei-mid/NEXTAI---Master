"""STUB. Owner: @role-3-official-agents. ANAF annual financial statements (OFFICIAL, free).

Facts:
- GET https://webservicesp.anaf.ro/bilant?an={year}&cui={cui}
- One CUI-year per call. Max 1 request/second (shares the webservicesp.anaf.ro limit).
- Response: {"an", "cui", "deni", "caen", "den_caen", "i": [{"indicator": "I1",
  "val_indicator": 123, "val_den_indicator": "Active imobilizate - total"}, ...]}
- Map indicators BY LABEL (`val_den_indicator`), NOT by code: the I-codes differ between
  company types (large/small/micro, banks, NGOs) and between years.
- Labels to map into FinancialYear (match case/diacritics-insensitively, keep the label table
  in this module): "Cifra de afaceri neta" -> turnover, "Profit net"/"Pierdere neta" ->
  net_profit (loss is negative), "Datorii" -> total_debts, "Capitaluri - total" -> equity,
  "Capital subscris varsat" -> share_capital, "Numar mediu de salariati" -> employees.
  Put everything else in FinancialYear.extra by label.
- An empty `i` list means "no statement filed for that year". That is NOT zero turnover.
- Fixture: fixtures/companies/<cui>_<slug>/bilant_<year>.json, the exact response shape.
"""

from __future__ import annotations

from verifirm.adapters.base import BaseAdapter, Sourced
from verifirm.core.ports.rate_limiter import RateLimit
from verifirm.core.registry import register_adapter
from verifirm.schema.financials import FinancialYear
from verifirm.schema.signals import SourceType

URL = "https://webservicesp.anaf.ro/bilant"


@register_adapter("anaf_bilant")
class AnafBilantAdapter(BaseAdapter):
    source_label = "ANAF financial statements (bilanț)"
    source_type = SourceType.OFFICIAL
    rate_limit = RateLimit.per_second(1)
    rate_limit_key = "anaf_webservicesp"
    cache_ttl_s = 7 * 86_400  # statements change rarely

    async def get_year(self, cui: str, year: int) -> Sourced[FinancialYear | None]:
        """One year. None if nothing was filed. Fixture: bilant_<year>.json."""
        raise NotImplementedError

    async def get_history(
        self, cui: str, last_year: int, years: int = 5
    ) -> list[Sourced[FinancialYear | None]]:
        """`years` consecutive years ending at `last_year`, oldest first (5 calls, rate limited)."""
        raise NotImplementedError
