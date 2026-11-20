#!/usr/bin/env python3
"""Tests for scripts/branch-reverts-a-file-to-an-older-main-version-check.py.

Run: python3 scripts/branch-reverts-a-file-to-an-older-main-version-check-test.py
Prints one line per case and exits non-zero if any case fails.

Each case builds a throwaway repository under a temporary directory, with
global and system git config shut out, and runs the check in it as a seat
would.
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
    Path(__file__).resolve().with_name("git-redirecting-environment-removal-test-fixture.py"))
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()

CHECK = Path(__file__).resolve().parent / "branch-reverts-a-file-to-an-older-main-version-check.py"
DAY_SECONDS = 86400
# The check's own window, copied so a change to it fails a case.
WINDOW_DAYS = 30
NOW = 1_790_000_000

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


class Repository:
    """A repository with main, where every commit's date is set by the case."""

    def __init__(self, directory):
        self.directory = directory
        self.empty_config = directory.parent / (directory.name + "-gitconfig")
        self.empty_config.write_text("")
        self.date = NOW - 60 * DAY_SECONDS
        self.git("init", "--quiet", "--initial-branch=main", str(directory), cwd=directory.parent)
        self.git("config", "user.name", "Revert Check Test")
        self.git("config", "user.email", "revert-check-test@example.invalid")

    def environment(self):
        env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        env["GIT_CONFIG_GLOBAL"] = str(self.empty_config)
        env["GIT_CONFIG_NOSYSTEM"] = "1"
        env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = "@%d +0000" % self.date
        return env

    def git(self, *arguments, cwd=None):
        done = subprocess.run(["git", *arguments], cwd=str(cwd or self.directory),
                              env=self.environment(), capture_output=True, text=True,
                              timeout=60)
        if done.returncode != 0:
            raise RuntimeError("git %s failed: %s" % (" ".join(arguments), done.stderr))
        return done.stdout.strip()

    def commit(self, files, message, days_before_now):
        self.date = NOW - days_before_now * DAY_SECONDS
        for name, content in files.items():
            path = self.directory / name
            if content is None:
                self.git("rm", "--quiet", name)
            else:
                path.write_text(content)
                self.git("add", name)
        self.git("commit", "--quiet", "--allow-empty", "-m", message)
        return self.git("rev-parse", "HEAD")

    def run_check(self, *arguments, path=None):
        env = self.environment()
        if path is not None:
            env["PATH"] = path
        return subprocess.run([sys.executable, str(CHECK), *arguments],
                              cwd=str(self.directory), env=env, capture_output=True,
                              text=True, timeout=60)


def squashed_branch(repository, changed_days_before_now=1, path="shared file.txt"):
    """main changes a file after the branch's old base; the branch is squashed onto main
    with `git reset --soft`, and keeps the old version.

    Returns main's commit that the squash undoes."""
    repository.commit({path: "old\n"}, "Base", 50)
    repository.git("switch", "--quiet", "-c", "work")
    repository.commit({"work.txt": "work\n"}, "Work", changed_days_before_now)
    repository.git("switch", "--quiet", "main")
    replaced = repository.commit({path: "new\n"}, "Main changes the file",
                                 changed_days_before_now)
    repository.commit({"later.txt": "later\n"}, "Main moves on", 0)
    repository.git("switch", "--quiet", "work")
    repository.git("reset", "--soft", "main")
    repository.commit({}, "Squashed work", 0)
    return replaced


def main():
    scratch = Path(tempfile.mkdtemp(prefix="revert-check-test-")).resolve()
    try:
        run_cases(scratch)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    if failures:
        print(f"\n{len(failures)} case(s) failed")
        return 1
    print("\nall cases passed")
    return 0


def run_cases(scratch):
    repository = Repository(scratch / "squashed")
    replaced = squashed_branch(repository)
    done = repository.run_check("--base", "main")
    check("a branch squashed by soft reset onto a newer main exits 1",
          done.returncode == 1, done.stdout + done.stderr)
    check("its first line is the verdict",
          done.stdout.startswith("VERDICT: BRANCH-REVERTS-A-FILE-TO-AN-OLDER-MAIN-VERSION -- "),
          done.stdout)
    check("it names the file, which holds a space, and main's commit it undoes",
          "  shared file.txt: back to its version before %s (Main changes the file)"
          % replaced[:12] in done.stdout.splitlines(), done.stdout)
    check("it names only that file", "work.txt" not in done.stdout, done.stdout)
    check("it says how to restore main's version and how to undo on purpose",
          "`git checkout main -- <path>`" in done.stdout
          and "name the commit, by at least its first 12 characters" in done.stdout,
          done.stdout)

    repository.git("commit", "--quiet", "--allow-empty", "-m",
                   "Undo %s on purpose" % replaced[:12])
    done = repository.run_check("--base", "main")
    check("naming main's commit by its first 12 characters accepts the undo",
          done.returncode == 0 and done.stdout.startswith("VERDICT: CLEAN"),
          done.stdout + done.stderr)

    repository = Repository(scratch / "eleven")
    replaced = squashed_branch(repository)
    repository.git("commit", "--quiet", "--allow-empty", "-m", "Undo %s" % replaced[:11])
    done = repository.run_check("--base", "main")
    check("naming it by 11 characters does not", done.returncode == 1, done.stdout)

    repository = Repository(scratch / "twice")
    repository.commit({"a.txt": "old\n"}, "Base", 10)
    repository.git("switch", "--quiet", "-c", "work")
    repository.commit({"work.txt": "work\n"}, "Work", 9)
    repository.git("switch", "--quiet", "main")
    repository.commit({"a.txt": "new\n"}, "Main changes a", 8)
    repository.commit({"a.txt": "old\n"}, "Main changes a back", 7)
    newest = repository.commit({"a.txt": "new\n"}, "Main changes a again", 6)
    repository.git("switch", "--quiet", "work")
    repository.git("reset", "--soft", "main")
    repository.commit({}, "Squashed work", 0)
    done = repository.run_check("--base", "main")
    lines = [line for line in done.stdout.splitlines() if line.startswith("  a.txt: ")]
    check("a file set back to a version main replaced twice is named once, with the newer commit",
          lines == ["  a.txt: back to its version before %s (Main changes a again)" % newest[:12]],
          done.stdout)

    repository = Repository(scratch / "twice-named")
    repository.commit({"a.txt": "old\n"}, "Base", 10)
    repository.commit({"a.txt": "new\n"}, "Main changes a", 8)
    repository.commit({"a.txt": "old\n"}, "Main changes a back", 7)
    newest = repository.commit({"a.txt": "new\n"}, "Main changes a again", 6)
    repository.git("switch", "--quiet", "-c", "work")
    repository.git("revert", "--no-edit", newest)
    done = repository.run_check("--base", "main")
    check("a named undo of main's newest change is clean, though an older change "
          "replaced the same version", done.returncode == 0, done.stdout + done.stderr)

    repository = Repository(scratch / "merge-revert")
    repository.commit({"a.txt": "old\n"}, "Base", 10)
    repository.git("switch", "--quiet", "-c", "topic")
    repository.commit({"a.txt": "new\n"}, "Topic changes a", 6)
    repository.git("switch", "--quiet", "main")
    repository.commit({"other.txt": "other\n"}, "Main moves on", 5)
    repository.git("merge", "--quiet", "--no-ff", "-m", "Merge pull request from topic",
                   "topic")
    merge = repository.git("rev-parse", "HEAD")
    repository.git("switch", "--quiet", "-c", "work")
    repository.git("revert", "--no-edit", "-m", "1", merge)
    done = repository.run_check("--base", "main")
    check("a branch made with `git revert -m 1` of a merge on main is clean",
          done.returncode == 0, done.stdout + done.stderr)
    repository.git("switch", "--quiet", "-c", "squashed", "main~2")
    repository.commit({"work.txt": "work\n"}, "Work", 0)
    repository.git("reset", "--soft", "main")
    repository.commit({}, "Squashed work", 0)
    done = repository.run_check("--base", "main")
    check("a squash that undoes a merged change names main's merge commit, as "
          "`git revert -m 1` would",
          done.returncode == 1
          and "  a.txt: back to its version before %s (Merge pull request from topic)"
          % merge[:12] in done.stdout.splitlines(), done.stdout + done.stderr)

    repository = Repository(scratch / "mode-only")
    repository.commit({"tool.sh": "old\n"}, "Base", 10)
    repository.commit({"tool.sh": "new\n"}, "Main changes the tool", 8)
    repository.commit({"tool.sh": "old\n"}, "Main changes the tool back", 7)
    repository.git("switch", "--quiet", "-c", "work")
    repository.git("update-index", "--chmod=+x", "tool.sh")
    repository.commit({}, "Work makes the tool executable", 0)
    done = repository.run_check("--base", "main")
    check("a branch that only changes a file's mode is clean",
          done.returncode == 0, done.stdout + done.stderr)

    repository = Repository(scratch / "git-revert")
    repository.commit({"a.txt": "old\n"}, "Base", 10)
    replaced = repository.commit({"a.txt": "new\n"}, "Main changes a", 5)
    repository.git("switch", "--quiet", "-c", "work")
    repository.git("revert", "--no-edit", replaced)
    done = repository.run_check("--base", "main")
    check("a branch made with `git revert` of main's commit is clean",
          done.returncode == 0, done.stdout + done.stderr)

    repository = Repository(scratch / "clean")
    repository.commit({"a.txt": "old\n"}, "Base", 10)
    repository.commit({"a.txt": "new\n"}, "Main changes a", 5)
    repository.git("switch", "--quiet", "-c", "work")
    repository.commit({"a.txt": "newer\n"}, "Work on a", 0)
    done = repository.run_check("--base", "main")
    check("a branch that changes a file to a version main never had is clean",
          done.returncode == 0 and done.stdout.startswith("VERDICT: CLEAN -- ")
          and done.stderr == "", done.stdout + done.stderr)

    repository = Repository(scratch / "nothing")
    repository.commit({"a.txt": "a\n"}, "Base", 10)
    repository.git("switch", "--quiet", "-c", "work")
    done = repository.run_check("--base", "main")
    check("a branch with no changes is clean", done.returncode == 0, done.stdout + done.stderr)

    repository = Repository(scratch / "deletion")
    repository.commit({"a.txt": "a\n"}, "Base", 10)
    repository.commit({"added.txt": "added\n"}, "Main adds a file", 5)
    repository.git("switch", "--quiet", "-c", "work")
    repository.commit({"added.txt": None}, "Work deletes it", 0)
    done = repository.run_check("--base", "main")
    check("a branch that deletes a file main added recently is clean",
          done.returncode == 0, done.stdout + done.stderr)

    repository = Repository(scratch / "outside-window")
    squashed_branch(repository, changed_days_before_now=WINDOW_DAYS + 2)
    done = repository.run_check("--base", "main")
    check("an undo of a change older than the window is not reported",
          done.returncode == 0, done.stdout + done.stderr)

    repository = Repository(scratch / "inside-window")
    squashed_branch(repository, changed_days_before_now=WINDOW_DAYS - 2)
    done = repository.run_check("--base", "main")
    check("an undo of a change just inside the window is reported",
          done.returncode == 1, done.stdout + done.stderr)

    repository = Repository(scratch / "bad-ref")
    repository.commit({"a.txt": "a\n"}, "Base", 10)
    done = repository.run_check("--head", "no-such-branch", "--base", "main")
    check("a head that is not a commit exits 2 with git's error and no verdict",
          done.returncode == 2 and done.stdout == ""
          and "could not tell whether this branch sets a file back to a version main has "
          "replaced, because `git rev-parse --verify no-such-branch^{commit}` exited 128"
          in done.stderr
          and done.stderr.rstrip().endswith(
              "fix what git reports, then run this check again from your worktree: python3 "
              "scripts/branch-reverts-a-file-to-an-older-main-version-check.py "
              "--head no-such-branch --base main"),
          done.stdout + done.stderr)

    done = repository.run_check("--base", "main", path=str(scratch / "no-git-here"))
    check("when git cannot be started, it exits 2 and says so",
          done.returncode == 2 and done.stdout == ""
          and "could not be started" in done.stderr, done.stdout + done.stderr)

    repository = Repository(scratch / "subject-fails")
    squashed_branch(repository)
    wrapper_directory = scratch / "git-failing-on-subject"
    wrapper_directory.mkdir()
    wrapper = wrapper_directory / "git"
    wrapper.write_text("#!/bin/sh\n"
                       "for argument; do\n"
                       "  [ \"$argument\" = \"--format=%%s\" ] && "
                       "{ echo 'fatal: subject lookup failed' >&2; exit 128; }\n"
                       "done\n"
                       "exec %s \"$@\"\n" % shutil.which("git"))
    wrapper.chmod(0o755)
    done = repository.run_check("--base", "main",
                                path="%s:%s" % (wrapper_directory, os.environ["PATH"]))
    check("when git fails while the report reads a commit's subject, it exits 2 with "
          "git's error and no verdict",
          done.returncode == 2 and done.stdout == ""
          and "because `git log -1 --format=%s" in done.stderr
          and "subject lookup failed" in done.stderr, done.stdout + done.stderr)


if __name__ == "__main__":
    sys.exit(main())
