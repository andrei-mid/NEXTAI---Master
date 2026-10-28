from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from verifirm.core.ports.web_search import WebResult, WebSearch


class FixtureWebSearch(WebSearch):
    """Serves fixtures/companies/*/media.json (Tavily response shape) with no network.

    A fixture file matches when its `query` and the search query share a word of 4+ letters.
    """

    def __init__(self, fixtures_dir: Path) -> None:
        self.fixtures_dir = fixtures_dir

    async def search(
        self, query: str, *, max_results: int = 10, since: date | None = None
    ) -> list[WebResult]:
        wanted = {w for w in query.lower().split() if len(w) >= 4}
        results: list[WebResult] = []
        for path in sorted(self.fixtures_dir.glob("companies/*/media.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not wanted & {w for w in str(payload.get("query", "")).lower().split()}:
                continue
            for item in payload.get("results", []):
                published = item.get("published_date")
                published_at = date.fromisoformat(published[:10]) if published else None
                if since is not None and published_at is not None and published_at < since:
                    continue
                results.append(
                    WebResult(
                        url=item["url"],
                        title=item.get("title", ""),
                        snippet=item.get("content", ""),
                        published_at=published_at,
                        provider="fixture",
                        fictional=bool(payload.get("fictional", False)),
                    )
                )
        return results[:max_results]
