"""Rate limiter port. Each adapter declares its limit. Limits are enforced GLOBALLY,
so 50 workers still respect ANAF's 1 request/second.

Local: in-memory (single process). Distributed: Redis (stub in impl_cloud).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class RateLimit:
    max_calls: int
    period_s: float

    @classmethod
    def per_second(cls, n: int = 1) -> RateLimit:
        return cls(max_calls=n, period_s=1.0)


class RateLimiter(ABC):
    @abstractmethod
    async def acquire(self, key: str, limit: RateLimit) -> None:
        """Wait until a call under `key` is allowed by `limit`, then record it."""
