#!/usr/bin/env python3
"""Every program that removes the variables that redirect git removes all six.

Each case sets all six variables listed in
nc-systems/general-tools/git-redirecting-environment-variables-removal-common.py,
then makes one caller run git, or the program it starts, and records which of
the six reached it. A stand-in `git`, first on PATH, records the environment
it was started with and runs no real git, so no case can reach the repository
a variable names. The list the cases set is written out here, not read from
the module, so a variable dropped from the module fails here too.

Run: python3 scripts/git-redirecting-environment-variables-removed-by-every-caller-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]

# The oracle, written out on purpose; scripts/git-redirecting-environment-variables-defined-once-test.py
# allows this one copy for that reason.
EXPECTED_VARIABLES = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
                      "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_COMMON_DIR")
RECORD_VARIABLE = "GIT_REDIRECTING_REMOVAL_TEST_RECORD"

# Records which of the six it was started with, as JSON, one line per start.
STAND_IN_PROGRAM = f"""#!{sys.executable}
import json, os
with open(os.environ[{RECORD_VARIABLE!r}], "a", encoding="utf-8") as record:
    record.write(json.dumps(sorted(name for name in {EXPECTED_VARIABLES!r}
                                   if name in os.environ)) + "\\n")
print(os.getcwd())
"""

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def load(module_name, relative_path):
    spec = importlib.util.spec_from_file_location(module_name, REPOSITORY_ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def leaked_from(environment):
    return sorted(set(environment) & set(EXPECTED_VARIABLES))


with tempfile.TemporaryDirectory(prefix="git-redirecting-removal-") as scratch:
    scratch = Path(scratch).resolve()
    stand_in_directory = scratch / "stand-in-bin"
    stand_in_directory.mkdir()
    stand_in_git = stand_in_directory / "git"
    stand_in_git.write_text(STAND_IN_PROGRAM, encoding="utf-8")
    stand_in_git.chmod(0o755)
    stand_in_cleaner = scratch / "stand-in-clean-worktrees.py"
    stand_in_cleaner.write_text(STAND_IN_PROGRAM, encoding="utf-8")
    record = scratch / "record.jsonl"
    target_directory = scratch / "target"
    target_directory.mkdir()

    saved = {name: os.environ.get(name)
             for name in (*EXPECTED_VARIABLES, "PATH", RECORD_VARIABLE)}

    def set_the_six():
        for name in EXPECTED_VARIABLES:
            os.environ[name] = str(scratch / "elsewhere" / ".git")

    def recorded_leaks(case_name, run):
        """Run one caller with the six set; return what its stand-in saw, or None."""
        record.write_text("", encoding="utf-8")
        set_the_six()
        try:
            run()
        except Exception as error:   # noqa: BLE001 -- reported as the case's failure
            check(case_name, False, f"{type(error).__name__}: {error}")
            return None
        lines = record.read_text(encoding="utf-8").splitlines()
        if not lines:
            check(case_name, False, "the stand-in was never started")
            return None
        return sorted({name for line in lines for name in json.loads(line)})

    try:
        os.environ["PATH"] = f"{stand_in_directory}{os.pathsep}{os.environ.get('PATH', '')}"
        os.environ[RECORD_VARIABLE] = str(record)

        # Loaded with the six unset, so a module that runs git when loaded is not misled.
        for name in EXPECTED_VARIABLES:
            os.environ.pop(name, None)
        runner = load("run_all_test_suites", "scripts/run-all-test-suites.py")
        fixture = load("git_redirecting_environment_removal_test_fixture",
                       "scripts/git-redirecting-environment-removal-test-fixture.py")
        review_plan = load("pull_request_review_plan", "scripts/pull-request-review-plan.py")
        saver = load("save_uncommitted_scratch_worktrees_before_reboot",
                     "scripts/save-uncommitted-scratch-worktrees-before-reboot.py")
        locator = load("locate_file_copies_across_machines",
                       "scripts/locate-file-copies-across-machines.py")
        supervisor = load("handoff_supervisor", "nc-systems/handoff/handoff-supervisor.py")
        fast_read = load("cold_read_fast_read", "nc-systems/cold-read/cold-read-fast-read.py")
        scratch_fixture = load("cold_read_scratch_repository_test_fixture",
                               "nc-systems/cold-read/tests/cold-read-scratch-repository-test-fixture.py")

        set_the_six()
        left = leaked_from(runner.environment_without_git_redirecting_variables())
        check("scripts/run-all-test-suites.py launches suites and runs git without any of the six",
              not left, left)
        left = leaked_from(runner.launch_environment_for_a_test_suite_with_git_redirecting_agent_session_attendance_and_credential_variables_removed())
        check("scripts/run-all-test-suites.py's suite launch environment has none of the six",
              not left, left)

        set_the_six()
        left = leaked_from(locator.environment_without_git_redirecting_variables())
        check("scripts/locate-file-copies-across-machines.py runs git without any of the six",
              not left, left)

        set_the_six()
        fixture.remove_git_redirecting_environment_variables_from_this_process()
        left = leaked_from(os.environ)
        check("scripts/git-redirecting-environment-removal-test-fixture.py takes all six "
              "out of the suite's process", not left, left)

        case = "scripts/pull-request-review-plan.py runs git without any of the six"
        seen = recorded_leaks(case, lambda: review_plan.run_git_in_repository(target_directory, "status"))
        if seen is not None:
            check(case, seen == [], seen)

        case = "scripts/save-uncommitted-scratch-worktrees-before-reboot.py runs git without any of the six"
        seen = recorded_leaks(case, lambda: saver.git(["status"], target_directory))
        if seen is not None:
            check(case, seen == [], seen)

        case = ("nc-systems/handoff/handoff-supervisor.py starts the worktree cleaner "
                "without any of the six")
        supervisor.CLEAN_WORKTREES_PATH = stand_in_cleaner
        seen = recorded_leaks(case, lambda: supervisor.remove_finished_worktrees_at_handoff(target_directory))
        if seen is not None:
            check(case, seen == [], seen)

        case = "nc-systems/cold-read/cold-read-fast-read.py runs git without any of the six"
        seen = recorded_leaks(case, lambda: fast_read.checkout_root_holding(target_directory / "a.md"))
        if seen is not None:
            check(case, seen == [], seen)

        case = ("nc-systems/cold-read/tests/cold-read-scratch-repository-test-fixture.py "
                "runs git without any of the six")
        seen = recorded_leaks(case, lambda: scratch_fixture.git(target_directory, "status"))
        if seen is not None:
            check(case, seen == [], seen)

        # The stand-in itself must see a variable that is set, or every case above passes vacuously.
        case = "the stand-in git records a variable that reaches it"
        seen = recorded_leaks(case, lambda: subprocess.run(
            ["git", "status"], capture_output=True, check=False))
        if seen is not None:
            check(case, seen == sorted(EXPECTED_VARIABLES), seen)
    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

print()
if failures:
    print(f"{len(failures)} case(s) failed:")
    for failure in failures:
        print(f"  {failure}")
    sys.exit(1)
print("all cases passed")
