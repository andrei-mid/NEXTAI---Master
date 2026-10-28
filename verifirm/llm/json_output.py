"""STUB. Owner: @role-5-ai-api. Schema-constrained output + Pydantic re-validation, shared by providers.

Implement:
- parse_and_validate(raw_text, schema): strip code fences, take the outermost JSON object,
  then schema.model_validate_json. Raise ValueError with the pydantic error text.
- complete_validated(llm, *, system, user, schema, model, retries=1): call llm.complete_json.
  On ValueError, retry once, appending the validation error to the prompt ("fix this JSON").
  Never return unvalidated data. Never let raw model text out of this function.
- load_prompt(path, **vars): read a prompts/*.md file and fill {placeholders} (str.format_map
  with a dict that raises on missing keys).
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from verifirm.core.ports.llm import LLMClient, T


def parse_and_validate(raw_text: str, schema: type[T]) -> T:
    raise NotImplementedError


async def complete_validated(
    llm: LLMClient,
    *,
    system: str,
    user: str,
    schema: type[T],
    model: str | None = None,
    retries: int = 1,
) -> T:
    raise NotImplementedError


def load_prompt(path: Path, **variables: object) -> str:
    raise NotImplementedError


__all__ = ["BaseModel", "complete_validated", "load_prompt", "parse_and_validate"]
