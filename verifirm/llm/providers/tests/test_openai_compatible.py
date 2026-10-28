import json

import httpx
import pytest
from pydantic import BaseModel

from verifirm.core.config import Settings
from verifirm.core.ports.llm import LLMMessage
from verifirm.llm import get_llm_client
from verifirm.llm.providers._http import LLMConfigError
from verifirm.llm.providers.openai_compatible import OpenAICompatibleClient


class Out(BaseModel):
    a: int


def settings(**kw: object) -> Settings:
    base = {
        "openai_compatible_base_url": "http://llm.example/v1/",
        "http_max_retries": 0,
        "llm_model_default": "llama",
    }
    return Settings(_env_file=None, **{**base, **kw})  # type: ignore[arg-type]


USER = [LLMMessage(role="user", content="hi")]


async def test_json_only_prompting_fenced_answer_and_repair() -> None:
    bodies: list[dict[str, object]] = []
    urls: list[str] = []
    answers = iter(['```json\n{"a": "bad"}\n```', 'Sure: {"a": 4}'])

    def handler(request: httpx.Request) -> httpx.Response:
        urls.append(str(request.url))
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": next(answers)}}]})

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    out = await OpenAICompatibleClient(settings(), http).complete_json(
        system="s", messages=USER, schema=Out
    )
    assert out.a == 4
    assert urls[0] == "http://llm.example/v1/chat/completions"
    assert "response_format" not in bodies[0]
    assert "JSON schema" in bodies[0]["messages"][0]["content"]  # type: ignore[index]
    assert "max_tokens" in bodies[0] and bodies[0]["temperature"] == 0.0


def test_needs_base_url_and_factory() -> None:
    with pytest.raises(LLMConfigError):
        OpenAICompatibleClient(Settings(_env_file=None))
    s = settings(llm_provider="openai_compatible")
    assert isinstance(get_llm_client(s), OpenAICompatibleClient)
