"""Cache port for external responses. Default TTL 24h, configurable per adapter."""

from __future__ import annotations

from abc import ABC, abstractmethod


class Cache(ABC):
    @abstractmethod
    async def get(self, key: str) -> bytes | None:
        """Return the cached value, or None if missing/expired."""

    @abstractmethod
    async def set(self, key: str, value: bytes, *, ttl_s: int) -> None: ...

    @abstractmethod
    async def delete(self, key: str) -> None: ...
