"""STUB. Owner: @role-5-ai-api. Any OpenAI-compatible endpoint (e.g. Featherless, local vLLM).

Implement as OpenAIClient with base_url=settings.openai_compatible_base_url and
api_key=settings.openai_compatible_api_key. Many of these servers do NOT support strict
json_schema, so fall back to "JSON only" prompting plus RE-VALIDATION and one repair retry (json_output.py).
"""

from __future__ import annotations

from verifirm.core.config import Settings
from verifirm.core.ports.llm import LLMClient, LLMMessage, T


class OpenAICompatibleClient(LLMClient):
    provider = "openai_compatible"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

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
        raise NotImplementedError

    async def complete_text(
        self,
        *,
        system: str,
        messages: list[LLMMessage],
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> str:
        raise NotImplementedError
