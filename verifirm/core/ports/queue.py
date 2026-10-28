"""Queue port. Local: in-memory. Redis under docker-compose. Cloud: SQS (D6)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel


class QueueMessage(BaseModel):
    message_id: str
    topic: str
    body: dict[str, Any]
    dedupe_key: str | None = None  # idempotency: same key -> enqueued once while pending
    attempts: int = 0
    receipt: str | None = None  # backend handle used for ack/nack


class Queue(ABC):
    @abstractmethod
    async def enqueue(
        self, topic: str, body: dict[str, Any], *, dedupe_key: str | None = None
    ) -> str:
        """Enqueue a message and return its message_id. A pending message with the same
        dedupe_key is not enqueued twice (the existing message_id is returned)."""

    @abstractmethod
    async def dequeue(self, topic: str, *, wait_s: float = 1.0) -> QueueMessage | None:
        """Return the next message (invisible to other consumers until ack/nack) or None."""

    @abstractmethod
    async def ack(self, message: QueueMessage) -> None:
        """Mark the message done. It is deleted."""

    @abstractmethod
    async def nack(self, message: QueueMessage, *, retry: bool = True) -> None:
        """Processing failed. retry=True makes it visible again, False drops / dead-letters it."""
