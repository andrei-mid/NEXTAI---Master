"""STUB. Owner: @role-2-core. Redis cache shared by all workers and API replicas."""

from __future__ import annotations

from verifirm.core.ports.cache import Cache


class RedisCache(Cache):
    """Implement with SET key value EX ttl_s / GET / DEL, keys prefixed `verifirm:cache:`.

    On AWS this is ElastiCache Redis (or Valkey) in the same VPC as the workers.
    """

    def __init__(self, redis_url: str) -> None:
        self.redis_url = redis_url

    async def get(self, key: str) -> bytes | None:
        raise NotImplementedError

    async def set(self, key: str, value: bytes, *, ttl_s: int) -> None:
        raise NotImplementedError

    async def delete(self, key: str) -> None:
        raise NotImplementedError
