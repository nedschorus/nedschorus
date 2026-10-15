#!/usr/bin/env python3
"""Tests for nc-systems/general-tools/git-redirecting-environment-variables-removal-common.py.

Run: python3 nc-systems/general-tools/tests/git-redirecting-environment-variables-removal-common-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import importlib.util
import os
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]

_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_variables_removal_common",
    REPOSITORY_ROOT / "nc-systems" / "general-tools"
    / "git-redirecting-environment-variables-removal-common.py")
removal = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(removal)

# Written out here on purpose, as the oracle the module is checked against.
EXPECTED_VARIABLES = {"GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
                      "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_COMMON_DIR"}
KEPT = {"GIT_NAMESPACE": "a-namespace", "GIT_CEILING_DIRECTORIES": "/elsewhere",
        "PATH": "/usr/bin", "A_VARIABLE_OF_ITS_OWN": "kept"}

failures = 0


def check(name, condition, detail=None):
    global failures
    if condition:
        print(f"PASS  {name}")
    else:
        failures += 1
        print(f"FAIL  {name}: {detail!r}")


check("the module lists exactly the six variables that redirect git",
      set(removal.GIT_REDIRECTING_ENVIRONMENT_VARIABLES) == EXPECTED_VARIABLES
      and len(removal.GIT_REDIRECTING_ENVIRONMENT_VARIABLES) == len(EXPECTED_VARIABLES),
      removal.GIT_REDIRECTING_ENVIRONMENT_VARIABLES)

given = {**{name: "/elsewhere/.git" for name in EXPECTED_VARIABLES}, **KEPT}
given_before = dict(given)
returned = removal.environment_without_git_redirecting_variables(given)
check("a given environment comes back without any of the six",
      not set(returned) & EXPECTED_VARIABLES, sorted(set(returned) & EXPECTED_VARIABLES))
check("every other variable, GIT_NAMESPACE and GIT_CEILING_DIRECTORIES included, "
      "comes back unchanged", returned == KEPT, returned)
check("the given environment is not changed", given == given_before, given)
check("the result is a new dict", returned is not given)

saved = {name: os.environ.get(name) for name in EXPECTED_VARIABLES}
try:
    for name in EXPECTED_VARIABLES:
        os.environ[name] = "/elsewhere/.git"
    returned = removal.environment_without_git_redirecting_variables()
    check("with no environment given, os.environ is copied without any of the six",
          not set(returned) & EXPECTED_VARIABLES and returned.get("PATH") == os.environ.get("PATH"),
          sorted(set(returned) & EXPECTED_VARIABLES))
    check("os.environ itself keeps the six",
          all(os.environ.get(name) == "/elsewhere/.git" for name in EXPECTED_VARIABLES))
finally:
    for name, value in saved.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value

print()
if failures:
    print(f"{failures} case(s) failed")
    sys.exit(1)
print("all cases passed")
