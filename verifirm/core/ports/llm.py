"""LLM port. Implemented only by verifirm/llm/providers (real) and core/impl_local (fake).

Callers ask for schema-validated output. Raw model text never crosses agent boundaries.
Untrusted text (PDFs, web pages) must be wrapped with verifirm.llm.untrusted first.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class LLMClient(ABC):
    provider: str = "abstract"

    @abstractmethod
    async def complete_json(
        self,
        *,
        system: str,
        messages: list[LLMMessage],
        schema: type[T],
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> T:
        """Return the answer parsed AND re-validated as `schema`.

        Raise ValueError if the output still fails validation after the provider's retries.
        """

    @abstractmethod
    async def complete_text(
        self,
        *,
        system: str,
        messages: list[LLMMessage],
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> str: ...
