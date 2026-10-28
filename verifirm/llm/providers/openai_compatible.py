"""Any OpenAI-compatible endpoint (e.g. Featherless, local vLLM).

Same as OpenAIClient with base_url / api_key from settings. Many of these servers do NOT support
strict json_schema, so the schema goes in the prompt ("JSON only") and the answer is
re-validated, with one repair retry (HttpLLMClient.complete_json).
"""

from __future__ import annotations

import httpx

from verifirm.core.config import Settings
from verifirm.llm.providers._http import LLMConfigError
from verifirm.llm.providers.openai import OpenAIClient


class OpenAICompatibleClient(OpenAIClient):
    provider = "openai_compatible"
    token_param = "max_tokens"
    use_json_schema = False
    send_temperature = True

    def __init__(self, settings: Settings, http: httpx.AsyncClient | None = None) -> None:
        if not settings.openai_compatible_base_url:
            raise LLMConfigError("LLM_PROVIDER=openai_compatible needs OPENAI_COMPATIBLE_BASE_URL")
        super().__init__(settings, http)
        self.base_url = settings.openai_compatible_base_url.rstrip("/")

    def api_key(self) -> str | None:
        return self.settings.openai_compatible_api_key or "none"  # local servers often need none
