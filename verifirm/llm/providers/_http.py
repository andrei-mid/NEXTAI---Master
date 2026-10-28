"""Shared plumbing for the HTTP LLM providers (Anthropic, OpenAI, OpenAI-compatible).

They talk to the vendors' REST APIs through httpx (already a dependency), so no vendor SDK
is needed. Each provider only builds its request and reads its response. Retry on 429/5xx,
the one JSON repair retry and the usage logging live here.
"""

from __future__ import annotations

import asyncio
import json
from abc import abstractmethod
from typing import Any

import httpx

from verifirm.core.config import Settings
from verifirm.core.logging import get_logger
from verifirm.core.ports.llm import LLMClient, LLMMessage, T
from verifirm.llm.json_output import parse_and_validate, repair_messages

log = get_logger(__name__)

# PENDING (DECISIONS.md): an LLM_TIMEOUT_S setting. Until then LLM calls use the larger of the
# generic HTTP timeout and this floor, because a memo takes longer than a registry lookup.
LLM_TIMEOUT_FLOOR_S = 90.0
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504, 529})


class LLMUnavailable(RuntimeError):
    """The provider could not be reached or kept failing. Never turned into an empty answer."""


class LLMConfigError(RuntimeError):
    """A provider setting is missing or wrong (API key, model name, base URL)."""


class HttpLLMClient(LLMClient):
    def __init__(self, settings: Settings, http: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self._http = http

    # ------------------------------------------------------------------ helpers
    def model_name(self, model: str | None) -> str:
        return model or self.settings.llm_model_default

    async def _client(self) -> httpx.AsyncClient:
        if self._http is None:
            timeout = max(self.settings.http_timeout_s, LLM_TIMEOUT_FLOOR_S)
            self._http = httpx.AsyncClient(timeout=timeout)
        return self._http

    async def post(self, url: str, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
        """POST JSON, retry transport errors / 429 / 5xx with backoff, return the parsed body."""
        attempts = max(1, self.settings.http_max_retries + 1)
        last_error = "unknown error"
        for attempt in range(attempts):
            try:
                response = await (await self._client()).post(url, headers=headers, json=payload)
            except httpx.TransportError as exc:
                last_error = type(exc).__name__
            else:
                if response.status_code < 400:
                    body: dict[str, Any] = response.json()
                    return body
                last_error = f"HTTP {response.status_code}"
                if response.status_code not in RETRY_STATUSES:
                    # The error body explains a bad request; it holds no prompt content.
                    raise LLMUnavailable(f"{self.provider}: {last_error}: {response.text[:300]}")
            if attempt < attempts - 1:
                await asyncio.sleep(0.5 * 2**attempt)
        raise LLMUnavailable(f"{self.provider}: failed after {attempts} attempts: {last_error}")

    def log_usage(self, model: str, input_tokens: int | None, output_tokens: int | None) -> None:
        log.info(
            "llm usage",
            extra={
                "provider": self.provider,
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            },
        )

    # ------------------------------------------------------------------ port
    @abstractmethod
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
        """The model's JSON answer as text. Validation happens in complete_json."""

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
        """Parse + re-validate as `schema`, with ONE repair retry that shows the model its error."""
        raw = await self.raw_json(
            system=system,
            messages=messages,
            schema=schema,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        try:
            return parse_and_validate(raw, schema)
        except ValueError as first:
            log.warning("llm output failed validation, retrying once")
            raw = await self.raw_json(
                system=system,
                messages=repair_messages(messages, raw, str(first)),
                schema=schema,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            try:
                return parse_and_validate(raw, schema)
            except ValueError as second:
                raise ValueError(
                    f"{self.provider} output failed validation after a repair retry: {second}"
                ) from second


def dump_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)
