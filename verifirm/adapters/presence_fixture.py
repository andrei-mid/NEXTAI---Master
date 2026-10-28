"""Shared reader for fixtures/companies/<cui>_<slug>/presence.json (demo footprint data).

The presence agent's four parts (website, job postings, SEAP contracts, EU-funded projects) live
in one fixture file. `seap`, `kohesio` and `web_search` each read their own part through
BaseAdapter.fetch() (fixture -> mirror -> SourceUnavailable), so the SourceRef points at the file.
A missing file or a part with the wrong shape is SourceUnavailable, never "nothing found".
"""

from __future__ import annotations

from typing import Any

import httpx

from verifirm.adapters.base import BaseAdapter, Sourced, SourceUnavailable


async def _never(client: httpx.AsyncClient) -> httpx.Response:
    raise SourceUnavailable("presence", "presence parts are never downloaded from here")


async def read_parts(
    adapter: BaseAdapter, cui: str, parts: dict[str, tuple[type, ...]]
) -> Sourced[dict[str, Any]]:
    """{part: value} from presence.json, each checked against its allowed types."""
    result = await adapter.fetch(
        cache_key=f"presence:{cui}",
        request=_never,
        fixture=adapter.company_fixture(cui, "presence.json"),
    )
    try:
        payload = result.json()
    except ValueError as exc:
        raise SourceUnavailable(adapter.name, f"presence.json for {cui} is not JSON") from exc
    if not isinstance(payload, dict):
        raise SourceUnavailable(adapter.name, f"presence.json for {cui} is not an object")
    out: dict[str, Any] = {}
    for part, kinds in parts.items():
        if part not in payload or not isinstance(payload[part], kinds):
            raise SourceUnavailable(
                adapter.name, f"presence.json for {cui}: bad or missing {part!r}"
            )
        out[part] = payload[part]
    return Sourced(data=out, source=result.source, stale=result.stale)
