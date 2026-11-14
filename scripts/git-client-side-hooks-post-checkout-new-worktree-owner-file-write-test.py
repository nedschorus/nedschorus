#!/usr/bin/env python3
"""Tests for scripts/git-client-side-hooks/post-checkout and the program it runs,
scripts/git-client-side-hooks-post-checkout-new-worktree-owner-file-write.py.

Run: python3 scripts/git-client-side-hooks-post-checkout-new-worktree-owner-file-write-test.py
Prints one line per case and exits non-zero if any case fails. Each case runs a real
`git worktree add` in a throwaway clone whose core.hooksPath is this checkout's hook
directory, with HOME pointed at a scratch directory holding the agent-seats' directories
and handoff records, so the hook reads no real agent-seat.
"""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    Path(__file__).resolve().with_name("git-redirecting-environment-removal-test-fixture.py"))
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()

SCRIPTS = Path(__file__).resolve().parent
HOOK_DIRECTORY = SCRIPTS / "git-client-side-hooks"
PROGRAM = SCRIPTS / "git-client-side-hooks-post-checkout-new-worktree-owner-file-write.py"
SEAT = "seat-a"

# Forks; the parent exits at once, so the child is reparented and runs the command with no
# `claude` among its parents, then writes its exit code and stderr, renamed into place whole.
ORPHANED_COMMAND_RUNNER = """
import json, os, subprocess, sys
if os.fork():
    os._exit(0)
result, command = sys.argv[1], sys.argv[2:]
finished = subprocess.run(command, capture_output=True, text=True, check=False)
with open(result + ".partial", "w") as stream:
    json.dump({"returncode": finished.returncode, "stderr": finished.stderr}, stream)
os.replace(result + ".partial", result)
"""
ORPHANED_COMMAND_TIMEOUT_SECONDS = 120

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


class ScratchMachine:
    """A HOME with one agent-seat, SEAT, its agent-home a worktree of a throwaway clone."""

    def __init__(self, root, hook_directory=HOOK_DIRECTORY):
        self.home = root / "home"
        self.clone = self.home / "Projects" / "nedschorus"
        self.agents = self.home / "agents"
        handoffs = self.home / ".claude" / "handoffs"
        handoffs.mkdir(parents=True)
        (handoffs / f"{SEAT}-handoff.md").write_text("handoff\n")
        (handoffs / "bad seat-handoff.md").write_text("handoff\n")
        (self.agents / "bad seat").mkdir(parents=True)
        self.environment = {key: value for key, value in os.environ.items()
                            if not key.startswith(("GIT_", "CLAUDE_", "NEDSCHORUS_"))}
        self.environment.update(HOME=str(self.home), GIT_CONFIG_NOSYSTEM="1",
                                GIT_CONFIG_GLOBAL=str(root / "empty-gitconfig"))
        (root / "empty-gitconfig").write_text("")
        self.clone.mkdir(parents=True)
        self.branches = 0
        self.git({}, "init", "--quiet", "--initial-branch=main")
        self.git({}, "-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid",
                 "commit", "--quiet", "--allow-empty", "-m", "base")
        self.git({}, "config", "core.hooksPath", str(hook_directory))
        self.worktree_add(self.agents / SEAT, author=SEAT)

    def git(self, extra_environment, *arguments, cwd=None):
        return subprocess.run(["git", *arguments], cwd=cwd or self.clone,
                              env={**self.environment, **extra_environment},
                              capture_output=True, text=True, check=False)

    def worktree_add(self, path, author=None, wrapper=None, with_no_claude_parent=False):
        """Run `git worktree add -b <new branch> <path>`. wrapper, when given, is a command that
        runs the git command line it is given as its last argument. with_no_claude_parent runs
        git in an orphaned process, which the system reparents away from every `claude`
        process, such as the one running this test."""
        environment = {**self.environment,
                       **({} if author is None else {"GIT_AUTHOR_NAME": author})}
        self.branches += 1
        command = ["git", "worktree", "add", "--quiet", "-b", f"branch-{self.branches}", str(path)]
        if wrapper is not None:
            command = [*wrapper, " ".join(command)]
        if not with_no_claude_parent:
            return subprocess.run(command, cwd=self.clone, env=environment,
                                  capture_output=True, text=True, check=False)
        result = self.clone.parent / f"orphaned-git-result-{self.branches}.json"
        subprocess.run([sys.executable, "-c", ORPHANED_COMMAND_RUNNER, str(result), *command],
                       cwd=self.clone, env=environment, check=True)
        deadline = time.monotonic() + ORPHANED_COMMAND_TIMEOUT_SECONDS
        while not result.is_file() and time.monotonic() < deadline:
            time.sleep(0.05)
        if not result.is_file():
            return subprocess.CompletedProcess(command, -1, "", "the orphaned git never finished")
        finished = json.loads(result.read_text())
        return subprocess.CompletedProcess(command, finished["returncode"], "", finished["stderr"])

    def owner_file(self, worktree):
        located = subprocess.run(["git", "-C", str(worktree), "rev-parse", "--absolute-git-dir"],
                                 env=self.environment, capture_output=True, text=True, check=True)
        path = Path(located.stdout.strip()) / "worktree-owner.json"
        return json.loads(path.read_text()) if path.is_file() else None


def main():
    root = Path(tempfile.mkdtemp(prefix="post-checkout-owner-file-test-")).resolve()
    try:
        run_cases(root)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    if failures:
        print(f"{len(failures)} case(s) failed")
        return 1
    print("all cases passed")
    return 0


def run_cases(root):
    machine = ScratchMachine(root / "one")

    check("an agent-seat's own agent-home gets no owner file",
          machine.owner_file(machine.agents / SEAT) is None,
          f"owner file: {machine.owner_file(machine.agents / SEAT)}")

    topic = machine.agents / f"{SEAT}-worktrees" / "topic"
    added = machine.worktree_add(topic, author=SEAT)
    check("a worktree an agent-seat makes for its work names that agent-seat",
          added.returncode == 0
          and machine.owner_file(topic) == {"owner_kind": "agent-seat", "agent_seat": SEAT},
          f"exit {added.returncode}, stderr {added.stderr!r}, owner {machine.owner_file(topic)}")
    check("a written owner file prints nothing", added.stderr == "", repr(added.stderr))

    for label, author in (("names no agent-seat", "someone"), ("is unset", None)):
        path = root / f"by-hand-{label.replace(' ', '-')}"
        added = machine.worktree_add(path, author=author)
        check(f"a worktree made while GIT_AUTHOR_NAME {label} gets no owner file, silently",
              added.returncode == 0 and machine.owner_file(path) is None and added.stderr == "",
              f"exit {added.returncode}, stderr {added.stderr!r}, owner {machine.owner_file(path)}")

    review = machine.home / ".cache" / "merge-lane-review-worktrees" / "pr12-head"
    added = machine.worktree_add(review, author=SEAT)
    check("a merge-lane review checkout gets no owner file",
          added.returncode == 0 and machine.owner_file(review) is None,
          f"exit {added.returncode}, owner {machine.owner_file(review)}")

    # Made with GIT_AUTHOR_NAME unset, so it has no owner file, though a new worktree at this
    # path made by SEAT would get one; only the hook's all-zeros guard keeps the switch from
    # writing it.
    unowned = machine.agents / f"{SEAT}-worktrees" / "made-before-the-hook"
    machine.worktree_add(unowned)
    switched = machine.git({"GIT_AUTHOR_NAME": SEAT}, "checkout", "--quiet", "-b", "another",
                           cwd=unowned)
    check("a branch switch writes no owner file",
          switched.returncode == 0 and unowned.is_dir() and machine.owner_file(unowned) is None,
          f"exit {switched.returncode}, owner {machine.owner_file(unowned)}")

    subagent = machine.clone / ".claude" / "worktrees" / "agent-a45a189e6c5e2e31e"
    # bash, as macOS's /bin/sh is, execs the last command of `-c`, which would replace the fake
    # claude process before the hook looks for it; `exit $?` keeps the git command from being last.
    claude = root / "bin" / "claude"
    claude.parent.mkdir()
    claude.symlink_to(shutil.which("bash"))
    pid_file = root / "claude-pid"
    added = machine.worktree_add(subagent, author=SEAT,
                                 wrapper=[str(claude), "-c", f'echo $$ > {pid_file}; sh -c "$0"; exit $?'])
    owner = machine.owner_file(subagent)
    key_parts = (owner or {}).get("owner_key", "").split("-")
    claude_pid = pid_file.read_text().strip() if pid_file.is_file() else None
    check("a subagent's worktree names the agent-session of the nearest claude parent process",
          added.returncode == 0 and owner is not None
          and owner.get("owner_kind") == "agent-session" and owner.get("agent_seat") == SEAT
          and claude_pid in key_parts,
          f"exit {added.returncode}, stderr {added.stderr!r}, owner {owner}, claude pid {claude_pid}")

    for name in ("bash-guards-replay-grouped-refusals", "restored-agent-a45a189e6c5e2e31e",
                 "agent-a45a189e6c5e2e31"):
        by_hand = machine.clone / ".claude" / "worktrees" / name
        added = machine.worktree_add(by_hand, author=SEAT,
                                     wrapper=[str(claude), "-c", 'sh -c "$0"; exit $?'])
        check(f"a worktree named {name} inside .claude/worktrees/ names the agent-seat, "
              "not an agent-session",
              added.returncode == 0
              and machine.owner_file(by_hand) == {"owner_kind": "agent-seat", "agent_seat": SEAT},
              f"exit {added.returncode}, stderr {added.stderr!r}, owner {machine.owner_file(by_hand)}")

    orphan = machine.clone / ".claude" / "worktrees" / "agent-a0123456789abcdef"
    added = machine.worktree_add(orphan, author=SEAT, with_no_claude_parent=True)
    check("a subagent's worktree with no claude parent process gets no owner file, and says why",
          added.returncode == 0 and machine.owner_file(orphan) is None
          and "no process named claude" in added.stderr
          and "was not written" in added.stderr,
          f"exit {added.returncode}, stderr {added.stderr!r}, owner {machine.owner_file(orphan)}")

    bad = machine.agents / "bad seat-worktrees" / "topic"
    added = machine.worktree_add(bad, author="bad seat")
    check("an owner file that cannot be written leaves the checkout succeeding and says why",
          added.returncode == 0 and machine.owner_file(bad) is None
          and "was not written" in added.stderr and "WorktreeOwnerFileError" in added.stderr,
          f"exit {added.returncode}, stderr {added.stderr!r}")

    existing = subprocess.run([sys.executable, str(PROGRAM)], cwd=topic,
                              env={**machine.environment, "GIT_AUTHOR_NAME": SEAT},
                              capture_output=True, text=True, check=False)
    check("a worktree that already has an owner file keeps it, silently",
          existing.returncode == 0 and existing.stderr == ""
          and machine.owner_file(topic) == {"owner_kind": "agent-seat", "agent_seat": SEAT},
          f"exit {existing.returncode}, stderr {existing.stderr!r}")

    failing_scripts = root / "failing" / "scripts"
    shutil.copytree(HOOK_DIRECTORY, failing_scripts / "git-client-side-hooks")
    (failing_scripts / PROGRAM.name).write_text("import sys\nsys.exit(5)\n")
    failing = ScratchMachine(root / "two", failing_scripts / "git-client-side-hooks")
    path = failing.agents / f"{SEAT}-worktrees" / "topic"
    added = failing.worktree_add(path, author=SEAT)
    check("the hook exits 0 when its Python file fails, so git worktree add succeeds",
          added.returncode == 0 and path.is_dir(),
          f"exit {added.returncode}, stderr {added.stderr!r}")


if __name__ == "__main__":
    sys.exit(main())
