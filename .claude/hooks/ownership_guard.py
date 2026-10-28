"""Claude Code PreToolUse hook: refuse edits to files another teammate owns (per CODEOWNERS).

Each teammate sets, in their own (git-ignored) .claude/settings.local.json:
    {"env": {"VERIFIRM_ROLE": "@their-handle"}}        # several: "@a,@b"
The hook allows an Edit/Write only when one of those owners is listed for the file in
CODEOWNERS (last matching line wins, like GitHub). Everything else is denied with a message
telling Claude to open a PENDING entry in docs/DECISIONS.md instead.

Always editable by everyone: SHARED_FILES (the shared logs every Claude must write to).
Stdlib only: runs with any Python 3 (`uv run --no-project`).
"""

from __future__ import annotations

import fnmatch
import json
import os
import sys
from pathlib import Path

# Logs every Claude is asked to update (CLAUDE.md "Definition of done"). GitHub CODEOWNERS
# still requires the owner's review for them on a PR.
SHARED_FILES = {
    "docs/CHANGELOG.md",
    "docs/DECISIONS.md",
    "docs/RULES.md",
    "docs/SOURCES.md",
    "verifirm/adapters/README.md",
}


def repo_root() -> Path:
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    return Path(env).resolve() if env else Path(__file__).resolve().parents[2]


def parse_codeowners(text: str) -> list[tuple[str, list[str]]]:
    rules = []
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        pattern, *owners = line.split()
        rules.append((pattern, [o.lower() for o in owners]))
    return rules


def matches(pattern: str, rel: str) -> bool:
    """Subset of CODEOWNERS/gitignore syntax used in this repo: `*`, `/dir/`, `/file`, `/x_*`."""
    if pattern == "*":
        return True
    anchored = pattern.startswith("/")
    pat = pattern.lstrip("/")
    if pat.endswith("/"):
        return rel.startswith(pat) if anchored else f"/{pat}" in f"/{rel}"
    if any(ch in pat for ch in "*?["):
        return (
            fnmatch.fnmatch(rel, pat) if anchored else fnmatch.fnmatch(rel.rsplit("/", 1)[-1], pat)
        )
    return (
        rel == pat or rel.startswith(pat + "/")
        if anchored
        else rel.endswith("/" + pat) or rel == pat
    )


def owners_of(rel: str, rules: list[tuple[str, list[str]]]) -> list[str]:
    found: list[str] = []
    for pattern, owners in rules:
        if matches(pattern, rel):
            found = owners  # last match wins
    return found


def decide(file_path: str, role_env: str | None, root: Path, codeowners_text: str) -> str | None:
    """Return a denial reason, or None to allow."""
    try:
        rel = Path(file_path).resolve().relative_to(root).as_posix()
    except ValueError:
        return None  # outside the repo: not our business
    if rel in SHARED_FILES:
        return None
    if not role_env:
        return (
            "VERIFIRM_ROLE is not set, so the ownership guard cannot tell who you are. Ask the human "
            'to add {"env": {"VERIFIRM_ROLE": "@their-github-handle"}} to .claude/settings.local.json '
            "(see CLAUDE.md, section 2), then restart Claude Code."
        )
    mine = {r.strip().lower() for r in role_env.split(",") if r.strip()}
    owners = owners_of(rel, parse_codeowners(codeowners_text))
    if not owners or mine & set(owners):
        return None
    return (
        f"{rel} is owned by {', '.join(owners)} (CODEOWNERS), not by {', '.join(sorted(mine))}. "
        "Don't edit it. Stay inside your folder: add a PENDING entry to docs/DECISIONS.md "
        "describing the change you need and why, tell the human, and continue with a local "
        "workaround (CLAUDE.md, 'Stay inside your folder')."
    )


def main() -> int:
    payload = json.load(sys.stdin)
    tool_input = payload.get("tool_input") or {}
    file_path = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not file_path:
        return 0
    root = repo_root()
    codeowners = root / "CODEOWNERS"
    if not codeowners.exists():
        return 0
    reason = decide(
        file_path, os.environ.get("VERIFIRM_ROLE"), root, codeowners.read_text(encoding="utf-8")
    )
    if reason is not None:
        json.dump(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            },
            sys.stdout,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
