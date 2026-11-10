#!/usr/bin/env python3
"""Tests for nc-systems/general-tools/edited-file-path-within-checkout-root-and-git-check-ignore-common.py.

Runs real git in a throwaway repository holding a committed file, an untracked
file and an ignored file, and in a checkout whose .git file names a git
directory that does not exist, where git check-ignore exits 128.

Run: python3 nc-systems/general-tools/tests/edited-file-path-within-checkout-root-and-git-check-ignore-common-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import importlib.util
import os
import shutil
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

_spec = importlib.util.spec_from_file_location(
    "edited_file_path_within_checkout_root_and_git_check_ignore_common",
    Path(__file__).resolve().parents[1] / "edited-file-path-within-checkout-root-and-git-check-ignore-common.py")
checks = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(checks)

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def git(directory, *arguments):
    subprocess.run(["git", "-C", str(directory), *arguments], check=True, capture_output=True)


def raised(function, *arguments):
    """Return the GitCommandFailed message function raised, None when it returned,
    or "other exception: ..." when it raised anything else, which no case accepts."""
    try:
        function(*arguments)
    except checks.GitCommandFailed as error:
        return str(error)
    except Exception as error:
        return f"other exception: {type(error).__name__}: {error}"
    return None


with tempfile.TemporaryDirectory(prefix="edited-file-path-within-checkout-root-and-git-check-ignore-") as scratch:
    scratch = Path(scratch).resolve()
    checkout = scratch / "checkout"
    (checkout / "docs").mkdir(parents=True)
    git(checkout, "init", "-q")
    git(checkout, "config", "user.name", "test")
    git(checkout, "config", "user.email", "test@example.invalid")
    (checkout / ".gitignore").write_text("ignored/\n", encoding="utf-8")
    (checkout / "docs" / "committed.md").write_text("first line   \nsecond line\n", encoding="utf-8")
    git(checkout, "add", ".gitignore", "docs/committed.md")
    git(checkout, "commit", "-q", "-m", "fixture")
    (checkout / "docs" / "untracked.md").write_text("new\n", encoding="utf-8")
    (checkout / "ignored").mkdir()
    (checkout / "ignored" / "scratch.md").write_text("scratch\n", encoding="utf-8")

    # --- enclosing_checkout_root and checkout_relative_path -------------------
    check("the checkout root is found from a directory inside the checkout",
          checks.enclosing_checkout_root(checkout / "docs") == checkout)
    check("no checkout root is found outside every checkout",
          checks.enclosing_checkout_root(scratch) is None)
    check("a file in the checkout gets its checkout-relative path",
          checks.checkout_relative_path(str(checkout / "docs" / "committed.md"), checkout / "docs")
          == (checkout, "docs/committed.md"))
    check("a file outside the checkout gets None",
          checks.checkout_relative_path(str(scratch / "elsewhere.md"), checkout) is None)

    # --- git_would_track ---------------------------------------------------
    check("git would track a committed file", checks.git_would_track(checkout, "docs/committed.md") is True)
    check("git would track an untracked file that is not ignored",
          checks.git_would_track(checkout, "docs/untracked.md") is True)
    check("git would not track an ignored file", checks.git_would_track(checkout, "ignored/scratch.md") is False)

    broken_checkout = scratch / "checkout-whose-git-directory-is-gone"
    broken_checkout.mkdir()
    (broken_checkout / ".git").write_text("gitdir: " + str(scratch / "no-such-git-directory") + "\n",
                                          encoding="utf-8")
    message = raised(checks.git_would_track, broken_checkout, "notes.md")
    check("a git check-ignore that exits 128 raises GitCommandFailed, not 'not tracked'",
          message is not None and "git check-ignore -q -- notes.md in" in message
          and "failed (exit 128" in message, message)

    original_path = os.environ.get("PATH", "")
    os.environ["PATH"] = str(scratch / "empty-path-directory")
    try:
        message = raised(checks.git_would_track, checkout, "docs/committed.md")
    finally:
        os.environ["PATH"] = original_path
    check("a git that cannot be started raises GitCommandFailed",
          message is not None and "git check-ignore -q -- docs/committed.md in" in message
          and "could not start git" in message, message)

    # --- file_lines_at_head_unless_git_ignores_file -----------------------
    check("a committed file's lines at HEAD come back with trailing whitespace removed",
          checks.file_lines_at_head_unless_git_ignores_file(checkout, "docs/committed.md")
          == {"first line", "second line", ""})
    check("a file HEAD lacks that git would track comes back as an empty set",
          checks.file_lines_at_head_unless_git_ignores_file(checkout, "docs/untracked.md") == set())
    check("an ignored file comes back as None",
          checks.file_lines_at_head_unless_git_ignores_file(checkout, "ignored/scratch.md") is None)
    message = raised(checks.file_lines_at_head_unless_git_ignores_file, broken_checkout, "notes.md")
    check("a git that cannot read HEAD raises GitCommandFailed, not 'new at HEAD'",
          message is not None and "git show HEAD:notes.md in" in message
          and "failed (exit 128" in message, message)

    no_commit_checkout = scratch / "checkout-with-no-commit"
    no_commit_checkout.mkdir()
    git(no_commit_checkout, "init", "-q")
    (no_commit_checkout / "first.md").write_text("first\n", encoding="utf-8")
    check("a file in a checkout with no commit yet comes back as an empty set",
          checks.file_lines_at_head_unless_git_ignores_file(no_commit_checkout, "first.md") == set())

    def git_failing_when(name, condition):
        """A directory holding a `git` that, when the shell test condition holds,
        prints "fatal: shimmed <name>" and exits 128, and otherwise runs the real git."""
        directory = scratch / name
        directory.mkdir()
        (directory / "git").write_text(
            "#!/bin/sh\n"
            f"if {condition}; then\n"
            f'  printf "fatal: shimmed {name}\\n" >&2\n'
            "  exit 128\n"
            "fi\n"
            f'exec "{shutil.which("git")}" "$@"\n', encoding="utf-8")
        (directory / "git").chmod(0o755)
        return directory

    for case_name, shim_name, condition in (
            ("a git show that fails on a file HEAD has", "show-failing-git", '[ "$1" = "show" ]'),
            ("a git show and git ls-tree that both fail", "show-and-ls-tree-failing-git",
             '[ "$1" = "show" ] || [ "$1" = "ls-tree" ]')):
        os.environ["PATH"] = f"{git_failing_when(shim_name, condition)}{os.pathsep}{original_path}"
        try:
            message = raised(checks.file_lines_at_head_unless_git_ignores_file, checkout,
                             "docs/committed.md")
        finally:
            os.environ["PATH"] = original_path
        check(f"{case_name} raises GitCommandFailed with git show's error, not 'new at HEAD'",
              message is not None and "git show HEAD:docs/committed.md in" in message
              and f"exit 128: fatal: shimmed {shim_name}" in message, message)

    os.environ["PATH"] = str(scratch / "empty-path-directory")
    try:
        message = raised(checks.file_lines_at_head_unless_git_ignores_file, checkout, "docs/committed.md")
    finally:
        os.environ["PATH"] = original_path
    check("a git show that cannot start raises GitCommandFailed",
          message is not None and "git show HEAD:docs/committed.md in" in message
          and "could not start git" in message, message)

    # A git that never answers: a stand-in that sleeps past a shortened timeout.
    slow_git_directory = scratch / "slow-git"
    slow_git_directory.mkdir()
    slow_git = slow_git_directory / "git"
    slow_git.write_text("#!/bin/sh\nexec sleep 30\n", encoding="utf-8")
    slow_git.chmod(0o755)
    original_timeout = checks.GIT_TIMEOUT_SECONDS
    checks.GIT_TIMEOUT_SECONDS = 0.5
    os.environ["PATH"] = f"{slow_git_directory}{os.pathsep}{original_path}"
    try:
        message = raised(checks.file_lines_at_head_unless_git_ignores_file, checkout, "docs/committed.md")
    finally:
        os.environ["PATH"] = original_path
        checks.GIT_TIMEOUT_SECONDS = original_timeout
    check("a git show that times out raises GitCommandFailed",
          message is not None and "git show HEAD:docs/committed.md in" in message
          and "did not finish within" in message, message)

print()
if failures:
    print(f"{len(failures)} case(s) failed")
    sys.exit(1)
print("all cases passed")
