"""STUB. Owner: @role-4-external-agents. Public procurement contracts won (SEAP / e-licitatie.ro) (OFFICIAL).

Facts / to confirm:
- Bulk-first: the procurement open-data exports (contracts / direct awards) are published
  on data.gov.ro. Ingest them on a schedule and look up by supplier CUI locally.
  Confirm the dataset URLs and columns, then record them in docs/SOURCES.md.
- Fixture: fixtures/companies/<cui>_<slug>/presence.json -> key "seap".

Local-first (docs/LOCAL_DATA.md): bulk: an ingest job (to add) loads the procurement exports locally. sync() no-op. contracts_for() reads local data only.
"""

from __future__ import annotations

from typing import Any

from verifirm.adapters.base import BaseAdapter, Sourced
from verifirm.core.registry import register_adapter
from verifirm.schema.signals import SourceType


@register_adapter("seap")
class SeapAdapter(BaseAdapter):
    source_label = "SEAP public procurement"
    source_type = SourceType.OFFICIAL
    mirror_max_age_s = 7 * 86_400

    async def contracts_for(self, cui: str) -> Sourced[list[dict[str, Any]]]:
        """Contracts where the company is the supplier: {authority, date, value_ron, cpv, ref}."""
        raise NotImplementedError
