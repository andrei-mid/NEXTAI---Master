"""The Claude Code ownership guard (.claude/hooks/ownership_guard.py) follows CODEOWNERS."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[2]
CODEOWNERS = (ROOT / "CODEOWNERS").read_text(encoding="utf-8")


def _guard() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "ownership_guard", ROOT / ".claude/hooks/ownership_guard.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


G = _guard()


def _decide(role: str | None, rel: str) -> str | None:
    return G.decide(str(ROOT / rel), role, ROOT, CODEOWNERS)


@pytest.mark.parametrize(
    "role,rel,allowed",
    [
        ("@andrei-mid", "verifirm/scoring/engine.py", True),
        ("@andrei-mid", "verifirm/schema/signals.py", True),
        ("@andrei-mid", "verifirm/agents/financials/agent.py", True),
        ("@andrei-mid", "verifirm/agents/media/agent.py", False),
        ("@role-3-official-agents", "verifirm/agents/financials/rules.py", True),
        ("@role-3-official-agents", "verifirm/adapters/anaf_bilant.py", True),
        ("@role-3-official-agents", "verifirm/adapters/anaf_v9.py", True),
        ("@role-3-official-agents", "verifirm/scoring/bands.py", False),
        ("@role-3-official-agents", "verifirm/core/config.py", False),
        ("@role-4-external-agents", "verifirm/agents/financials/agent.py", False),
        ("@role-1-database", "apps/worker/jobs/ingest_onrc.py", True),
        ("@role-1-database", "apps/worker/jobs/sync_portfolio.py", False),
        ("@role-5-ai-api", "apps/api/routes/runs.py", True),
        ("@role-6-frontend-demo", "fixtures/README.md", True),
        ("@role-4-external-agents", "docs/CHANGELOG.md", True),  # shared log
        ("@role-4-external-agents", "verifirm/adapters/README.md", True),  # shared status table
        ("@role-4-external-agents", "CLAUDE.md", False),
    ],
)
def test_ownership(role: str, rel: str, allowed: bool) -> None:
    assert (_decide(role, rel) is None) is allowed


def test_multiple_roles_and_case() -> None:
    assert _decide("@ROLE-4-external-agents, @andrei-mid", "verifirm/agents/media/agent.py") is None


def test_unset_role_is_denied_with_setup_instructions() -> None:
    reason = _decide(None, "verifirm/agents/media/agent.py")
    assert reason and "VERIFIRM_ROLE" in reason


def test_files_outside_the_repo_are_ignored(tmp_path: Path) -> None:
    assert G.decide(str(tmp_path / "x.py"), "@nobody", ROOT, CODEOWNERS) is None


def test_denial_points_to_the_pending_workflow() -> None:
    reason = _decide("@role-3-official-agents", "verifirm/schema/signals.py")
    assert reason and "@andrei-mid" in reason and "DECISIONS.md" in reason
