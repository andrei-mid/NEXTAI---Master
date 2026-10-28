import json

import httpx
import pytest
from pydantic import BaseModel

from verifirm.core.config import Settings
from verifirm.core.ports.llm import LLMMessage
from verifirm.llm.providers._http import LLMConfigError
from verifirm.llm.providers.openai import OpenAIClient, strict_schema


class Inner(BaseModel):
    n: int = 1


class Out(BaseModel):
    a: int
    inner: Inner = Inner()
    tags: list[str] = []


def settings(**kw: object) -> Settings:
    base = {"openai_api_key": "k", "http_max_retries": 0, "llm_model_default": "gpt-test"}
    return Settings(_env_file=None, **{**base, **kw})  # type: ignore[arg-type]


USER = [LLMMessage(role="user", content="hi")]


def reply(content: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "choices": [{"message": {"content": content}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 2},
        },
    )


def test_strict_schema_requires_everything_and_closes_objects() -> None:
    schema = strict_schema(Out.model_json_schema())
    assert schema["additionalProperties"] is False
    assert schema["required"] == ["a", "inner", "tags"]
    inner = schema["$defs"]["Inner"]
    assert inner["additionalProperties"] is False and inner["required"] == ["n"]
    assert "default" not in json.dumps(schema)


async def test_complete_json_sends_strict_json_schema() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        seen["auth"] = request.headers["authorization"]
        return reply('{"a": 3, "inner": {"n": 2}, "tags": []}')

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    out = await OpenAIClient(settings(), http).complete_json(system="s", messages=USER, schema=Out)
    assert out.a == 3 and out.inner.n == 2
    assert seen["auth"] == "Bearer k"
    assert seen["response_format"]["json_schema"]["strict"] is True  # type: ignore[index]
    assert seen["messages"][0] == {"role": "system", "content": "s"}  # type: ignore[index]
    assert "temperature" not in seen


async def test_refusal_is_an_error_not_an_answer() -> None:
    body = {"choices": [{"message": {"content": None, "refusal": "no"}}]}
    http = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=body)))
    with pytest.raises(ValueError, match="refused"):
        await OpenAIClient(settings(), http).complete_json(system="s", messages=USER, schema=Out)


async def test_claude_model_name_is_rejected_for_openai() -> None:
    http = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: reply("x")))
    client = OpenAIClient(settings(llm_model_default="claude-sonnet-5-5"), http)
    with pytest.raises(LLMConfigError):
        await client.complete_text(system="s", messages=USER)


def test_needs_api_key() -> None:
    with pytest.raises(LLMConfigError):
        OpenAIClient(Settings(_env_file=None, openai_api_key=None))
