#!/usr/bin/env python3
"""The environment variables that make git act on a different repository, and
an environment with them removed.

Set in an agent-session or a test suite, each of these points a git command at
another repository's files whatever `-C` or the working directory says, so a
program that runs git on a repository it names removes them first. This module
is the one place the list is written; scripts/git-redirecting-environment-variables-defined-once-test.py
fails when a copy of the list appears anywhere else.

Kept: GIT_NAMESPACE, which renames refs inside one repository and does not
reach another, and GIT_CEILING_DIRECTORIES, whose removal would widen, not
narrow, where git looks for a repository. scripts/run-all-test-suites.py's
docstring says what each variable was measured to do.

Load it by path, under the snake_case form of its file name:

    spec = importlib.util.spec_from_file_location(
        "git_redirecting_environment_variables_removal_common", <path>)
"""

import os

GIT_REDIRECTING_ENVIRONMENT_VARIABLES = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_COMMON_DIR",
)


def environment_without_git_redirecting_variables(environment=None):
    """Return a new dict copy of `environment`, os.environ when None, without the variables."""
    source = os.environ if environment is None else environment
    return {name: value for name, value in source.items()
            if name not in GIT_REDIRECTING_ENVIRONMENT_VARIABLES}
