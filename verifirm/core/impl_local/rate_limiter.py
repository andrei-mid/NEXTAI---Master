from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque

from verifirm.core.ports.rate_limiter import RateLimit, RateLimiter


class MemoryRateLimiter(RateLimiter):
    """Sliding-window limiter. Global only within one process (see impl_cloud for Redis)."""

    def __init__(self) -> None:
        self._calls: dict[str, deque[float]] = defaultdict(deque)
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def acquire(self, key: str, limit: RateLimit) -> None:
        async with self._locks[key]:
            calls = self._calls[key]
            while True:
                now = time.monotonic()
                while calls and now - calls[0] >= limit.period_s:
                    calls.popleft()
                if len(calls) < limit.max_calls:
                    calls.append(now)
                    return
                await asyncio.sleep(limit.period_s - (now - calls[0]))
