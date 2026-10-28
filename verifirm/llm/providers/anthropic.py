"""STUB. Owner: @role-5-ai-api. Claude via the direct Anthropic API (D3 default).

Implement with the official `anthropic` SDK (add it to pyproject in the implementing PR):
- AsyncAnthropic(api_key=settings.anthropic_api_key).
- complete_json: use structured outputs / a single forced tool whose input_schema is
  schema.model_json_schema(), then RE-VALIDATE with schema.model_validate (json_output.py).
  One repair retry with the validation error, then raise ValueError.
- Model ids come from settings (llm_model_default / model_for(task)), never hard-coded.
- temperature 0 by default. Log usage tokens with the run_id (core.logging).
"""

from __future__ import annotations

from verifirm.core.config import Settings
from verifirm.core.ports.llm import LLMClient, LLMMessage, T


class AnthropicClient(LLMClient):
    provider = "anthropic"

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
