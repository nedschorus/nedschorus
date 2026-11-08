#!/usr/bin/env python3
"""Tests for the agent-home refusal in scripts/git-client-side-hooks/pre-commit,
which refuses a commit in a worktree whose own git directory holds
agent-home-marker, and lets a commit through in any other worktree.

Run: python3 scripts/git-client-side-hooks-pre-commit-agent-home-refusal-test.py
Prints one line per case and exits non-zero if any case fails. Every case
commits with real git in throwaway repositories under a temporary directory,
with core.hooksPath pointed at this checkout's copy of the hook directory,
except the last, which runs the hook file directly with a stub git that fails.
The session and identity variables of the agent-session running the suite are
removed, and global and system git config are shut out.
"""

import importlib.util
import os
import subprocess
import sys
import tempfile
from pathlib import Path

_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    Path(__file__).resolve().with_name(
        "git-redirecting-environment-removal-test-fixture.py"))
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()

HOOK_DIRECTORY = Path(__file__).resolve().with_name("git-client-side-hooks")
MARKER_NAME = "agent-home-marker"
SESSION = {"CLAUDE_CODE_SESSION_ID": "00000000-fake-4000-8000-0000000000a1"}
SEAT_IDENTITY = {"GIT_AUTHOR_NAME": "seat-a", "GIT_AUTHOR_EMAIL": "seat-a@nedschorus.invalid",
                 "GIT_COMMITTER_NAME": "seat-a", "GIT_COMMITTER_EMAIL": "seat-a@nedschorus.invalid"}
REMOVED_VARIABLES = ("CLAUDE_CODE_SESSION_ID", "CLAUDE_CODE_BRIDGE_SESSION_ID", *SEAT_IDENTITY)

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def environment(root: Path, extra):
    env = {key: value for key, value in os.environ.items() if key not in REMOVED_VARIABLES}
    empty_global = root / "empty-gitconfig"
    empty_global.touch()
    env["GIT_CONFIG_GLOBAL"] = str(empty_global)
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env.update(extra)
    return env


def git(root: Path, directory: Path, *arguments, extra=None, check_exit=True):
    completed = subprocess.run(["git", *arguments], cwd=str(directory),
                               env=environment(root, extra or {}),
                               capture_output=True, text=True, timeout=30)
    if check_exit and completed.returncode != 0:
        raise RuntimeError(f"git {' '.join(arguments)} failed: {completed.stderr.strip()}")
    return completed


def make_clone(root: Path) -> Path:
    clone = root / "clone"
    clone.mkdir()
    git(root, clone, "init", "--quiet", "--initial-branch=main")
    (clone / "base.txt").write_text("base\n")
    git(root, clone, "add", "base.txt")
    git(root, clone, "-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid",
        "commit", "--quiet", "-m", "Base commit")
    git(root, clone, "config", "user.name", "unconfigured-agent")
    git(root, clone, "config", "user.email", "unconfigured-agent@nedschorus.invalid")
    git(root, clone, "config", "core.hooksPath", str(HOOK_DIRECTORY))
    return clone


def add_worktree(root: Path, clone: Path, name: str, marked: bool) -> Path:
    worktree = root / name
    git(root, clone, "worktree", "add", "--quiet", "--detach", str(worktree), "main")
    if marked:
        git_directory = git(root, worktree, "rev-parse", "--absolute-git-dir").stdout.strip()
        (Path(git_directory) / MARKER_NAME).touch()
    return worktree


def attempt_commit(root: Path, worktree: Path, extra):
    with open(worktree / "change.txt", "a") as handle:
        handle.write("line\n")
    git(root, worktree, "add", "change.txt")
    return git(root, worktree, "commit", "--quiet", "-m", "A change", extra=extra,
               check_exit=False)


def head(root: Path, worktree: Path) -> str:
    return git(root, worktree, "rev-parse", "HEAD").stdout.strip()


def main() -> int:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        clone = make_clone(root)
        agent_home = add_worktree(root, clone, "agent-home", marked=True)
        topic = add_worktree(root, clone, "topic-worktree", marked=False)
        git(root, topic, "switch", "--quiet", "-c", "topic")

        before = head(root, agent_home)
        refused = attempt_commit(root, agent_home, {**SESSION, **SEAT_IDENTITY})
        check("an agent-session's commit in an agent-home is refused",
              refused.returncode != 0 and head(root, agent_home) == before,
              refused.stderr)
        check("the refusal names the agent-home and why",
              f"pre-commit: this commit is refused, because {agent_home.resolve()} is an "
              "agent-home" in refused.stderr, refused.stderr)
        check("the refusal says where to commit instead, with the clone's worktrees directory",
              f"worktree add -b <branch name> {clone.resolve()}/.claude/worktrees/"
              "<directory name> HEAD" in refused.stderr, refused.stderr)

        refused_outside_session = attempt_commit(
            root, agent_home, {"GIT_AUTHOR_NAME": "Ned", "GIT_AUTHOR_EMAIL": "ned@example.invalid",
                               "GIT_COMMITTER_NAME": "Ned",
                               "GIT_COMMITTER_EMAIL": "ned@example.invalid"})
        check("a commit outside any Claude session is refused in an agent-home too",
              refused_outside_session.returncode != 0 and head(root, agent_home) == before,
              refused_outside_session.stderr)

        git(root, clone, "switch", "--quiet", "-c", "side")
        (clone / "side.txt").write_text("side\n")
        git(root, clone, "add", "side.txt")
        git(root, clone, "commit", "--quiet", "-m", "Side commit", extra=SEAT_IDENTITY)
        git(root, clone, "switch", "--quiet", "main")
        git(root, agent_home, "reset", "--quiet", "--hard", "HEAD")
        merged = git(root, agent_home, "merge", "--no-ff", "--no-edit", "side",
                     extra={**SESSION, **SEAT_IDENTITY}, check_exit=False)
        check("a merge commit in an agent-home is refused, through pre-merge-commit",
              merged.returncode != 0 and head(root, agent_home) == before
              and "is an agent-home" in merged.stderr, merged.stdout + merged.stderr)
        git(root, agent_home, "merge", "--abort", check_exit=False)

        allowed = attempt_commit(root, topic, {**SESSION, **SEAT_IDENTITY})
        check("an agent-session's commit in a worktree with no marker goes through",
              allowed.returncode == 0, allowed.stderr)

        stubs = root / "stubs"
        stubs.mkdir()
        (stubs / "git").write_text("#!/bin/sh\necho 'fatal: stub git fails' >&2\nexit 128\n")
        (stubs / "git").chmod(0o755)
        stub_environment = environment(root, SESSION)
        stub_environment["PATH"] = f"{stubs}{os.pathsep}{stub_environment['PATH']}"
        failed = subprocess.run(["sh", str(HOOK_DIRECTORY / "pre-commit")], cwd=str(topic),
                                env=stub_environment, capture_output=True, text=True,
                                timeout=30)
        check("when git cannot name the worktree's git directory, the commit is refused and said",
              failed.returncode != 0
              and "could not tell whether this worktree is an agent-home" in failed.stderr,
              failed.stderr)

    print(f"\n{len(failures)} failure(s)" if failures else "\nall cases passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
