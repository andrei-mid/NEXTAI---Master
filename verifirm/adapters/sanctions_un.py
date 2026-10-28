"""STUB. Owner: @role-4-external-agents. UN Security Council consolidated list (OFFICIAL).

Facts:
- XML: https://scsanctions.un.org/resources/xml/en/consolidated.xml
- Bulk download on a schedule. Normalize to the same entry shape as sanctions_eu.
- Fixture: fixtures/sources/sanctions/un_sample.xml (fictional entries only).

Local-first (docs/LOCAL_DATA.md): bulk: the ingest_sanctions job. sync() no-op. Screening reads local entries only.
"""

from __future__ import annotations

from typing import Any

from verifirm.adapters.base import BaseAdapter, Sourced
from verifirm.core.registry import register_adapter
from verifirm.schema.signals import SourceType

URL = "https://scsanctions.un.org/resources/xml/en/consolidated.xml"


@register_adapter("sanctions_un")
class SanctionsUnAdapter(BaseAdapter):
    source_label = "UN Security Council consolidated list"
    source_type = SourceType.OFFICIAL

    async def download_entries(self) -> Sourced[list[dict[str, Any]]]:
        """INDIVIDUALS + ENTITIES -> normalized entries (see sanctions_eu for the shape)."""
        raise NotImplementedError
