"""Object store port: raw-response archive (audit + replay) and submitted documents.

Archive keys are content-addressed (`<prefix>/<sha256>`), so storing the same bytes twice
is a no-op. Local: filesystem under .data/objects. Cloud: S3.
"""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod


def content_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class ObjectStore(ABC):
    @abstractmethod
    async def put(self, data: bytes, *, prefix: str) -> str:
        """Store bytes content-addressed and return the key `<prefix>/<sha256>`."""

    @abstractmethod
    async def put_named(self, key: str, data: bytes) -> None:
        """Store bytes under an explicit, overwritable key (e.g. `lastgood/<adapter>/<key>`)."""

    @abstractmethod
    async def get(self, key: str) -> bytes | None: ...

    @abstractmethod
    async def exists(self, key: str) -> bool: ...
