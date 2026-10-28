from __future__ import annotations

import time

from verifirm.core.ports.cache import Cache


class MemoryCache(Cache):
    def __init__(self) -> None:
        self._data: dict[str, tuple[float, bytes]] = {}

    async def get(self, key: str) -> bytes | None:
        item = self._data.get(key)
        if item is None:
            return None
        expires_at, value = item
        if time.monotonic() >= expires_at:
            del self._data[key]
            return None
        return value

    async def set(self, key: str, value: bytes, *, ttl_s: int) -> None:
        self._data[key] = (time.monotonic() + ttl_s, value)

    async def delete(self, key: str) -> None:
        self._data.pop(key, None)
