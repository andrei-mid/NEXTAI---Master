"""STUB. Owner: @role-2-core. Distributed rate limiter, so N workers share one global limit."""

from __future__ import annotations

from verifirm.core.ports.rate_limiter import RateLimit, RateLimiter


class RedisRateLimiter(RateLimiter):
    """Sliding window in Redis, enforced atomically with a Lua script.

    Implement:
    - key `verifirm:rl:{key}` as a sorted set of call timestamps.
    - The Lua script trims entries older than period_s, and if ZCARD < max_calls it ZADDs now
      and returns 0. Otherwise it returns the ms to wait. The caller sleeps and retries.
    - Use the Redis server TIME, not the worker clock, so skewed workers can't exceed the limit.
    - Must make 50 workers respect ANAF's 1 req/s globally (add a test with N concurrent tasks).
    """

    def __init__(self, redis_url: str) -> None:
        self.redis_url = redis_url

    async def acquire(self, key: str, limit: RateLimit) -> None:
        raise NotImplementedError
