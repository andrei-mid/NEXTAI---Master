from __future__ import annotations

import asyncio
import uuid
from collections import defaultdict, deque
from typing import Any

from verifirm.core.ports.queue import Queue, QueueMessage


class MemoryQueue(Queue):
    def __init__(self) -> None:
        self._ready: dict[str, deque[QueueMessage]] = defaultdict(deque)
        self._in_flight: dict[str, QueueMessage] = {}
        self._pending_dedupe: dict[str, str] = {}  # dedupe_key -> message_id
        self._signal: dict[str, asyncio.Event] = defaultdict(asyncio.Event)

    async def enqueue(
        self, topic: str, body: dict[str, Any], *, dedupe_key: str | None = None
    ) -> str:
        if dedupe_key is not None and dedupe_key in self._pending_dedupe:
            return self._pending_dedupe[dedupe_key]
        msg = QueueMessage(
            message_id=uuid.uuid4().hex, topic=topic, body=body, dedupe_key=dedupe_key
        )
        self._ready[topic].append(msg)
        if dedupe_key is not None:
            self._pending_dedupe[dedupe_key] = msg.message_id
        self._signal[topic].set()
        return msg.message_id

    async def dequeue(self, topic: str, *, wait_s: float = 1.0) -> QueueMessage | None:
        if not self._ready[topic]:
            event = self._signal[topic]
            event.clear()
            try:
                await asyncio.wait_for(event.wait(), timeout=wait_s)
            except TimeoutError:
                return None
            if not self._ready[topic]:
                return None
        msg = self._ready[topic].popleft()
        msg = msg.model_copy(update={"attempts": msg.attempts + 1, "receipt": uuid.uuid4().hex})
        self._in_flight[msg.receipt or ""] = msg
        return msg

    async def ack(self, message: QueueMessage) -> None:
        self._in_flight.pop(message.receipt or "", None)
        if message.dedupe_key is not None:
            self._pending_dedupe.pop(message.dedupe_key, None)

    async def nack(self, message: QueueMessage, *, retry: bool = True) -> None:
        self._in_flight.pop(message.receipt or "", None)
        if retry:
            self._ready[message.topic].append(message.model_copy(update={"receipt": None}))
            self._signal[message.topic].set()
        elif message.dedupe_key is not None:
            self._pending_dedupe.pop(message.dedupe_key, None)
