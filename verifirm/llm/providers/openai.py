"""STUB. Owner: @role-5-ai-api. OpenAI (LLM_PROVIDER=openai).

Implement with the official `openai` SDK (add it in the implementing PR):
- AsyncOpenAI(api_key=settings.openai_api_key).
- complete_json: response_format={"type": "json_schema", "json_schema": {"name": schema.__name__,
  "schema": schema.model_json_schema(), "strict": True}}, then RE-VALIDATE (json_output.py).
  Strict mode needs additionalProperties=false and all fields required, so adapt the schema there.
"""

from __future__ import annotations

from verifirm.core.config import Settings
from verifirm.core.ports.llm import LLMClient, LLMMessage, T


class OpenAIClient(LLMClient):
    provider = "openai"

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
