"""Forbidden-import checks (stdlib `ast` only). Keeps the packages independent, so 5 people can
work in parallel without stepping on each other.

Rules (verifirm/<area>, test folders excluded):
- schema imports nothing else from verifirm (the shared contract).
- core imports only schema + core.
- adapters never import agents / consolidation / scoring / persistence.
- an agent never imports another agent (agents.base is shared).
- scoring is pure: no LLM, no network, no adapters, no DB.
- only verifirm/llm talks to LLM SDKs. Only verifirm/persistence imports the DB stack.
- nothing in verifirm imports apps.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / "verifirm"

ALLOWED_INTERNAL: dict[str, set[str]] = {
    "schema": {"schema"},
    "core": {"schema", "core"},
    "adapters": {"schema", "core", "adapters", "llm"},
    "agents": {"schema", "core", "adapters", "llm", "agents"},
    "llm": {"schema", "core", "llm"},
    "scoring": {"schema", "core", "scoring"},
    "consolidation": {"schema", "core", "adapters", "llm", "consolidation"},
    "persistence": {"schema", "core", "persistence"},
}
LLM_SDKS = {"anthropic", "openai", "boto3", "aioboto3", "botocore"}
DB_STACK = {"sqlalchemy", "asyncpg", "alembic", "psycopg", "psycopg2"}
NETWORK = {"httpx", "requests", "aiohttp", "urllib3"}
FORBIDDEN_EXTERNAL: dict[str, set[str]] = {
    "schema": LLM_SDKS | DB_STACK | NETWORK | {"fastapi"},
    "core": LLM_SDKS | DB_STACK | {"fastapi"},
    "scoring": LLM_SDKS | DB_STACK | NETWORK,
    "agents": LLM_SDKS | DB_STACK,
    "adapters": LLM_SDKS | DB_STACK,
    "consolidation": LLM_SDKS | DB_STACK,
    "llm": DB_STACK,
    "persistence": LLM_SDKS,
}


def _module_name(path: Path) -> str:
    parts = list(path.relative_to(ROOT).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    module = _module_name(path)
    package = module if path.name == "__init__.py" else module.rsplit(".", 1)[0]
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package.split(".")
                base = base[: len(base) - (node.level - 1)]
                found.append(".".join(base + ([node.module] if node.module else [])))
            elif node.module:
                found.append(node.module)
    return found


def _sources() -> list[Path]:
    return sorted(
        p
        for p in PKG.rglob("*.py")
        if "tests" not in p.relative_to(PKG).parts and "migrations" not in p.relative_to(PKG).parts
    )


def _violations(path: Path) -> list[str]:
    rel = path.relative_to(PKG).parts
    area = rel[0] if len(rel) > 1 else None
    out: list[str] = []
    for imp in _imports(path):
        top = imp.split(".")[0]
        if top == "apps":
            out.append(f"imports apps ({imp})")
        if area is None:
            continue
        if top == "verifirm":
            parts = imp.split(".")
            target = parts[1] if len(parts) > 1 else ""
            if target and target not in ALLOWED_INTERNAL[area]:
                out.append(f"{area} must not import verifirm.{target} ({imp})")
            if area == "agents" and target == "agents" and len(parts) > 2 and len(rel) > 2:
                own = rel[1]
                other = parts[2]
                if other not in {"base", own}:
                    out.append(f"agent {own} imports another agent ({imp})")
        if top in FORBIDDEN_EXTERNAL.get(area, set()):
            out.append(f"{area} must not import {top}")
    return out


@pytest.mark.parametrize("path", _sources(), ids=lambda p: p.relative_to(ROOT).as_posix())
def test_no_forbidden_imports(path: Path) -> None:
    assert _violations(path) == []


def test_checker_catches_violations(tmp_path: Path) -> None:
    """Self-test: the rules really fire."""
    fake = PKG / "agents" / "identity" / "_probe_violation.py"
    fake.write_text(
        "from verifirm.agents.tax import rules\nimport anthropic\nimport apps.wiring\n",
        encoding="utf-8",
    )
    try:
        problems = _violations(fake)
    finally:
        fake.unlink()
    assert any("another agent" in p for p in problems)
    assert any("anthropic" in p for p in problems)
    assert any("apps" in p for p in problems)
