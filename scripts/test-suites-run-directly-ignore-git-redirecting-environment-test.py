#!/usr/bin/env python3
"""A test suite run directly, with a variable that redirects git set, leaves
the repository that variable names alone.

WHAT WENT WRONG. A suite that needs a git repository builds one with
`git init` in a scratch directory. Started with GIT_DIR set, that `git init`
re-initialises the repository GIT_DIR names and exits 0, no repository is
made in the scratch directory, and every later git command of the suite, and
of the program it tests, lands in the named repository. On 2026-09-22 a suite
run directly on ned-box put 14 commits by a test identity on a live seat's
branch and overwrote the `user.name` and `user.email` shared by every
worktree of that clone; on 2026-09-24 another wrote `core.bare=true` there.
GitHub issue "Test suites write into the ambient repository when GIT_DIR is
set: git init's result is unchecked and the suite runner passes no
environment" (https://github.com/nedschorus/nedschorus/issues/639).
scripts/run-all-test-suites.py removes the variables from every suite it
launches, which does nothing for a suite run directly. Measured 2026-10-01
on main, 80 of its 82 suites each run directly with GIT_DIR naming a
throwaway repository: 20 wrote into it, two of them while exiting 0.

THE FIX THIS SUITE PINS. A suite, or a fixture, that runs `git init` first
calls remove_git_redirecting_environment_variables_from_this_process() from
scripts/git-redirecting-environment-removal-test-fixture.py, which takes the
variables scripts/run-all-test-suites.py strips out of the suite's own
process. Out of the process, not out of one git helper's environment: the
program a suite tests is started with the suite's environment, and runs git
too.

WHAT IT CHECKS.

  * Reading every `*-test.py` and `*-test-fixture.py` file git tracks: one
    that runs `git init` makes that call on an earlier line than its first
    `git init`. A suite that landed a day after the issue was filed built its
    scratch repository the same unprotected way, so the count this rule
    covers rises with every such suite, and nothing else would tell its
    author. REMOVE_THE_VARIABLES_ANOTHER_WAY lists the files that were
    measured to leave the named repository alone before this suite existed
    and says how each does it; this suite does not check what they do.

  * Running real suites directly, each started with one variable naming a
    throwaway repository this suite builds: that repository keeps its HEAD,
    its commits, its tracked files and its `user.name` and `user.email`; no
    file in it, .git included, is added, removed or changed, which is what
    catches GIT_INDEX_FILE and GIT_OBJECT_DIRECTORY; and the suite exits 0,
    so none of that is read off a crash. One suite is started with GIT_DIR,
    the variable both incidents had set: on main it wrote 63 commits into
    the named repository while exiting 0. One short suite, which on main
    crashed under GIT_DIR after writing, is started with each variable the
    runner strips, alone.
    GIT_ALTERNATE_OBJECT_DIRECTORIES writes nothing into the repository it
    names, so its case passed before the suites removed the variables; it is
    there so that every variable the runner strips has a case.

  * It has a case for every variable the runner strips, so a seventh added
    to the runner fails here until it has one.

HOW A FAILING RUN IS KEPT AWAY FROM A LIVE REPOSITORY. The suites are run out
of a copy of their files in a temporary directory that is in no repository,
so a variable that redirects only part of git (the work tree, the index, the
object store) has no checkout to combine with. Each variable is set only in
the environment of the one suite process, and only ever names a repository
this suite built in that temporary directory. This suite removes the
variables from its own environment before it runs git: it reads the runner's
list itself rather than calling the fixture, so that it still runs, and
fails for the reason above, where the fixture is missing or broken.

WHAT IT DOES NOT COVER. A suite that runs git without ever running
`git init`; the variables git honours that the runner does not strip; and
the suites it does not run, beyond the line the first check reads.

Run: python3 scripts/test-suites-run-directly-ignore-git-redirecting-environment-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNNER_PATH = "scripts/run-all-test-suites.py"
FIXTURE_PATH = "scripts/git-redirecting-environment-removal-test-fixture.py"
REMOVAL_CALL = "remove_git_redirecting_environment_variables_from_this_process()"

# A git `init` argument as the suites write it, in a list or as a helper's
# argument. Written as a character class so this file's own text does not
# hold the pattern it looks for anywhere but in its real `git init` calls.
GIT_INIT_ARGUMENT = re.compile(r"""["']init["']""")

# Files that run `git init` and do not call the fixture, with how each keeps
# git out of the repository a variable names. Measured 2026-10-01: each one
# run directly with GIT_DIR naming a throwaway repository left it
# byte-identical.
REMOVE_THE_VARIABLES_ANOTHER_WAY = {
    "nc-systems/cold-read/tests/cold-read-scratch-repository-test-fixture.py":
        "its git() removes the runner's six from the environment of every git it runs",
    "nc-systems/cold-read/tests/"
    "cold-read-scratch-repository-fixture-ignores-git-redirecting-environment-test.py":
        "it removes the six from its own environment before it runs git",
    "nc-systems/cold-read/tests/cold-read-fast-read-test.py":
        "its own `git init` runs with GIT_DIR and GIT_WORK_TREE removed",
    "scripts/branch-conflict-check-test.py":
        "its git runs with every GIT_ variable removed",
    "scripts/daily-full-test-run-of-main-test.py":
        "its fixture_git() runs with the runner's own stripped environment",
    "scripts/find-deleted-path-across-backups-test.py":
        "its git helpers remove GIT_DIR, and GIT_WORK_TREE with it",
    "scripts/git-client-side-hooks-pre-push-test.py":
        "every GIT_ variable is removed from each case's environment",
    "scripts/locate-file-copies-across-machines-test.py":
        "its git() removes the same six from the environment of every git it runs",
    "scripts/pull-request-head-test-run-test.py":
        "its fixture_git() runs with the runner's own stripped environment",
    "scripts/unvalidated-negative-result-check-test.py":
        "its git runs with every GIT_ variable removed",
    "scripts/test-suites-run-directly-ignore-git-redirecting-environment-test.py":
        "this suite: it removes the runner's list from its own environment, below",
}

# Each suite this one runs directly, with the other files it reads. Only
# these, the fixture and the runner are copied, so this suite's recorded
# inputs are these files and not the whole checkout. A suite here that comes
# to read another file fails its "exits 0" case until the file is listed.
SUITES_RUN_WITH_GIT_DIR = {
    "scripts/dangling-path-citation-check-test.py": (
        "scripts/dangling-path-citation-check.py", "scripts/md-drift-lint.py"),
}
SUITE_RUN_WITH_EVERY_VARIABLE = "scripts/code-review-codex-cell-test.py"
FILES_THE_SUITE_RUN_WITH_EVERY_VARIABLE_READS = (
    "scripts/code-review-codex-cell.py",
    "nc-systems/cold-read/cold-read-cell-common.py",
    "nc-systems/cold-read/cold-read-record-names.py",
)

# Where each variable points, relative to the named repository's top
# directory: the value git itself would use for that repository.
NAMED_REPOSITORY_PATH_FOR_VARIABLE = {
    "GIT_DIR": ".git",
    "GIT_WORK_TREE": ".",
    "GIT_INDEX_FILE": ".git/index",
    "GIT_OBJECT_DIRECTORY": ".git/objects",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES": ".git/objects",
    "GIT_COMMON_DIR": ".git",
}

NAMED_REPOSITORY_IDENTITY = ("the named repository's own identity",
                             "named-repository@nedschorus.invalid")

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def load_module(module_name, path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = load_module("run_all_test_suites", REPO_ROOT / RUNNER_PATH)

# Before anything runs git: a variable this suite was started with must
# reach neither this suite's own git calls nor the suites it starts.
for _variable in runner.GIT_REDIRECTING_ENVIRONMENT_VARIABLES:
    os.environ.pop(_variable, None)


def own_git(repository, *arguments):
    """This suite's own git, with the user's hooks and signing kept out."""
    return subprocess.run(
        ["git", "-C", str(repository), "-c", "core.hooksPath=/dev/null",
         "-c", "commit.gpgsign=false", *arguments],
        capture_output=True, text=True, check=False)


def build_named_repository(repository):
    """The repository a variable points at, standing in for a live checkout:
    one commit, and a committing identity pinned in its own config."""
    repository.mkdir()
    (repository / "real-work.txt").write_text("the seat's real work\n", encoding="utf-8")
    for arguments in (("init", "-q", "-b", "main"),
                      ("config", "maintenance.auto", "false"),
                      ("config", "user.name", NAMED_REPOSITORY_IDENTITY[0]),
                      ("config", "user.email", NAMED_REPOSITORY_IDENTITY[1]),
                      ("add", "-A"),
                      ("commit", "-q", "-m", "the seat's real commit")):
        completed = own_git(repository, *arguments)
        if completed.returncode != 0:
            raise RuntimeError(f"named repository git {' '.join(arguments)}: "
                               f"{completed.stderr.strip()}")


def state_of(repository):
    """What the issue's reproduction compares, as git answers it."""
    def answer(*arguments):
        completed = own_git(repository, *arguments)
        return (completed.stdout.strip() if completed.returncode == 0
                else f"git exit {completed.returncode}: {completed.stderr.strip()}")
    return {
        "HEAD": answer("rev-parse", "HEAD"),
        "commits": answer("rev-list", "--all").split("\n"),
        "tracked files": answer("ls-files").split("\n"),
        "identity": (answer("config", "user.name"), answer("config", "user.email")),
    }


def every_path_and_its_bytes(directory):
    """Each file's bytes, and each directory as None, keyed by relative path."""
    return {str(path.relative_to(directory)):
            (path.read_bytes() if path.is_file() else None)
            for path in directory.rglob("*")}


def tracked_suites_and_fixtures():
    listed = own_git(REPO_ROOT, "ls-files", "-z", "--", "*-test.py", "*-test-fixture.py")
    if listed.returncode != 0:
        raise RuntimeError(f"git ls-files in {REPO_ROOT}: {listed.stderr.strip()}")
    return [path for path in listed.stdout.split("\0") if path]


# --- Every file that runs `git init` first removes the variables -------------
for relative_path in tracked_suites_and_fixtures():
    if not (REPO_ROOT / relative_path).is_file():
        continue    # deleted in the working tree, not yet in the index
    lines = (REPO_ROOT / relative_path).read_text(encoding="utf-8").split("\n")
    first_git_init = next((number for number, line in enumerate(lines, start=1)
                           if GIT_INIT_ARGUMENT.search(line)), None)
    if first_git_init is None:
        continue
    if relative_path in REMOVE_THE_VARIABLES_ANOTHER_WAY:
        continue
    removal_call = next((number for number, line in enumerate(lines, start=1)
                         if REMOVAL_CALL in line), None)
    check(f"{relative_path} removes the variables that redirect git before its "
          f"first `git init`",
          removal_call is not None and removal_call < first_git_init,
          f"its first `git init` is on line {first_git_init} and "
          + ("it never calls " + REMOVAL_CALL if removal_call is None
             else f"its call of {REMOVAL_CALL} is on line {removal_call}"))

# --- Real suites run directly leave the named repository alone ---------------
check("this suite has a case for every variable the runner strips",
      set(NAMED_REPOSITORY_PATH_FOR_VARIABLE)
      == set(runner.GIT_REDIRECTING_ENVIRONMENT_VARIABLES),
      f"the runner strips {sorted(runner.GIT_REDIRECTING_ENVIRONMENT_VARIABLES)}, "
      f"this suite sets {sorted(NAMED_REPOSITORY_PATH_FOR_VARIABLE)}")

runs = [(suite, "GIT_DIR") for suite in SUITES_RUN_WITH_GIT_DIR]
runs += [(SUITE_RUN_WITH_EVERY_VARIABLE, variable)
         for variable in NAMED_REPOSITORY_PATH_FOR_VARIABLE]

files_to_copy = [RUNNER_PATH, FIXTURE_PATH, SUITE_RUN_WITH_EVERY_VARIABLE,
                 *FILES_THE_SUITE_RUN_WITH_EVERY_VARIABLE_READS]
for suite, files_it_reads in SUITES_RUN_WITH_GIT_DIR.items():
    files_to_copy += [suite, *files_it_reads]

with tempfile.TemporaryDirectory(prefix="test-suites-run-directly-") as temporary:
    temporary = Path(temporary).resolve()
    copy = temporary / "copy-of-the-suites"
    for relative_path in files_to_copy:
        # A file that is missing is left out, and the suite that needs it
        # fails its "exits 0" case by name.
        if (REPO_ROOT / relative_path).is_file():
            (copy / relative_path).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(REPO_ROOT / relative_path, copy / relative_path)

    for number, (suite, variable) in enumerate(runs):
        named = temporary / f"named-repository-{number}"
        build_named_repository(named)
        state_before = state_of(named)
        paths_before = every_path_and_its_bytes(named)

        environment = dict(os.environ)
        environment[variable] = str(named / NAMED_REPOSITORY_PATH_FOR_VARIABLE[variable])
        completed = subprocess.run(
            [sys.executable, "-u", suite], cwd=str(copy), env=environment,
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, check=False)

        state_after = state_of(named)
        paths_after = every_path_and_its_bytes(named)
        changed_state = [f"{key}: {state_before[key]!r} -> {state_after[key]!r}"
                         for key in state_before if state_before[key] != state_after[key]]
        changed_paths = sorted(path for path in set(paths_before) | set(paths_after)
                               if paths_before.get(path, "absent")
                               != paths_after.get(path, "absent"))

        case = f"{suite} run directly with {variable} naming another repository"
        check(f"{case}: that repository keeps its HEAD, commits, tracked files "
              f"and identity",
              not changed_state, "; ".join(changed_state)[:600])
        check(f"{case}: no file in that repository, .git included, is added, "
              f"removed or changed",
              not changed_paths,
              f"{len(changed_paths)} path(s) added, removed or changed, "
              f"first {changed_paths[:5]}")
        check(f"{case}: the suite exits 0",
              completed.returncode == 0,
              f"exit {completed.returncode}; its last lines: "
              f"{completed.stdout.strip().splitlines()[-3:]!r}")

print()
if failures:
    print(f"{len(failures)} case(s) failed:")
    for failure in failures:
        print(f"  {failure}")
    sys.exit(1)
print("all cases passed")
