#!/usr/bin/env python3
"""Tests for run-all-test-suites.py's --save-recorded-inputs-to-directory and
adopt_passing_recordings_that_match_the_checkout(), the way merge-lane-2 uses them.

Each case builds a scratch repository whose one suite reads two files, and runs the
real runner as a subprocess on worktrees of it, the way merge-lane-2's head test runs
and its merge program do: selecting by one store, with each pull request's run saving
either into that store, as before, or into a directory of its own whose recordings
the merge adopts. The case that reproduces the stale recording: pull request X changes
one file the suite reads and merges; pull request Z, built on main before X merged,
changes the other file and is then tested, and never merges; then pull request A,
on main after X, is tested. When every run saves into the store, Z's run replaces X's
recording, and A's run selects the suite because its recording read another copy of a
file than the checkout holds. When runs save apart and the merge adopts, A's run leaves
the suite out.

Run: python3 scripts/run-all-test-suites-recordings-saved-apart-then-adopted-when-they-match-the-merge-commit-test.py   (exit 0 = all passed)
"""

import importlib.util
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent
PROGRAM = SCRIPTS_DIR / "run-all-test-suites.py"
SUITE = "reads-two-files-test.py"
SUITE_BODY = ("import pathlib\n"
              "for name in ('first.txt', 'second.txt'):\n"
              "    pathlib.Path(name).read_text()\n")

_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    SCRIPTS_DIR / "git-redirecting-environment-removal-test-fixture.py")
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()

# As inside a full run: the fixture suite runs unconfined, without an nc-test-sandbox, whose
# own tests are elsewhere.
os.environ["RUN_ALL_TEST_SUITES_INSIDE_SIGNAL_SANDBOX"] = "1"

_spec = importlib.util.spec_from_file_location("run_all_test_suites", PROGRAM)
runner = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(runner)

failures = []
scratch_directories = []


def check(name, condition, detail=""):
    print(("PASS  " if condition else "FAIL  ") + name)
    if not condition:
        failures.append(name)
        if detail:
            print("      " + str(detail).replace("\n", "\n      "))


def git(repo, *arguments):
    return subprocess.run(["git", "-C", str(repo), "-c", "core.hooksPath=/dev/null",
                           "-c", "user.name=fixture", "-c", "user.email=fixture@invalid",
                           "-c", "commit.gpgsign=false", *arguments],
                          capture_output=True, text=True, check=True).stdout.strip()


def commit(repo, files, message):
    for relative, body in files.items():
        (repo / relative).write_text(body)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message)
    return git(repo, "rev-parse", "HEAD")


class Scratch:
    """A repository with main at M0, and worktrees made from it as each case needs."""

    def __init__(self):
        self.root = pathlib.Path(tempfile.mkdtemp(prefix="recordings-adopted-test-"))
        scratch_directories.append(self.root)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q", "-b", "main")
        self.m0 = commit(self.repo, {SUITE: SUITE_BODY, "first.txt": "0\n",
                                     "second.txt": "0\n", "unread.txt": "0\n"}, "M0")
        self.runs = 0

    def worktree(self, name, base, files=None):
        path = self.root / name
        git(self.repo, "worktree", "add", "-q", "--detach", str(path), base)
        if files:
            commit(path, files, name)
        return path, git(path, "rev-parse", "HEAD")

    def run(self, checkout, since=None, store="store", save_to=None):
        self.runs += 1
        command = [sys.executable, str(PROGRAM), "--checkout", str(checkout),
                   "--log-dir", str(self.root / f"logs-{self.runs}"),
                   "--lock-file", str(self.root / "run.lock"),
                   "--recorded-inputs-directory", str(self.root / store),
                   "--suite-files-only-strace-saw-lists-directory", str(self.root / "strace-lists")]
        if since is not None:
            command += ["--only-suites-whose-recorded-inputs-changed-since", since]
        if save_to is not None:
            command += ["--save-recorded-inputs-to-directory", str(self.root / save_to)]
        return subprocess.run(command, capture_output=True, text=True, check=False,
                              stdin=subprocess.DEVNULL)

    def recording(self, store):
        found = list((self.root / store).glob(f"*/{SUITE}.json"))
        return json.loads(found[0].read_text()) if found else None


def selection_line(result):
    return next((line for line in result.stdout.splitlines()
                 if line.startswith((f"SELECTED {SUITE}:", f"NOT SELECTED {SUITE}:"))),
                result.stdout + result.stderr)


def x_merges_then_z_and_a_are_tested(save_apart):
    """Return (A's run, the scratch) after the sequence the docstring describes."""
    scratch = Scratch()
    main_checkout, _ = scratch.worktree("main-at-m0", scratch.m0)
    scratch.run(main_checkout)
    x_checkout, _ = scratch.worktree("pr-x", scratch.m0, {"first.txt": "x\n"})
    scratch.run(x_checkout, since=scratch.m0, save_to="pr-x-recordings" if save_apart else None)
    git(scratch.repo, "merge", "-q", "--ff-only", git(x_checkout, "rev-parse", "HEAD"))
    m1 = git(scratch.repo, "rev-parse", "HEAD")
    merge_commit_checkout, _ = scratch.worktree("merge-commit", m1)
    adopted = (runner.adopt_passing_recordings_that_match_the_checkout(
        merge_commit_checkout, scratch.root / "store", [scratch.root / "pr-x-recordings"])
        if save_apart else None)
    z_checkout, _ = scratch.worktree("pr-z", scratch.m0, {"second.txt": "z\n"})
    scratch.run(z_checkout, since=scratch.m0, save_to="pr-z-recordings" if save_apart else None)
    a_checkout, _ = scratch.worktree("pr-a", m1, {"unread.txt": "a\n"})
    return scratch.run(a_checkout, since=m1), scratch, adopted


def main():
    result, scratch, _ = x_merges_then_z_and_a_are_tested(save_apart=False)
    check("reproduced: when every head test run saves into the store, a pull request built "
          "on the older main replaces the merged pull request's recording, and the next run "
          "on main selects the suite because its recording read another copy of a file",
          selection_line(result) == (
              f"SELECTED {SUITE}: its recording read another copy of first.txt and 1 more than the "
              f"checkout holds, so what it reads here is unknown"), selection_line(result))

    result, scratch, adopted = x_merges_then_z_and_a_are_tested(save_apart=True)
    check("when head test runs save apart and the merge adopts the recordings that match "
          "it, the next run on main leaves the suite out",
          selection_line(result).startswith(f"NOT SELECTED {SUITE}: none of the")
          and result.returncode == 0, selection_line(result))
    check("the merge adopts the merged pull request's recording, from its own directory",
          adopted == [(SUITE, runner.recordings_directory_for(
              scratch.root / "pr-x-recordings", scratch.repo))], adopted)
    z_recording = scratch.recording("pr-z-recordings")
    check("the unmerged pull request's run saved its recording in its own directory, not "
          "in the store",
          z_recording is not None
          and z_recording["reads"]["second.txt"] != scratch.recording("store")["reads"][
              "second.txt"], (z_recording, scratch.recording("store")))

    scratch = Scratch()
    main_checkout, _ = scratch.worktree("main-at-m0", scratch.m0)
    scratch.run(main_checkout)
    in_store = scratch.recording("store")
    z_checkout, _ = scratch.worktree("pr-z", scratch.m0, {"second.txt": "z\n"})
    scratch.run(z_checkout, since=scratch.m0, save_to="pr-z-recordings")
    adopted = runner.adopt_passing_recordings_that_match_the_checkout(
        main_checkout, scratch.root / "store", [scratch.root / "pr-z-recordings"])
    check("a recording made on a tree whose files the checkout does not hold is not adopted, "
          "and the store's own matching one is kept",
          adopted == [] and scratch.recording("store") == in_store, adopted)

    failing_checkout, _ = scratch.worktree("pr-fails", scratch.m0, {
        SUITE: SUITE_BODY + "raise SystemExit(1)\n"})
    scratch.run(failing_checkout, since=scratch.m0, save_to="pr-fails-recordings")
    (scratch.root / "empty-store").mkdir()
    adopted = runner.adopt_passing_recordings_that_match_the_checkout(
        failing_checkout, scratch.root / "empty-store", [scratch.root / "pr-fails-recordings"])
    check("a recording of a run that failed is not adopted, even on its own tree",
          scratch.recording("pr-fails-recordings")["exit"] == 1 and adopted == [], adopted)

    scratch.run(main_checkout, save_to="read-only-recordings")
    saved_apart = next((scratch.root / "read-only-recordings").glob("*"))
    store_before = scratch.recording("store")
    saved_apart.chmod(0o555)
    try:
        result = scratch.run(main_checkout, save_to="read-only-recordings")
    finally:
        saved_apart.chmod(0o755)
    check("a recording that cannot be saved apart leaves the store as it was, and says the "
          "earlier recording where saves go could not be removed either",
          f"inputs of {SUITE} not recorded: " in result.stdout
          and f"Delete {saved_apart / (SUITE + '.json')} before the next run" in result.stdout
          and scratch.recording("store") == store_before, result.stdout)

    no_suites = scratch.root / "no-suites"
    no_suites.mkdir()
    git(no_suites, "init", "-q")
    commit(no_suites, {"README": "no suites\n"}, "no suites")
    check("a checkout with no suite adopts nothing",
          runner.adopt_passing_recordings_that_match_the_checkout(
              no_suites, scratch.root / "store", [scratch.root / "pr-z-recordings"]) == [])

    real_git = runner.git
    for exit_code, how in ((128, "exits 128"), (-9, "is killed by a signal")):

        def git_whose_ls_files_fails(checkout, *arguments, exit_code=exit_code):
            # Only the listing of suites, so a later git ls-files cannot raise in its place.
            if arguments[:1] == ("ls-files",) and runner.TEST_SUITE_PATHSPEC in arguments:
                return subprocess.CompletedProcess(arguments, exit_code, "", "fatal: injected\n")
            return real_git(checkout, *arguments)

        runner.git = git_whose_ls_files_fails
        try:
            runner.adopt_passing_recordings_that_match_the_checkout(
                main_checkout, scratch.root / "store", [scratch.root / "pr-z-recordings"])
            refused = None
        except runner.CouldNotRun as refusal:
            refused = str(refusal)
        finally:
            runner.git = real_git
        check(f"a git ls-files of the suites that {how} is refused with git's error",
              refused is not None and "git ls-files failed" in refused
              and "fatal: injected" in refused, refused)

    not_a_repository = scratch.root / "not-a-repository"
    not_a_repository.mkdir()
    try:
        runner.adopt_passing_recordings_that_match_the_checkout(
            not_a_repository, scratch.root / "store", [])
        refused = None
    except runner.CouldNotRun as refusal:
        refused = str(refusal)
    check("a directory git cannot list is refused with git's error",
          refused is not None and "git" in refused, refused)

    print()
    if failures:
        print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
        return 1
    print("all cases passed")
    return 0


if __name__ == "__main__":
    try:
        exit_code = main()
    finally:
        for directory in scratch_directories:
            shutil.rmtree(directory, ignore_errors=True)
    sys.exit(exit_code)
