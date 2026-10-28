"""Owner: @role-4-external-agents. EU cohesion-funds beneficiaries (Kohesio, European Commission).

Facts / to confirm:
- https://kohesio.ec.europa.eu publishes projects and beneficiaries (API + bulk exports).
  Prefer the bulk export filtered to Romania, ingested on a schedule. Confirm the endpoint and
  licence, then record them in docs/SOURCES.md.
- Beneficiaries are matched by name (plus the CUI when present), so return match info.
- Fixture: fixtures/companies/<cui>_<slug>/presence.json -> key "kohesio".

Local-first (docs/LOCAL_DATA.md): bulk: an ingest job (to add) loads the beneficiaries export locally. sync() no-op. projects_for() reads local data only.
"""

from __future__ import annotations

from typing import Any

from verifirm.adapters.base import BaseAdapter, Sourced, SourceUnavailable
from verifirm.adapters.presence_fixture import read_parts
from verifirm.core.registry import register_adapter
from verifirm.schema.signals import SourceType


@register_adapter("kohesio")
class KohesioAdapter(BaseAdapter):
    source_label = "Kohesio (EU funds)"
    source_type = SourceType.OFFICIAL
    mirror_max_age_s = 7 * 86_400

    async def projects_for(
        self, company_name: str, cui: str | None
    ) -> Sourced[list[dict[str, Any]]]:
        """Projects where the company is a beneficiary: {title, programme, eu_contribution_eur, start, url}.
        Empty list = checked, none found. FIXTURE_MODE: presence.json -> "kohesio" (by CUI). Live:
        unavailable until the Kohesio ingest job exists (never "no projects" by default)."""
        if not self.settings.fixture_mode:
            raise SourceUnavailable(self.name, "no local Kohesio data yet (ingest job to add)")
        if not cui:
            raise SourceUnavailable(self.name, "fixture data is keyed by CUI")
        result = await read_parts(self, cui, {"kohesio": (list,)})
        return Sourced(data=result.data["kohesio"], source=result.source, stale=result.stale)
