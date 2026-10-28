"""Owner: @role-3-official-agents. MOCK of a Politically Exposed Persons list (real lists are commercial).

Fixture: fixtures/sources/pep_sample.json
  {"fictional": true, "entries": [{"name", "function", "country", "since", "until"}]}
Fuzzy-matched against administrators (and mock shareholders). Feeds SAN-PEP-01.

Local-first (docs/LOCAL_DATA.md): mocks read fixtures/ only, in every mode. No sync, no network.
"""

from __future__ import annotations

from typing import Any

from verifirm.adapters.base import Sourced
from verifirm.adapters.mocks import MockAdapter
from verifirm.core.registry import register_adapter


@register_adapter("mock_pep")
class MockPepAdapter(MockAdapter):
    source_label = "PEP list (MOCK)"

    async def entries(self) -> Sourced[list[dict[str, Any]]]:
        """The whole (fictional) PEP list: [{name, function, country, since, until}]."""
        result = await self.read_shared("pep_sample.json", {"entries": list})
        return Sourced(data=result.data["entries"], source=result.source)
