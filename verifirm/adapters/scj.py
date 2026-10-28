"""STUB. Owner: @role-4-external-agents. High Court of Cassation and Justice (ICCJ) cases (OFFICIAL).

Facts:
- JSON API: http://api.scj.ro:97/api/CautareDosare
- AVAILABLE ONLY BETWEEN 03:30 AND 06:30 (Romania time). So: a nightly batch job queries
  every portfolio company + pending applicants inside the window, and results go to the cache
  with a long TTL. Agents ONLY read the cached result. Outside the window, a cache miss is
  reported as UNAVAILABLE (never clean).
- Fixture: fixtures/companies/<cui>_<slug>/scj.json (absent = no ICCJ cases in fixture mode).
"""

from __future__ import annotations

from typing import Any

from verifirm.adapters.base import BaseAdapter, Sourced
from verifirm.core.ports.rate_limiter import RateLimit
from verifirm.core.registry import register_adapter
from verifirm.schema.signals import SourceType

URL = "http://api.scj.ro:97/api/CautareDosare"
WINDOW = ("03:30", "06:30")  # Europe/Bucharest


@register_adapter("scj")
class ScjAdapter(BaseAdapter):
    source_label = "ICCJ (scj.ro)"
    source_type = SourceType.OFFICIAL
    rate_limit = RateLimit.per_second(1)  # PROPOSAL
    cache_ttl_s = 3 * 86_400

    def in_window(self) -> bool:
        """True if now (self.deps.clock, Europe/Bucharest) is inside WINDOW."""
        raise NotImplementedError

    async def search_cases(self, party_name: str) -> Sourced[list[dict[str, Any]]]:
        """Cached read for agents. Outside the window: cache only, else SourceUnavailable."""
        raise NotImplementedError

    async def nightly_refresh(self, party_names: list[str]) -> int:
        """Called by the scheduler inside the window. Refresh the cache, return the count refreshed."""
        raise NotImplementedError
