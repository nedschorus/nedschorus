#!/usr/bin/env python3
"""The cold-read scratch repository fixture builds its repository where it is
told to, whatever git variables the suite was started with.

WHAT WENT WRONG. On 2026-09-24 at 00:10:41Z a reviewer ran a cold-read suite
directly, not through scripts/run-all-test-suites.py, with GIT_DIR set to
ned-box's shared clone. The fixture's git() passed that environment on, so the
`git init` and the three `git config` calls in
commit_seeded_cold_read_scratch_repository wrote into the shared clone's
.git/config, which every worktree on ned-box reads: core.bare=true,
user.name=cold-read scratch repository test fixture,
user.email=test@test.invalid and maintenance.auto=false. They were repaired by
hand the same day, at about 17:08Z and 17:20Z. The runner already strips the
variables that redirect git from every suite it launches; a suite run directly
had no such protection. The fixture's git() now strips the same six. This is
the defect class of GitHub issue 639, "Test suites write into the ambient
repository when GIT_DIR is set", and this suite covers the fixture only.

WHAT IT CHECKS. For each variable the runner strips, set alone and pointed at
an ambient repository this suite builds in a temporary directory:

  * the ambient repository's .git/config is byte-identical afterwards;
  * the ambient repository gains no commit;
  * no other file in the ambient repository, .git included, is added, removed
    or changed, which is what catches GIT_INDEX_FILE and GIT_OBJECT_DIRECTORY,
    neither of which touches the config or the commit list;
  * the scratch repository has its own .git, holding exactly one commit,
    `seed`, whose objects are all in the scratch repository's own store.

The ambient repository holds a copy of the fixture file, and the fixture
copies itself into the scratch repository with the rest of
nc-systems/cold-read/, so both hold the same blob. That is what makes the
GIT_ALTERNATE_OBJECT_DIRECTORIES case bite: git does not write an object it
can already reach through an alternate, so without the fix the scratch
repository's commit points at a blob its own store lacks, and `git fsck`
says so once the variable is gone.

It also checks that it has a case for every variable the runner strips, so a
seventh added to the runner fails here until it has a case, and that case
fails until the fixture strips it too.

This suite pops the six variables from its own environment before it does
anything else, so a run started with one of them set cannot pass it to the
fixture or to this suite's own git calls, and it sets each one only while
the fixture runs.

WHAT IT DOES NOT COVER. Only git run through the fixture's git(). The cells
the cold-read suites launch get the suite's environment, and this suite does
not test them. The fix for all 21 suites that build a scratch repository is
item 2 of GitHub issue 639's "Next action", and it is not this suite.

Run: python3 nc-systems/cold-read/tests/cold-read-scratch-repository-fixture-ignores-git-redirecting-environment-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# This suite sits in nc-systems/cold-read/tests/ beside the fixture; the
# runner whose list the fixture copies is in the repository's scripts/.
TESTS_DIRECTORY = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIRECTORY.parent.parent.parent
FIXTURE_PATH = TESTS_DIRECTORY / "cold-read-scratch-repository-test-fixture.py"
RUNNER_PATH = REPO_ROOT / "scripts" / "run-all-test-suites.py"

# Where each variable points, relative to the ambient repository's top
# directory: the value git itself would use for that repository.
AMBIENT_PATH_FOR_VARIABLE = {
    "GIT_DIR": ".git",
    "GIT_WORK_TREE": ".",
    "GIT_INDEX_FILE": ".git/index",
    "GIT_OBJECT_DIRECTORY": ".git/objects",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES": ".git/objects",
    "GIT_COMMON_DIR": ".git",
}

# Before anything runs git: a variable this suite was started with must reach
# neither the fixture nor this suite's own git calls.
for _variable in AMBIENT_PATH_FOR_VARIABLE:
    os.environ.pop(_variable, None)

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


def own_git(repository, *arguments):
    """This suite's own git. Never called while a case has a variable set."""
    return subprocess.run(["git", "-C", str(repository), *arguments],
                          capture_output=True, text=True, check=False)


def build_ambient_repository(ambient):
    """The repository a variable points at, standing in for a real clone."""
    ambient.mkdir()
    shutil.copy2(FIXTURE_PATH, ambient / FIXTURE_PATH.name)
    for arguments in (("init", "-b", "main"),
                      ("config", "maintenance.auto", "false"),
                      ("config", "user.email", "ambient@test.invalid"),
                      ("config", "user.name", "ambient repository"),
                      ("add", "-A"),
                      ("commit", "-m", "ambient")):
        completed = own_git(ambient, *arguments)
        if completed.returncode != 0:
            raise RuntimeError(f"ambient git {' '.join(arguments)}: "
                               f"{completed.stderr.strip()}")


def every_path_and_its_bytes(directory):
    """Each file's bytes, and each directory as None, keyed by relative path."""
    return {str(path.relative_to(directory)):
            (path.read_bytes() if path.is_file() else None)
            for path in directory.rglob("*")}


fixture = load_module("cold_read_scratch_repository_test_fixture", FIXTURE_PATH)
runner = load_module("run_all_test_suites", RUNNER_PATH)

check("this suite has a case for every variable the runner strips",
      set(AMBIENT_PATH_FOR_VARIABLE) == set(runner.GIT_REDIRECTING_ENVIRONMENT_VARIABLES),
      f"the runner strips {sorted(runner.GIT_REDIRECTING_ENVIRONMENT_VARIABLES)}, "
      f"this suite sets {sorted(AMBIENT_PATH_FOR_VARIABLE)}")

for variable, relative_path in AMBIENT_PATH_FOR_VARIABLE.items():
    with tempfile.TemporaryDirectory(
            prefix="cold-read-scratch-repository-fixture-git-environment-") as temporary:
        ambient = Path(temporary) / "ambient-repository"
        build_ambient_repository(ambient)
        config_before = (ambient / ".git" / "config").read_bytes()
        commits_before = own_git(ambient, "rev-list", "--all").stdout.split()
        paths_before = every_path_and_its_bytes(ambient)

        repository = Path(temporary) / "scratch-repository"
        repository.mkdir()
        (repository / "seed.txt").write_text("seeded by this suite\n", encoding="utf-8")
        raised = None
        os.environ[variable] = str((ambient / relative_path).resolve())
        try:
            fixture.commit_seeded_cold_read_scratch_repository(repository)
        except Exception as error:
            raised = error
        finally:
            os.environ.pop(variable, None)

        config_after = (ambient / ".git" / "config").read_bytes()
        commits_after = own_git(ambient, "rev-list", "--all").stdout.split()
        paths_after = every_path_and_its_bytes(ambient)
        changed_paths = sorted(path for path in set(paths_before) | set(paths_after)
                               if paths_before.get(path, "absent")
                               != paths_after.get(path, "absent"))
        git_directory = own_git(repository, "rev-parse", "--absolute-git-dir")
        subjects = own_git(repository, "log", "--all", "--format=%s")
        fsck = own_git(repository, "fsck", "--full", "--no-dangling")

        check(f"{variable} set: the ambient repository's .git/config is byte-identical",
              config_after == config_before,
              f"it now reads {config_after.decode(errors='replace')!r}")
        check(f"{variable} set: the ambient repository gains no commit",
              commits_after == commits_before,
              f"{len(commits_before)} commit(s) before, {len(commits_after)} after")
        check(f"{variable} set: no other file in the ambient repository changes",
              not changed_paths,
              f"{len(changed_paths)} path(s) added, removed or changed, "
              f"first {changed_paths[:5]}")
        check(f"{variable} set: the scratch repository has its own .git holding "
              f"the seed commit",
              raised is None
              and (repository / ".git").is_dir()
              and git_directory.returncode == 0
              and Path(git_directory.stdout.strip()) == (repository / ".git").resolve()
              and subjects.stdout.split("\n") == ["seed", ""]
              and fsck.returncode == 0,
              f"fixture raised {raised!r}; "
              f"git dir {git_directory.stdout.strip() or git_directory.stderr.strip()!r}; "
              f"commits {subjects.stdout.split()!r}; "
              f"fsck exit {fsck.returncode} "
              f"{(fsck.stdout + fsck.stderr).strip()[:200]!r}")

print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
