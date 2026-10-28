"""STUB. Owner: @role-5-ai-api. Claude via Amazon Bedrock (switch with LLM_PROVIDER=bedrock).

Why: IAM auth (no API key), AWS billing, data stays in an EU region (AWS_REGION, default
eu-central-1). Implement with `anthropic.AsyncAnthropicBedrock(aws_region=settings.aws_region)`:
the same request shape as providers/anthropic.py, so share the code. Bedrock model ids differ
from API ids (and may need a cross-region inference profile prefix such as "eu."), so put them in settings.
"""

from __future__ import annotations

from verifirm.core.config import Settings
from verifirm.core.ports.llm import LLMClient, LLMMessage, T


class BedrockClient(LLMClient):
    provider = "bedrock"

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
