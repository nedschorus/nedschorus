#!/usr/bin/env python3
"""Tests for merge-lane-pull-request-head-and-merged-worktrees-rebuild.py.

Runs the program against real git in a scratch directory: a bare origin
holding main and a pull request's head at refs/pull/7/head, as GitHub keeps
it, and a clone of that origin as the checkout git runs in. The program runs
with GIT_DIR pointing at a directory that does not exist, so a case passes
only if the program drops the variables that redirect git, and with no
identity in its environment or a global git config, so the merge commit's
author comes from the program alone.

Run: python3 scripts/merge-lane-pull-request-head-and-merged-worktrees-rebuild-test.py
"""

import importlib.util
import os
import shutil
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

PROGRAM = Path(__file__).with_name("merge-lane-pull-request-head-and-merged-worktrees-rebuild.py")
GIT_ENVIRONMENT = {
    **{key: value for key, value in os.environ.items() if not key.startswith("GIT_")},
    "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@example.invalid",
    "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@example.invalid",
    "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
}

failures = []


def check(name, condition, detail=""):
    print(("PASS  " if condition else "FAIL  ") + name)
    if not condition:
        failures.append(name)
        if detail:
            print("      " + detail.replace("\n", "\n      "))


def git(directory, *arguments):
    return subprocess.run(["git", "-C", str(directory), *arguments], capture_output=True,
                          text=True, check=True, env=GIT_ENVIRONMENT).stdout.strip()


def build_repositories(scratch):
    """Return (checkout, main commit, head commit)."""
    origin = scratch / "origin.git"
    author = scratch / "author"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True,
                   env=GIT_ENVIRONMENT)
    subprocess.run(["git", "init", "-q", "-b", "main", str(author)], check=True,
                   env=GIT_ENVIRONMENT)
    (author / "on-main.txt").write_text("main\n")
    git(author, "add", ".")
    git(author, "commit", "-q", "-m", "main")
    main_commit = git(author, "rev-parse", "HEAD")
    git(author, "checkout", "-q", "-b", "topic")
    (author / "on-topic.txt").write_text("topic\n")
    git(author, "add", ".")
    git(author, "commit", "-q", "-m", "topic")
    head_commit = git(author, "rev-parse", "HEAD")
    git(author, "push", "-q", str(origin), "main:refs/heads/main",
        "topic:refs/pull/7/head")
    checkout = scratch / "checkout"
    subprocess.run(["git", "clone", "-q", str(origin), str(checkout)], check=True,
                   env=GIT_ENVIRONMENT)
    return checkout, main_commit, head_commit


def run_program(helpers, checkout, *arguments, cwd=None):
    return subprocess.run(
        [sys.executable, str(PROGRAM), *arguments, "--merge-lane-worktrees-and-outputs-directory", str(helpers),
         "--review-tools-worktree-at-main", str(checkout)],
        capture_output=True, text=True, cwd=cwd,
        env={**{key: value for key, value in GIT_ENVIRONMENT.items()
                if not key.startswith(("GIT_AUTHOR_", "GIT_COMMITTER_"))},
             "GIT_DIR": str(helpers / "no-such-git-directory")})


def main():
    scratch = Path(tempfile.mkdtemp(prefix="merge-lane-worktrees-rebuild-test-")).resolve()
    try:
        checkout, main_commit, head_commit = build_repositories(scratch)
        helpers = scratch / "merge-helpers"
        head_worktree = helpers / "wt" / "pr7-head"
        merged_worktree = helpers / "wt" / "pr7-merged"

        completed = run_program(helpers, checkout, "7", head_commit, main_commit)
        detail = f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}"
        check("both worktrees are made, exit 0", completed.returncode == 0
              and head_worktree.is_dir() and merged_worktree.is_dir(), detail)
        if completed.returncode == 0:
            check("wt/pr<n>-head is at the head commit",
                  git(head_worktree, "rev-parse", "HEAD") == head_commit, detail)
            check("wt/pr<n>-head is detached",
                  git(head_worktree, "rev-parse", "--abbrev-ref", "HEAD") == "HEAD", detail)
            parents = git(merged_worktree, "rev-list", "--parents", "-n", "1", "HEAD").split()[1:]
            check("wt/pr<n>-merged is a merge commit of main and the head commit",
                  parents == [main_commit, head_commit], repr(parents))
            check("the merge commit is made as merge-lane-2",
                  git(merged_worktree, "log", "-1", "--format=%an") == "merge-lane-2", detail)
            merged_tree = git(merged_worktree, "rev-parse", "HEAD^{tree}")
            check("the output names the head, the merge commit, its tree and main",
                  completed.stdout.strip() == (
                      f"PR 7: head {head_commit[:7]}, merged "
                      f"{git(merged_worktree, 'rev-parse', '--short', 'HEAD')} tree "
                      f"{merged_tree} on main {main_commit[:8]}"), completed.stdout)

            (head_worktree / "left-behind.txt").write_text("a change in the old worktree\n")
            completed = run_program(helpers, checkout, "7", head_commit, main_commit)
            check("running again replaces both worktrees, dropping changes in them",
                  completed.returncode == 0
                  and not (head_worktree / "left-behind.txt").exists()
                  and git(head_worktree, "rev-parse", "HEAD") == head_commit,
                  f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}")

        relative_helpers = scratch / "relative-helpers"
        completed = run_program(Path("relative-helpers"), Path("checkout"), "7", head_commit,
                                main_commit, cwd=scratch)
        check("relative directory options make the worktrees under the caller's directory, "
              "not under the checkout git runs in",
              completed.returncode == 0
              and (relative_helpers / "wt" / "pr7-head").is_dir()
              and (relative_helpers / "wt" / "pr7-merged").is_dir()
              and not (checkout / "relative-helpers").exists(),
              f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}")

        completed = run_program(helpers, checkout, "7", "0" * 40, main_commit)
        check("a head commit git cannot find exits 1 and names the failed step",
              completed.returncode == 1 and "worktrees not rebuilt" in completed.stdout
              and "worktree add" in completed.stdout,
              f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}")

        completed = run_program(helpers, checkout, "8", head_commit, main_commit)
        check("a pull request origin does not have exits 1 at the fetch",
              completed.returncode == 1 and "git fetch" in completed.stdout,
              f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}")
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    if failures:
        print(f"\n{len(failures)} case(s) failed")
        return 1
    print("\nall cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
