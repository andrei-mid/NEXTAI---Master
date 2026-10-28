"""The ONLY place that talks to LLM providers. Everything else uses the LLMClient port.

D3: default provider = Claude via the direct Anthropic API. Bedrock, OpenAI and
OpenAI-compatible (e.g. Featherless) are switchable with LLM_PROVIDER. "fake" is offline.
"""

from __future__ import annotations

from verifirm.core.config import Settings
from verifirm.core.ports.llm import LLMClient


def get_llm_client(settings: Settings) -> LLMClient:
    """Build the configured provider. Providers are imported lazily (their SDKs are optional)."""
    provider = settings.llm_provider
    if provider == "fake":
        from verifirm.core.impl_local.llm import FakeLLMClient

        return FakeLLMClient()
    if provider == "anthropic":
        from verifirm.llm.providers.anthropic import AnthropicClient

        return AnthropicClient(settings)
    if provider == "bedrock":
        from verifirm.llm.providers.bedrock import BedrockClient

        return BedrockClient(settings)
    if provider == "openai":
        from verifirm.llm.providers.openai import OpenAIClient

        return OpenAIClient(settings)
    if provider == "openai_compatible":
        from verifirm.llm.providers.openai_compatible import OpenAICompatibleClient

        return OpenAICompatibleClient(settings)
    raise ValueError(f"unknown LLM provider {provider!r}")
