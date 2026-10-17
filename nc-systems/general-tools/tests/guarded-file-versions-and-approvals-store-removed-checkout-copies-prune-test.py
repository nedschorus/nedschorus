#!/usr/bin/env python3
"""Tests for nc-systems/general-tools/guarded-file-versions-and-approvals-store-removed-checkout-copies-prune.py.

Each case builds a scratch store and scratch checkouts in a temporary directory, never the real
store, and runs the program on them as ned-box.

Run: python3 nc-systems/general-tools/tests/guarded-file-versions-and-approvals-store-removed-checkout-copies-prune-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import hashlib
import importlib.util
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]

_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    REPOSITORY_ROOT / "scripts" / "git-redirecting-environment-removal-test-fixture.py")
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()

PROGRAM = (Path(__file__).resolve().parents[1]
           / "guarded-file-versions-and-approvals-store-removed-checkout-copies-prune.py")
HOOK_PATH = (REPOSITORY_ROOT / ".claude" / "hooks"
             / "guarded-file-unapproved-change-afterward-backup-and-ask-hook.py")
_specification = importlib.util.spec_from_file_location("guarded_file_hook", HOOK_PATH)
hook = importlib.util.module_from_spec(_specification)
_specification.loader.exec_module(hook)

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def blob(text):
    data = text.encode()
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def add_version(store, path, text, approved):
    """Put one copy of path into the scratch store, as the hook does, with its seen line and,
    when approved, its approved line."""
    directory = store / path.lstrip("/")
    directory.mkdir(parents=True, exist_ok=True)
    key = blob(text)
    (directory / key).write_text(text)
    with open(directory / hook.LOG_FILE_NAME, "ab") as log:
        log.write(hook.checked_line("\t".join(["seen", "1", "session", "owner", key, key, ""])))
    if approved:
        with open(directory / hook.APPROVED_FILE_NAME, "ab") as approved_file:
            approved_file.write(hook.checked_line(key))
    return directory / key


def run(store, *arguments):
    environment = dict(os.environ, GUARDED_FILE_VERSIONS_MACHINE="ned-box",
                       GUARDED_FILE_VERSIONS_STORE_DIRECTORY=str(store))
    return subprocess.run([sys.executable, str(PROGRAM), *arguments], capture_output=True,
                          text=True, env=environment, timeout=120)


def git(*arguments):
    subprocess.run(["git", *arguments], check=True, capture_output=True)


def scratch(root):
    """A store and the checkouts its paths name: (store, agents directory, live repository)."""
    store = root / "store"
    store.mkdir()
    agents = root / "agents"
    (agents / "live").mkdir(parents=True)
    (agents / "live" / "CLAUDE.md").write_text("live\n")
    repository = root / "repository"
    repository.mkdir()
    git("init", "-q", str(repository))
    (repository / ".gitignore").write_text("worktrees/\n")
    (repository / "docs").mkdir()
    return store, agents, repository


def test_removed_checkouts_pruned_and_others_kept():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory).resolve()
        store, agents, repository = scratch(root)
        removed = add_version(store, f"{agents}/removed/CLAUDE.md", "one\n", approved=True)
        live = add_version(store, f"{agents}/live/CLAUDE.md", "live\n", approved=True)
        unapproved_old = add_version(store, f"{agents}/declined/CLAUDE.md", "a\n", approved=True)
        unapproved = add_version(store, f"{agents}/declined/CLAUDE.md", "b\n", approved=False)
        nested = add_version(store, f"{repository}/worktrees/gone/CLAUDE.md", "n\n", approved=True)
        branch_deleted_directory = add_version(store, f"{repository}/docs/gone/a.md", "d\n",
                                               approved=True)
        branch_deleted_file = add_version(store, f"{repository}/docs/b.md", "f\n", approved=True)
        dry = run(store, "--dry-run")
        check("--dry-run exits 0", dry.returncode == 0, dry.stderr)
        check("--dry-run deletes nothing", removed.exists() and nested.exists(), dry.stdout)
        check("--dry-run names the removed checkout", f"would prune {agents}/removed:" in dry.stdout,
              dry.stdout)
        result = run(store)
        check("a run exits 0", result.returncode == 0, result.stderr)
        check("a removed checkout's approved copy is deleted", not removed.exists())
        check("its log and approved set stay", (removed.parent / hook.LOG_FILE_NAME).exists())
        check("an existing checkout's copy is kept", live.exists())
        check("a removed checkout's version never approved is kept", unapproved.exists())
        check("so is the approved copy beside it", unapproved_old.exists())
        check("a gone checkout under a directory git ignores is pruned", not nested.exists())
        check("a directory deleted on a branch keeps its copies", branch_deleted_directory.exists())
        check("a file deleted in an existing directory keeps its copies",
              branch_deleted_file.exists())
        check("the summary counts two checkouts and two kept copies",
              "copies of 2 removed checkouts" in result.stdout and "kept 2 copies" in result.stdout,
              result.stdout)


def test_unreadable_store_fails():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory).resolve()
        result = run(root / "absent")
        check("a store that does not exist exits 1", result.returncode == 1, result.stdout)
        check("and says the store could not be opened", "could not be opened" in result.stderr,
              result.stderr)
        store, agents, _ = scratch(root)
        copy = add_version(store, f"{agents}/removed/CLAUDE.md", "one\n", approved=True)
        unreadable = store / str(agents).lstrip("/")
        unreadable.chmod(0)
        try:
            result = run(store)
        finally:
            unreadable.chmod(0o700)
        check("a store directory that cannot be read exits 1", result.returncode == 1,
              result.stdout)
        check("and names the directory", str(unreadable) in result.stderr, result.stderr)
        (copy.parent / hook.LOG_FILE_NAME).chmod(0)
        try:
            result = run(store)
        finally:
            (copy.parent / hook.LOG_FILE_NAME).chmod(0o600)
        check("a log that cannot be read exits 1", result.returncode == 1, result.stdout)
        check("and keeps the copy", copy.exists())


def test_failing_delete_fails():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory).resolve()
        store, agents, _ = scratch(root)
        stuck = add_version(store, f"{agents}/removed-a/CLAUDE.md", "one\n", approved=True)
        other = add_version(store, f"{agents}/removed-b/CLAUDE.md", "two\n", approved=True)
        stuck.parent.chmod(0o500)
        try:
            result = run(store)
        finally:
            stuck.parent.chmod(0o700)
        check("a delete that fails exits 1", result.returncode == 1, result.stdout)
        check("and names the copy", f"{stuck} could not be deleted" in result.stderr,
              result.stderr)
        check("the other checkout is still pruned", not other.exists())


def test_git_failure_fails():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory).resolve()
        store = root / "store"
        store.mkdir()
        broken = root / "broken"
        broken.mkdir()
        (broken / ".git").write_text(f"gitdir: {root}/no-such-git-directory\n")
        copy = add_version(store, f"{broken}/worktree/CLAUDE.md", "one\n", approved=True)
        result = run(store)
        check("git that cannot answer exits 1", result.returncode == 1, result.stdout)
        check("and says git failed", "check-ignore" in result.stderr, result.stderr)
        check("and deletes nothing", copy.exists())


if __name__ == "__main__":
    test_removed_checkouts_pruned_and_others_kept()
    test_unreadable_store_fails()
    test_failing_delete_fails()
    test_git_failure_fails()
    if failures:
        print(f"{len(failures)} case(s) failed")
        sys.exit(1)
    print("all cases passed")
