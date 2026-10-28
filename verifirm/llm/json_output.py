"""Schema-constrained output + Pydantic re-validation, shared by the providers and the callers.

Raw model text never leaves this module: callers get a validated model or a ValueError.
"""

from __future__ import annotations

import re
from collections import UserDict
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from verifirm.core.logging import get_logger
from verifirm.core.ports.llm import LLMClient, LLMMessage, T

log = get_logger(__name__)

_FENCE = re.compile(r"^\s*```[A-Za-z0-9_-]*\s*\n?|\n?```\s*$")


def _outermost_object(text: str) -> str:
    """The first balanced {...} in `text`, respecting JSON strings. ValueError if none."""
    start = text.find("{")
    if start < 0:
        raise ValueError("no JSON object found in the model output")
    depth = 0
    in_string = False
    escaped = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
        elif ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    raise ValueError("unterminated JSON object in the model output")


def parse_and_validate(raw_text: str, schema: type[T]) -> T:
    """Strip code fences, take the outermost JSON object, validate it as `schema`."""
    stripped = _FENCE.sub("", raw_text.strip())
    candidate = _outermost_object(stripped)
    try:
        return schema.model_validate_json(candidate)
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc


def repair_messages(messages: list[LLMMessage], raw: str, error: str) -> list[LLMMessage]:
    """The conversation extended with a 'fix this JSON' turn (used for the one retry)."""
    return [
        *messages,
        LLMMessage(role="assistant", content=raw),
        LLMMessage(
            role="user",
            content=(
                "Your previous answer failed validation. Return ONLY the corrected JSON "
                f"object, nothing else.\nValidation error:\n{error}"
            ),
        ),
    ]


async def complete_validated(
    llm: LLMClient,
    *,
    system: str,
    user: str,
    schema: type[T],
    model: str | None = None,
    retries: int = 1,
) -> T:
    """`llm.complete_json` with `retries` extra attempts on ValueError (error text appended).

    Never returns unvalidated data: the port already re-validates, and a final failure raises.
    """
    messages = [LLMMessage(role="user", content=user)]
    last: ValueError | None = None
    for attempt in range(retries + 1):
        try:
            return await llm.complete_json(
                system=system, messages=messages, schema=schema, model=model
            )
        except ValueError as exc:
            last = exc
            log.warning("llm output failed validation", extra={"attempt": attempt + 1})
            messages = [
                LLMMessage(
                    role="user",
                    content=f"{user}\n\nFix this JSON. The previous answer was invalid:\n{exc}",
                )
            ]
    raise ValueError(f"LLM output failed validation after {retries + 1} attempts: {last}")


class _Strict(UserDict[str, Any]):
    def __missing__(self, key: str) -> Any:
        raise KeyError(f"prompt placeholder {{{key}}} has no value")


def load_prompt(path: Path, **variables: object) -> str:
    """Read a prompts/*.md file and fill {placeholders}. A missing variable raises KeyError.

    Literal braces in a prompt (JSON examples) are written doubled: {{ and }}.
    """
    return path.read_text(encoding="utf-8").format_map(_Strict(variables))


def split_prompt(text: str) -> tuple[str, str]:
    """Split a prompt file laid out as `**System:** ... **User:** ...` into (system, user)."""
    match = re.search(r"\*\*System:\*\*(.*?)\*\*User:\*\*(.*)", text, re.DOTALL)
    if match is None:
        raise ValueError("prompt file needs **System:** and **User:** sections")
    return match.group(1).strip(), match.group(2).strip()


__all__ = [
    "BaseModel",
    "complete_validated",
    "load_prompt",
    "parse_and_validate",
    "repair_messages",
    "split_prompt",
]
