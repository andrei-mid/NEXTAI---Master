from __future__ import annotations

from typing import Any

from verifirm.core.ports.llm import LLMClient, LLMMessage, T


class FakeLLMClient(LLMClient):
    """Deterministic, offline LLM for tests and fixture mode (LLM_PROVIDER=fake).

    `json_responses` maps a schema class name to the payload to return for it.
    `text_responses` are returned in order by complete_text.
    """

    provider = "fake"

    def __init__(
        self,
        json_responses: dict[str, Any] | None = None,
        text_responses: list[str] | None = None,
    ) -> None:
        self.json_responses = dict(json_responses or {})
        self.text_responses = list(text_responses or [])
        self.calls: list[dict[str, Any]] = []

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
        self.calls.append({"system": system, "messages": messages, "schema": schema.__name__})
        if schema.__name__ not in self.json_responses:
            raise ValueError(f"FakeLLMClient has no canned response for {schema.__name__}")
        return schema.model_validate(self.json_responses[schema.__name__])

    async def complete_text(
        self,
        *,
        system: str,
        messages: list[LLMMessage],
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> str:
        self.calls.append({"system": system, "messages": messages, "schema": None})
        if not self.text_responses:
            raise ValueError("FakeLLMClient has no canned text responses left")
        return self.text_responses.pop(0)
