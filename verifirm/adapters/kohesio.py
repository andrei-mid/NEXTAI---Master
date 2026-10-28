"""STUB. Owner: @role-4-external-agents. EU cohesion-funds beneficiaries (Kohesio, European Commission).

Facts / to confirm:
- https://kohesio.ec.europa.eu publishes projects and beneficiaries (API + bulk exports).
  Prefer the bulk export filtered to Romania, ingested on a schedule. Confirm the endpoint and
  licence, then record them in docs/SOURCES.md.
- Beneficiaries are matched by name (plus the CUI when present), so return match info.
- Fixture: fixtures/companies/<cui>_<slug>/presence.json -> key "kohesio".
"""

from __future__ import annotations

from typing import Any

from verifirm.adapters.base import BaseAdapter, Sourced
from verifirm.core.registry import register_adapter
from verifirm.schema.signals import SourceType


@register_adapter("kohesio")
class KohesioAdapter(BaseAdapter):
    source_label = "Kohesio (EU funds)"
    source_type = SourceType.OFFICIAL
    cache_ttl_s = 7 * 86_400

    async def projects_for(
        self, company_name: str, cui: str | None
    ) -> Sourced[list[dict[str, Any]]]:
        """Projects where the company is a beneficiary: {title, programme, eu_contribution_eur, start, url}."""
        raise NotImplementedError
