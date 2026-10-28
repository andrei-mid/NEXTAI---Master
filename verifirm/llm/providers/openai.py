"""OpenAI chat completions (LLM_PROVIDER=openai), over httpx (no SDK dependency).

complete_json uses strict structured outputs (response_format json_schema). Strict mode needs
additionalProperties=false and every property required, so `strict_schema` adapts the Pydantic
schema. The answer is still re-validated with Pydantic (HttpLLMClient.complete_json).
OpenAI-compatible servers reuse this class: see openai_compatible.py.
"""

from __future__ import annotations

from typing import Any

import httpx

from verifirm.core.config import Settings
from verifirm.core.ports.llm import LLMMessage, T
from verifirm.llm.providers._http import HttpLLMClient, LLMConfigError

API_BASE = "https://api.openai.com/v1"
# Keywords strict mode rejects. They only constrain values, and Pydantic re-checks them anyway.
_UNSUPPORTED = {"default", "title", "minLength", "maxLength", "minimum", "maximum", "format"}


def strict_schema(node: Any) -> Any:
    """Adapt a Pydantic JSON schema to OpenAI strict mode (recursively)."""
    if isinstance(node, list):
        return [strict_schema(n) for n in node]
    if not isinstance(node, dict):
        return node
    out = {k: strict_schema(v) for k, v in node.items() if k not in _UNSUPPORTED}
    props = out.get("properties")
    if isinstance(props, dict):
        out["additionalProperties"] = False
        out["required"] = list(props)
    return out


class OpenAIClient(HttpLLMClient):
    provider = "openai"
    base_url = API_BASE
    token_param = "max_completion_tokens"
    use_json_schema = True
    send_temperature = False  # newer OpenAI models only accept the default temperature

    def __init__(self, settings: Settings, http: httpx.AsyncClient | None = None) -> None:
        super().__init__(settings, http)
        if not self.api_key():
            raise LLMConfigError("LLM_PROVIDER=openai needs OPENAI_API_KEY")

    def api_key(self) -> str | None:
        return self.settings.openai_api_key

    def model_name(self, model: str | None) -> str:
        name = super().model_name(model)
        if name.startswith("claude"):
            raise LLMConfigError(
                f"{self.provider}: model {name!r} is a Claude model. "
                "Set LLM_MODEL_DEFAULT (and LLM_MODEL_MEMO / LLM_MODEL_CRITIC) for this provider."
            )
        return name

    def _payload(
        self,
        system: str,
        messages: list[LLMMessage],
        model: str | None,
        max_tokens: int,
        temperature: float,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model_name(model),
            "messages": [{"role": "system", "content": system}, *[m.model_dump() for m in messages]],
            self.token_param: max_tokens,
        }
        if self.send_temperature:
            payload["temperature"] = temperature
        return payload

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key()}", "content-type": "application/json"}

    async def _chat(self, payload: dict[str, Any]) -> str:
        body = await self.post(f"{self.base_url}/chat/completions", self._headers(), payload)
        usage = body.get("usage") or {}
        self.log_usage(payload["model"], usage.get("prompt_tokens"), usage.get("completion_tokens"))
        choices = body.get("choices") or []
        if not choices:
            raise ValueError(f"{self.provider} returned no choices")
        message = choices[0].get("message") or {}
        if message.get("refusal"):
            raise ValueError(f"{self.provider} refused: {message['refusal']}")
        return str(message.get("content") or "")

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
        if self.use_json_schema:
            payload = self._payload(system, messages, model, max_tokens, temperature)
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": schema.__name__,
                    "schema": strict_schema(schema.model_json_schema()),
                    "strict": True,
                },
            }
        else:
            # No strict mode: "JSON only" prompting, validated afterwards by the caller.
            hint = (
                f"{system}\n\nRespond with ONLY one JSON object that matches this JSON schema, "
                f"with no prose and no code fences:\n{schema.model_json_schema()}"
            )
            payload = self._payload(hint, messages, model, max_tokens, temperature)
        return await self._chat(payload)

    async def complete_text(
        self,
        *,
        system: str,
        messages: list[LLMMessage],
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> str:
        return await self._chat(self._payload(system, messages, model, max_tokens, temperature))
