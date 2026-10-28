"""STUB. Owner: @role-5-ai-api. Build the IdentitySheet from OFFICIAL sources only (never the web).

Implement `build_identity_sheet`:
- anaf_v9 (lookup for today's date): name, address, reg. no., CAEN, legal form, VAT, inactive.
- onrc_bulk.company(cui): name history, office history, status, authorized CAEN (Rev.2 + Rev.3),
  legal representatives -> Person(role=ADMINISTRATOR) with valid_from / valid_to.
- mock_shareholders: shareholders (Person.source.type == MOCK).
- Conflicts between ANAF and ONRC: keep both in the history, prefer the most recent dated value
  as current, and record every SourceRef in `sources`.
- If BOTH anaf_v9 and onrc_bulk fail -> raise SourceUnavailable: the run can't continue
  without identity (and identity is required for GREEN).
- fictional = cui in core.cui.FICTIONAL_CUIS.
"""

from __future__ import annotations

from collections.abc import Mapping

from verifirm.adapters.base import BaseAdapter
from verifirm.core.ports.clock import Clock
from verifirm.schema.identity import IdentitySheet


async def build_identity_sheet(
    cui: str, adapters: Mapping[str, BaseAdapter], clock: Clock
) -> IdentitySheet:
    raise NotImplementedError
