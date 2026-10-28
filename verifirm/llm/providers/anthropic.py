"""Claude via the direct Anthropic API (D3 default), over httpx (no SDK dependency).

complete_json forces a single tool whose input_schema is the Pydantic schema, then the shared
HttpLLMClient re-validates the tool input and retries once on a validation error.
Model ids come from settings (llm_model_default / model_for), never hard-coded here.
"""

from __future__ import annotations

import httpx

from verifirm.core.config import Settings
from verifirm.core.ports.llm import LLMMessage, T
from verifirm.llm.providers._http import HttpLLMClient, LLMConfigError, dump_json

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"
TOOL_NAME = "emit_result"


class AnthropicClient(HttpLLMClient):
    provider = "anthropic"
    url = API_URL

    def __init__(self, settings: Settings, http: httpx.AsyncClient | None = None) -> None:
        super().__init__(settings, http)
        if not settings.anthropic_api_key:
            raise LLMConfigError("LLM_PROVIDER=anthropic needs ANTHROPIC_API_KEY")

    def _headers(self) -> dict[str, str]:
        return {
            "x-api-key": self.settings.anthropic_api_key or "",
            "anthropic-version": API_VERSION,
            "content-type": "application/json",
        }

    def _payload(
        self,
        system: str,
        messages: list[LLMMessage],
        model: str | None,
        max_tokens: int,
        temperature: float,
    ) -> dict[str, object]:
        return {
            "model": self.model_name(model),
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system,
            "messages": [m.model_dump() for m in messages],
        }

    async def raw_json(
        self,
        *,
        system: str,
        messages: list[LLMMessage],
        schema: type[T],
        model: str | None,
        max_tokens: int,
        temperature: float,
    ) -> str:
        payload = self._payload(system, messages, model, max_tokens, temperature)
        payload["tools"] = [
            {
                "name": TOOL_NAME,
                "description": f"Return the answer as a {schema.__name__} object.",
                "input_schema": schema.model_json_schema(),
            }
        ]
        payload["tool_choice"] = {"type": "tool", "name": TOOL_NAME}
        body = await self.post(self.url, self._headers(), payload)
        self._log(body, str(payload["model"]))
        for block in body.get("content", []):
            if block.get("type") == "tool_use":
                return dump_json(block.get("input", {}))
        raise ValueError(f"anthropic returned no tool_use block (stop: {body.get('stop_reason')})")

    async def complete_text(
        self,
        *,
        system: str,
        messages: list[LLMMessage],
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> str:
        payload = self._payload(system, messages, model, max_tokens, temperature)
        body = await self.post(self.url, self._headers(), payload)
        self._log(body, str(payload["model"]))
        return "".join(b.get("text", "") for b in body.get("content", []) if b.get("type") == "text")

    def _log(self, body: dict[str, object], model: str) -> None:
        usage = body.get("usage")
        usage = usage if isinstance(usage, dict) else {}
        self.log_usage(model, usage.get("input_tokens"), usage.get("output_tokens"))
