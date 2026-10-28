"""MOCK sources: real sources we cannot access in the hackathon (paid, captcha or certificate).

Every mock has source_type = MOCK, so the UI shows a MOCK badge. Mocks read ONLY fixtures/,
in every mode. A company without a mock fixture -> SourceUnavailable (never clean).
A fixture with the wrong shape -> SourceUnavailable too (never silently "nothing found").

Production route per mock (docs/SOURCES.md): the applicant's documents (D300, SAF-T,
certificat de atestare fiscală) or a paid provider (BPI, shareholders, PEP). Swapping a mock
for the real source changes only the adapter. Agents keep calling the same READ method.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from verifirm.adapters.base import BaseAdapter, Sourced, SourceUnavailable
from verifirm.core.ports.object_store import content_hash
from verifirm.schema.signals import SourceType


class MockAdapter(BaseAdapter):
    """Base for mocks: read one fixture file, check its shape, return it with a MOCK SourceRef.
    No sync() (nothing to download) and no network in any mode."""

    source_type = SourceType.MOCK

    async def read_company(
        self, cui: str, filename: str, required: dict[str, type]
    ) -> Sourced[Any]:
        """fixtures/companies/<cui>_*/<filename>, checked for `required` {key: type}."""
        return await self._read(self.company_fixture(cui, filename), f"{cui}/{filename}", required)

    async def read_shared(self, relative: str, required: dict[str, type]) -> Sourced[Any]:
        """fixtures/sources/<relative>, checked for `required` {key: type}."""
        return await self._read(self.shared_fixture(relative), relative, required)

    async def _read(self, path: Path | None, label: str, required: dict[str, type]) -> Sourced[Any]:
        if path is None:
            raise SourceUnavailable(self.name, f"no mock data for {label}")
        body = await asyncio.to_thread(path.read_bytes)
        try:
            data = json.loads(body)
        except ValueError as exc:
            raise SourceUnavailable(self.name, f"invalid JSON in {label}") from exc
        wrong = [
            key
            for key, kind in required.items()
            if not isinstance(data, dict) or not isinstance(data.get(key), kind)
        ]
        if wrong:
            raise SourceUnavailable(self.name, f"{label} is missing or has wrong {wrong}")
        rel = path.relative_to(self.fixtures_dir).as_posix()
        source = self._source_ref(None, f"fixture:{rel}", content_hash(body), self.deps.clock.now())
        return Sourced(data=data, source=source)
