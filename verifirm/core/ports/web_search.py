"""Web search port (media agent). Provider: Tavily (D10). Fixture implementation in impl_local.

Results are UNTRUSTED data. A result without a URL and a date can never become a signal.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from pydantic import BaseModel


class WebResult(BaseModel):
    url: str
    title: str
    snippet: str
    published_at: date | None = None
    provider: str
    fictional: bool = False


class WebSearch(ABC):
    @abstractmethod
    async def search(
        self, query: str, *, max_results: int = 10, since: date | None = None
    ) -> list[WebResult]: ...
