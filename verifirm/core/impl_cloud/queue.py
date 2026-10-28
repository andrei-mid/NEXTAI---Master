"""STUB. Owner: @role-2-core. Redis (local docker-compose) and SQS (AWS, D6) queues."""

from __future__ import annotations

from typing import Any

from verifirm.core.ports.queue import Queue, QueueMessage


class RedisQueue(Queue):
    """Redis Streams queue (XADD / XREADGROUP / XACK) for docker-compose and the single box.

    Implement:
    - enqueue: XADD to stream `verifirm:{topic}`. Dedupe: SET NX `dedupe:{key}` -> message_id
      (cleared on ack or on nack with retry=False).
    - dequeue: XREADGROUP with consumer group "workers", BLOCK wait_s*1000. receipt = stream id.
    - ack: XACK + XDEL. nack(retry=True): XACK, then XADD again with attempts+1.
    - Reclaim messages stuck in the PEL with XAUTOCLAIM (visibility timeout from settings).
    """

    def __init__(self, redis_url: str) -> None:
        self.redis_url = redis_url

    async def enqueue(
        self, topic: str, body: dict[str, Any], *, dedupe_key: str | None = None
    ) -> str:
        raise NotImplementedError

    async def dequeue(self, topic: str, *, wait_s: float = 1.0) -> QueueMessage | None:
        raise NotImplementedError

    async def ack(self, message: QueueMessage) -> None:
        raise NotImplementedError

    async def nack(self, message: QueueMessage, *, retry: bool = True) -> None:
        raise NotImplementedError


class SqsQueue(Queue):
    """Amazon SQS queue (target deployment A: Fargate + SQS).

    Implement:
    - one queue URL per topic (settings.sqs_queue_url as a prefix or a JSON map).
    - enqueue: SendMessage. Dedupe via a FIFO queue with MessageDeduplicationId=dedupe_key,
      or a standard queue + Repository-level idempotency (run_id). Decide in DECISIONS.md.
    - dequeue: ReceiveMessage (WaitTimeSeconds=wait_s, long polling). receipt = ReceiptHandle.
    - ack: DeleteMessage. nack(retry=True): ChangeMessageVisibility(0). Use a DLQ redrive policy.
    """

    def __init__(self, queue_url: str, region: str) -> None:
        self.queue_url = queue_url
        self.region = region

    async def enqueue(
        self, topic: str, body: dict[str, Any], *, dedupe_key: str | None = None
    ) -> str:
        raise NotImplementedError

    async def dequeue(self, topic: str, *, wait_s: float = 1.0) -> QueueMessage | None:
        raise NotImplementedError

    async def ack(self, message: QueueMessage) -> None:
        raise NotImplementedError

    async def nack(self, message: QueueMessage, *, retry: bool = True) -> None:
        raise NotImplementedError
