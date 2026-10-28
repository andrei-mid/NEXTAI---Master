"""STUB. Owner: @role-4-external-agents. EU Financial Sanctions Files (FSF) consolidated list (OFFICIAL).

Facts:
- Discover the CURRENT file URL at runtime from the RSS feed:
  https://webgate.ec.europa.eu/fsd/fsf/public/rss (the file link contains a token; never
  hard-code it).
- Bulk: download the whole list on a schedule (jobs/ingest_sanctions.py), normalize it into
  entries, store locally, and re-screen the portfolio when it changes (change detection).
- Fixture: fixtures/sources/sanctions/eu_fsf_sample.xml (fictional entries only).
"""

from __future__ import annotations

from typing import Any

from verifirm.adapters.base import BaseAdapter, Sourced
from verifirm.core.registry import register_adapter
from verifirm.schema.signals import SourceType

RSS_URL = "https://webgate.ec.europa.eu/fsd/fsf/public/rss"


@register_adapter("sanctions_eu")
class SanctionsEuAdapter(BaseAdapter):
    source_label = "EU Financial Sanctions (FSF)"
    source_type = SourceType.OFFICIAL
    cache_ttl_s = 86_400

    async def download_entries(self) -> Sourced[list[dict[str, Any]]]:
        """RSS -> file URL -> XML -> normalized entries:
        {list: "EU", entity_type: "person"|"entity", names: [...], aliases: [...],
         birth_dates: [...], countries: [...], identifiers: [...], programme, listed_on, ref}."""
        raise NotImplementedError
