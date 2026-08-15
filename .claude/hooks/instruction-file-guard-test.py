#!/usr/bin/env python3
"""Tests for instruction-file-guard.py.

Run: python3 .claude/hooks/instruction-file-guard-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_PATH = Path(__file__).with_name("instruction-file-guard.py")

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def run_hook(project_directory: Path, file_path: str):
    payload = json.dumps({"tool_input": {"file_path": file_path}})
    environment = dict(os.environ, CLAUDE_PROJECT_DIR=str(project_directory))
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH)], input=payload,
        capture_output=True, text=True, check=False, env=environment,
    )


with tempfile.TemporaryDirectory() as temporary_directory:
    workspace = Path(temporary_directory)

    result = run_hook(workspace, str(workspace / "CLAUDE.md"))
    check("editing CLAUDE.md is blocked", result.returncode == 2, str(result.returncode))
    check("the block teaches the walk path", "get the user's approval" in result.stderr, result.stderr)
    check("the block names the override marker", ".walk-approved" in result.stderr, result.stderr)

    result = run_hook(workspace, str(workspace / "sub" / "CLAUDE.local.md"))
    check("an identity file anywhere is blocked", result.returncode == 2)

    result = run_hook(workspace, str(workspace / ".claude" / "skills" / "new" / "SKILL.md"))
    check("creating under .claude/ is blocked (the creation gap)", result.returncode == 2)

    result = run_hook(workspace, str(workspace / ".claude" / "settings.json"))
    check("the hook's own wiring is protected", result.returncode == 2)

    result = run_hook(workspace, str(workspace / "docs" / "ordinary.md"))
    check("an ordinary file passes", result.returncode == 0, result.stderr)

    # The two carve-outs: harness working space, not machinery. Each was added
    # after a real write tripped the guard, and each is asserted against its
    # neighbours so a future widening cannot quietly take the protected paths
    # with it.
    result = run_hook(workspace, str(workspace / ".claude" / "jobs" / "ab12cd34" / "tmp" / "draft.txt"))
    check("a background job's scratch file passes", result.returncode == 0, result.stderr)

    result = run_hook(workspace, str(workspace / ".claude" / "worktrees" / "feature" / "src" / "app.py"))
    check("a file inside a worktree checkout passes", result.returncode == 0, result.stderr)

    result = run_hook(workspace, str(workspace / ".claude" / "worktrees" / "feature" / ".claude" / "settings.json"))
    check("a worktree's OWN .claude/ is still protected", result.returncode == 2)

    result = run_hook(workspace, str(workspace / ".claude" / "projects" / "-a-project" / "memory" / "fact.md"))
    check("the auto-memory is still protected", result.returncode == 2)

    result = run_hook(workspace, str(workspace / ".claude" / "jobs.json"))
    check("a file merely named jobs.json under .claude/ is still protected",
          result.returncode == 2)

    worktree = workspace / ".claude" / "worktrees" / "some-worktree"
    result = run_hook(workspace, str(worktree / "docs" / "ordinary.md"))
    check("an ordinary file in a worktree passes (the plumbing prefix is not the checkout's .claude)",
          result.returncode == 0, result.stderr)
    result = run_hook(workspace, str(worktree / ".walk-approved"))
    check("a worktree's own approval marker passes (the circular-block bug)",
          result.returncode == 0, result.stderr)
    result = run_hook(workspace, str(worktree / ".claude" / "hooks" / "some-hook.py"))
    check("a worktree's own .claude machinery is still blocked", result.returncode == 2)

    result = run_hook(workspace, "")
    check("a payload without a file path passes", result.returncode == 0)

    marker = workspace / ".walk-approved"
    marker.write_text("user approved: add the naming line (2026-08-07)\n", encoding="utf-8")
    result = run_hook(workspace, str(workspace / "CLAUDE.md"))
    check("an approved change passes once", result.returncode == 0, result.stderr)
    check("the marker is consumed by the pass", not marker.exists())
    result = run_hook(workspace, str(workspace / "CLAUDE.md"))
    check("the next unapproved change is blocked again", result.returncode == 2)

    marker.write_text("   \n", encoding="utf-8")
    result = run_hook(workspace, str(workspace / "CLAUDE.md"))
    check("an empty marker does not approve", result.returncode == 2)

print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
