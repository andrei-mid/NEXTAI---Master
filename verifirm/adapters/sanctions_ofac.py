"""STUB. Owner: @role-4-external-agents. US Treasury OFAC SDN list (OFFICIAL).

Facts:
- CSV: https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/SDN.CSV
  (no header row. Columns: ent_num, SDN_Name, SDN_Type, Program, Title, Call_Sign,
  Vess_type, Tonnage, GRT, Vess_flag, Vess_owner, Remarks. "-0-" means empty).
- Aliases are in ALT.CSV and addresses in ADD.CSV at the same base URL. Add them if matching needs them.
- Bulk download on a schedule. Normalize to the same entry shape as sanctions_eu.
- Fixture: fixtures/sources/sanctions/ofac_sdn_sample.csv (fictional entries only).
"""

from __future__ import annotations

from typing import Any

from verifirm.adapters.base import BaseAdapter, Sourced
from verifirm.core.registry import register_adapter
from verifirm.schema.signals import SourceType

URL = "https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/SDN.CSV"


@register_adapter("sanctions_ofac")
class SanctionsOfacAdapter(BaseAdapter):
    source_label = "OFAC SDN list"
    source_type = SourceType.OFFICIAL

    async def download_entries(self) -> Sourced[list[dict[str, Any]]]:
        """SDN.CSV -> normalized entries (see sanctions_eu for the shape)."""
        raise NotImplementedError
