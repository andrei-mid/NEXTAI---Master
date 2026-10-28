"""Ports: every piece of infrastructure sits behind one of these interfaces.

Each port has an in-memory / filesystem implementation in core/impl_local (works with zero
services running) and a stub for the real/cloud implementation in core/impl_cloud.
Changing infrastructure = adding an implementation, never rewriting callers.
"""

from verifirm.core.ports.cache import Cache
from verifirm.core.ports.clock import Clock
from verifirm.core.ports.llm import LLMClient, LLMMessage
from verifirm.core.ports.object_store import ObjectStore
from verifirm.core.ports.queue import Queue, QueueMessage
from verifirm.core.ports.rate_limiter import RateLimit, RateLimiter
from verifirm.core.ports.repository import Repository
from verifirm.core.ports.web_search import WebResult, WebSearch

__all__ = [
    "Cache",
    "Clock",
    "LLMClient",
    "LLMMessage",
    "ObjectStore",
    "Queue",
    "QueueMessage",
    "RateLimit",
    "RateLimiter",
    "Repository",
    "WebResult",
    "WebSearch",
]
