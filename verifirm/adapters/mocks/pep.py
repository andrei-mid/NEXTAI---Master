"""STUB. Owner: @role-3-official-agents. MOCK of a Politically Exposed Persons list (real lists are commercial).

Fixture: fixtures/sources/pep_sample.json
  {"fictional": true, "entries": [{"name", "function", "country", "since", "until"}]}
Fuzzy-matched against administrators (and mock shareholders). Feeds SAN-PEP-01.
"""

from __future__ import annotations

from typing import Any

from verifirm.adapters.base import BaseAdapter, Sourced
from verifirm.core.registry import register_adapter
from verifirm.schema.signals import SourceType


@register_adapter("mock_pep")
class MockPepAdapter(BaseAdapter):
    source_label = "PEP list (MOCK)"
    source_type = SourceType.MOCK

    async def entries(self) -> Sourced[list[dict[str, Any]]]:
        raise NotImplementedError
