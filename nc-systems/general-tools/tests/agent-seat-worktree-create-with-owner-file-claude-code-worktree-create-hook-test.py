#!/usr/bin/env python3
"""Tests for nc-systems/general-tools/agent-seat-worktree-create-with-owner-file-claude-code-worktree-create-hook.py,
run alone.

Each case feeds the hook the JSON Claude Code feeds it, on a scratch machine: a HOME with one
agent-seat and a clone with a local bare origin, as
scripts/agent-seat-worktree-create-with-owner-file-test.py builds it.
nc-systems/general-tools/tests/agent-seat-worktree-create-with-owner-file-claude-code-worktree-create-hook-real-claude-code-test.py
tries the hook with the installed Claude Code.

Run: python3 nc-systems/general-tools/tests/agent-seat-worktree-create-with-owner-file-claude-code-worktree-create-hook-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
HOOK = REPO_ROOT / "nc-systems" / "general-tools" / "agent-seat-worktree-create-with-owner-file-claude-code-worktree-create-hook.py"
SEAT = "seat-a"
SUBAGENT_NAME = "agent-a0123456789abcdef"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_git_environment_fixture = load_module("git_redirecting_environment_removal_test_fixture",
                                       REPO_ROOT / "scripts" / "git-redirecting-environment-removal-test-fixture.py")
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()
owner_file = load_module("worktree_owner_file_read_and_write", REPO_ROOT / "scripts" / "worktree-owner-file-read-and-write.py")

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def git(cwd, *arguments, environment):
    return subprocess.run(["git", *arguments], cwd=cwd, env=environment, capture_output=True, text=True,
                          check=True).stdout


def worktree_records(clone, environment):
    """{path: the porcelain lines of its record} from git worktree list."""
    records = {}
    for block in git(clone, "worktree", "list", "--porcelain", environment=environment).strip().split("\n\n"):
        lines = block.splitlines()
        records[lines[0].removeprefix("worktree ")] = lines[1:]
    return records


def run_hook(hook_input, cwd, environment):
    text = hook_input if isinstance(hook_input, str) else json.dumps(hook_input)
    completed = subprocess.run([sys.executable, str(HOOK)], input=text, cwd=cwd, env=environment,
                               capture_output=True, text=True, check=False)
    return completed.returncode, completed.stdout, completed.stderr


def test_hook_alone():
    root = Path(os.path.realpath(tempfile.mkdtemp(prefix="worktree-create-hook-test-")))
    try:
        home = root / "home"
        handoffs = home / ".claude" / "handoffs"
        handoffs.mkdir(parents=True)
        (handoffs / f"{SEAT}-handoff.md").write_text("handoff\n")
        (home / "agents" / SEAT).mkdir(parents=True)
        (root / "empty-gitconfig").write_text("")
        environment = {key: value for key, value in os.environ.items()
                       if not key.startswith(("GIT_", "CLAUDE_", "NEDSCHORUS_"))}
        environment.update(HOME=str(home), GIT_CONFIG_NOSYSTEM="1",
                           GIT_CONFIG_GLOBAL=str(root / "empty-gitconfig"), GIT_AUTHOR_NAME=SEAT)
        origin, clone = root / "origin.git", root / "clone"
        git(root, "init", "--quiet", "--bare", "--initial-branch=main", str(origin), environment=environment)
        clone.mkdir()
        git(clone, "init", "--quiet", "--initial-branch=main", environment=environment)
        git(clone, "-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid", "commit", "--quiet",
            "--allow-empty", "-m", "base", environment=environment)
        git(clone, "remote", "add", "origin", str(origin), environment=environment)
        git(clone, "push", "--quiet", "origin", "main", environment=environment)
        hook_input = {"session_id": "s", "hook_event_name": "WorktreeCreate", "cwd": str(clone),
                      "name": SUBAGENT_NAME}

        expected = clone / ".claude" / "worktrees" / f"worktree-{SUBAGENT_NAME}"
        code, out, err = run_hook(hook_input, root, environment)
        record = worktree_records(clone, environment).get(str(expected), [])
        check("the hook makes the worktree in the reference-checkout's .claude/worktrees and prints only its path",
              code == 0 and out == f"{expected}\n", f"exit {code}, stdout {out!r}, stderr {err}")
        main_commit = git(clone, "rev-parse", "origin/main", environment=environment).strip()
        check("the worktree checks out a new branch worktree-<name> cut from origin/main, unlocked",
              f"branch refs/heads/worktree-{SUBAGENT_NAME}" in record and f"HEAD {main_commit}" in record
              and not any(line.startswith("locked") for line in record), str(record))
        check("the worktree's owner file names the agent-seat GIT_AUTHOR_NAME names",
              owner_file.worktree_owner_file_read(expected) == {"owner_kind": owner_file.OWNER_AGENT_SEAT,
                                                                 "agent_seat": SEAT}, "")

        code, out, err = run_hook({**hook_input, "cwd": str(expected), "name": "agent-afedcba9876543210"},
                                  root, environment)
        check("asked from inside a worktree, the hook still makes the new one under the reference-checkout",
              code == 0 and out == f"{clone / '.claude' / 'worktrees' / 'worktree-agent-afedcba9876543210'}\n",
              f"exit {code}, stdout {out!r}, stderr {err}")

        for label, bad_input in (("stdin that is not JSON", "not json"),
                                 ("stdin JSON with no name", {"cwd": str(clone)}),
                                 ("stdin JSON with no cwd", {"name": "agent-a1111111111111111"}),
                                 ("stdin JSON that is not an object", ["agent-a1111111111111111"])):
            before = worktree_records(clone, environment)
            code, out, err = run_hook(bad_input, root, environment)
            check(f"{label} fails with exit 1, a FAILED message, no path and no worktree",
                  code == 1 and out == "" and "FAILED:" in err and "no worktree was made" in err
                  and worktree_records(clone, environment) == before, f"exit {code}, stdout {out!r}, stderr {err}")

        before = worktree_records(clone, environment)
        code, out, err = run_hook({**hook_input, "name": "agent-a2222222222222222"}, root,
                                  {**environment, "GIT_AUTHOR_NAME": "not-an-agent-seat"})
        check("a creator that refuses fails the hook with exit 1, naming the creator's exit, its message passed through",
              code == 1 and out == "" and "agent-seat-worktree-create-with-owner-file.py exited 2" in err
              and "REFUSED: GIT_AUTHOR_NAME is 'not-an-agent-seat'" in err
              and worktree_records(clone, environment) == before, f"exit {code}, stdout {out!r}, stderr {err}")
    finally:
        shutil.rmtree(root, ignore_errors=True)


test_hook_alone()
print(f"FAILED: {len(failures)} failed" if failures else "PASSED: 0 failed")
sys.exit(1 if failures else 0)
