import json

import httpx
import pytest
from pydantic import BaseModel

from verifirm.core.config import Settings
from verifirm.core.ports.llm import LLMMessage
from verifirm.llm import get_llm_client
from verifirm.llm.providers._http import LLMConfigError, LLMUnavailable
from verifirm.llm.providers.anthropic import AnthropicClient


class Out(BaseModel):
    a: int


def settings(**kw: object) -> Settings:
    base = {"anthropic_api_key": "k", "http_max_retries": 1, "llm_model_default": "m-default"}
    return Settings(_env_file=None, **{**base, **kw})  # type: ignore[arg-type]


def client(handler, **kw: object) -> AnthropicClient:  # type: ignore[no-untyped-def]
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return AnthropicClient(settings(**kw), http)


def tool_reply(payload: dict[str, object]) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "content": [{"type": "tool_use", "name": "emit_result", "input": payload}],
            "usage": {"input_tokens": 3, "output_tokens": 4},
        },
    )


USER = [LLMMessage(role="user", content="hi")]


async def test_complete_json_forces_the_tool_and_validates() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        seen["key"] = request.headers["x-api-key"]
        return tool_reply({"a": 5})

    out = await client(handler).complete_json(system="s", messages=USER, schema=Out, model="m-x")
    assert out == Out(a=5)
    assert seen["model"] == "m-x" and seen["key"] == "k"
    assert seen["tool_choice"] == {"type": "tool", "name": "emit_result"}
    assert seen["tools"][0]["input_schema"]["properties"]["a"]  # type: ignore[index]


async def test_default_model_comes_from_settings() -> None:
    models: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        models.append(json.loads(request.content)["model"])
        return tool_reply({"a": 1})

    await client(handler).complete_json(system="s", messages=USER, schema=Out)
    assert models == ["m-default"]


async def test_one_repair_retry_then_valueerror() -> None:
    calls: list[list[dict[str, str]]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(json.loads(request.content)["messages"])
        return tool_reply({"a": "nope"})

    with pytest.raises(ValueError):
        await client(handler).complete_json(system="s", messages=USER, schema=Out)
    assert len(calls) == 2
    assert "failed validation" in calls[1][-1]["content"]


async def test_retries_on_429_then_succeeds() -> None:
    n = {"i": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        n["i"] += 1
        return httpx.Response(429) if n["i"] == 1 else tool_reply({"a": 1})

    assert (await client(handler).complete_json(system="s", messages=USER, schema=Out)).a == 1


async def test_hard_failure_is_unavailable_not_empty() -> None:
    with pytest.raises(LLMUnavailable):
        await client(lambda r: httpx.Response(401, text="bad key")).complete_text(
            system="s", messages=USER
        )


async def test_complete_text_joins_text_blocks() -> None:
    reply = httpx.Response(200, json={"content": [{"type": "text", "text": "a"}, {"type": "text", "text": "b"}]})
    assert await client(lambda r: reply).complete_text(system="s", messages=USER) == "ab"


def test_missing_key_is_a_config_error_and_factory_builds_it() -> None:
    with pytest.raises(LLMConfigError):
        AnthropicClient(Settings(_env_file=None, anthropic_api_key=None))
    assert isinstance(get_llm_client(settings()), AnthropicClient)
