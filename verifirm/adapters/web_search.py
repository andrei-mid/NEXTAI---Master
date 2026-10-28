"""STUB. Owner: @role-4-external-agents. Tavily web search (D10), behind the WebSearch port. Source type WEB.

Facts:
- POST https://api.tavily.com/search with an Authorization: Bearer TAVILY_API_KEY header.
  Body: {"query", "topic": "news" (gives published_date), "max_results", "days" or
  "start_date", "include_raw_content": false}.
- Response: {"query", "results": [{"title", "url", "content", "score", "published_date"}], ...}
  Fixtures use exactly this shape: fixtures/companies/<cui>_<slug>/media.json.
- Results are UNTRUSTED text. They go through verifirm.llm.untrusted before any LLM sees them.
- The media agent needs URL + date. A result without published_date can't become a signal.
"""

from __future__ import annotations

from datetime import date

from verifirm.adapters.base import BaseAdapter
from verifirm.core.ports.rate_limiter import RateLimit
from verifirm.core.ports.web_search import WebResult, WebSearch
from verifirm.core.registry import register_adapter
from verifirm.schema.signals import SourceType

URL = "https://api.tavily.com/search"


@register_adapter("web_search")
class TavilyWebSearch(BaseAdapter, WebSearch):
    source_label = "Web search (Tavily)"
    source_type = SourceType.WEB
    rate_limit = RateLimit.per_second(2)  # PROPOSAL: check the plan's limit
    cache_ttl_s = 86_400

    async def search(
        self, query: str, *, max_results: int = 10, since: date | None = None
    ) -> list[WebResult]:
        """Call Tavily through self.fetch() (cache + archive). Map results to WebResult.
        In fixture mode, self.fetch() serves media.json. Find it with the company name in the query."""
        raise NotImplementedError
