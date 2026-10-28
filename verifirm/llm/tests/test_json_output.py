from pathlib import Path

import pytest
from pydantic import BaseModel

from verifirm.core.impl_local.llm import FakeLLMClient
from verifirm.core.ports.llm import LLMClient, LLMMessage
from verifirm.llm.json_output import (
    complete_validated,
    load_prompt,
    parse_and_validate,
    split_prompt,
)


class Out(BaseModel):
    a: int
    b: str = "x"


def test_parse_strips_fences_and_prose() -> None:
    raw = 'Here you go:\n```json\n{"a": 1, "b": "}{"}\n```'
    assert parse_and_validate(raw, Out) == Out(a=1, b="}{")


def test_parse_takes_the_outermost_object() -> None:
    assert parse_and_validate('{"a": 2} {"a": 3}', Out).a == 2


@pytest.mark.parametrize("raw", ["no json", '{"a": ', '{"a": "not int"}'])
def test_parse_rejects_bad_output_with_valueerror(raw: str) -> None:
    with pytest.raises(ValueError):
        parse_and_validate(raw, Out)


class Flaky(LLMClient):
    def __init__(self, fail: int) -> None:
        self.fail = fail
        self.seen: list[str] = []

    async def complete_json(self, *, system, messages: list[LLMMessage], schema, **_):  # type: ignore[no-untyped-def]
        self.seen.append(messages[-1].content)
        if self.fail:
            self.fail -= 1
            raise ValueError("bad json")
        return schema(a=1)

    async def complete_text(self, **_):  # type: ignore[no-untyped-def]
        return ""


async def test_retries_once_and_shows_the_error() -> None:
    llm = Flaky(fail=1)
    out = await complete_validated(llm, system="s", user="u", schema=Out)
    assert out.a == 1
    assert "bad json" in llm.seen[1]


async def test_gives_up_after_the_retry() -> None:
    with pytest.raises(ValueError, match="after 2 attempts"):
        await complete_validated(Flaky(fail=5), system="s", user="u", schema=Out)


async def test_fake_client_passthrough() -> None:
    llm = FakeLLMClient(json_responses={"Out": {"a": 7}})
    assert (await complete_validated(llm, system="s", user="u", schema=Out)).a == 7


def test_load_prompt_fills_and_raises_on_missing(tmp_path: Path) -> None:
    p = tmp_path / "p.md"
    p.write_text('{{"k": 1}} {name}', encoding="utf-8")
    assert load_prompt(p, name="ok") == '{"k": 1} ok'
    with pytest.raises(KeyError):
        load_prompt(p)


def test_load_prompt_does_not_reparse_values(tmp_path: Path) -> None:
    p = tmp_path / "p.md"
    p.write_text("{x}", encoding="utf-8")
    assert load_prompt(p, x="{not a placeholder}") == "{not a placeholder}"


def test_split_prompt() -> None:
    assert split_prompt("# t\n**System:**\nsys\n**User:**\nusr\n") == ("sys", "usr")
    with pytest.raises(ValueError):
        split_prompt("no sections")
