from __future__ import annotations

import asyncio
from pathlib import Path

from verifirm.core.ports.object_store import ObjectStore, content_hash


class FilesystemObjectStore(ObjectStore):
    """Stores objects as files under `root` (default .data/objects, git-ignored)."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root.resolve()):
            raise ValueError(f"object key escapes the store: {key!r}")
        return path

    async def put(self, data: bytes, *, prefix: str) -> str:
        key = f"{prefix.strip('/')}/{content_hash(data)}"
        path = self._path(key)
        if not path.exists():
            await asyncio.to_thread(self._write, path, data)
        return key

    async def put_named(self, key: str, data: bytes) -> None:
        await asyncio.to_thread(self._write, self._path(key), data)

    async def get(self, key: str) -> bytes | None:
        path = self._path(key)
        if not path.exists():
            return None
        return await asyncio.to_thread(path.read_bytes)

    async def exists(self, key: str) -> bool:
        return self._path(key).exists()

    @staticmethod
    def _write(path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_bytes(data)
        tmp.replace(path)
