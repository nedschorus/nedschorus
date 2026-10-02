#!/usr/bin/env python3
"""Takes the variables that redirect git out of a test suite's own process.

Not a test file, and not a program a seat runs: the suites that build a
scratch repository with `git init` load it and call
remove_git_redirecting_environment_variables_from_this_process() before they
run git. Its name ends `-test-fixture.py` rather than `-test.py` so
scripts/run-all-test-suites.py, which finds suites with
`git ls-files -- '*-test.py'`, does not run it as a suite of its own.

WHY IT EXISTS. scripts/run-all-test-suites.py launches every suite with
GIT_DIR and the other variables that redirect git removed; its docstring says
what each was measured to do. A suite run directly, by a person or an agent,
gets no such thing: started with GIT_DIR set, its `git init` re-initialises
the repository GIT_DIR names instead of making one in its scratch directory,
and every later git command lands there. That is how a suite run directly
put 14 test commits on a live seat's branch and overwrote the shared
`user.name` and `user.email` on ned-box on 2026-09-22. GitHub issue "Test
suites write into the ambient repository when GIT_DIR is set: git init's
result is unchecked and the suite runner passes no environment"
(https://github.com/nedschorus/nedschorus/issues/639), "Next action" item 2.

WHY THE PROCESS'S ENVIRONMENT, not the environment of one git helper. A suite
starts the program it tests with its own environment, and that program runs
git too: scripts/checkout-freshness-catch-up-test.py starts
checkout-freshness-catch-up.py with `dict(os.environ)`. Removing the
variables from os.environ once, before the first git, covers the suite's own
git, every process it starts, and every git those run. A suite that gives a
child one of these variables on purpose still does: it sets the variable in
that child's environment after this has run.

WHY NOT A CHECK THAT `git init` MADE THE REPOSITORY, which is what the issue
first proposed. By the time such a check fails, `git init` has already run
against the repository the variable names. Measured 2026-10-01 with git
2.56.0: with GIT_DIR naming a linked worktree's git directory, which is what
a seat's checkout has, `git init` alone writes `core.bare = true` into the
config every worktree of that clone shares, the value found in ned-box's
shared clone after the 2026-09-24 run. With the variables gone, `git init`
makes the repository where it was told to, and there is nothing left for the
check to catch.

WHICH VARIABLES. The list is GIT_REDIRECTING_ENVIRONMENT_VARIABLES in
scripts/run-all-test-suites.py, read from that file and not copied here, so
a suite run directly and a suite the runner launches have the same ones
removed.
scripts/test-suites-run-directly-ignore-git-redirecting-environment-test.py
checks that every suite and fixture that runs `git init` calls this first.
"""

import importlib.util
import os
from pathlib import Path

RUNNER_PATH = Path(__file__).resolve().with_name("run-all-test-suites.py")


def _load_runner():
    spec = importlib.util.spec_from_file_location("run_all_test_suites", RUNNER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GIT_REDIRECTING_ENVIRONMENT_VARIABLES = _load_runner().GIT_REDIRECTING_ENVIRONMENT_VARIABLES


def remove_git_redirecting_environment_variables_from_this_process():
    for variable in GIT_REDIRECTING_ENVIRONMENT_VARIABLES:
        os.environ.pop(variable, None)
