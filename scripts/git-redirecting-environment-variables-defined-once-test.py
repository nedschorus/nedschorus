#!/usr/bin/env python3
"""The list of environment variables that redirect git has one definition,
and this test keeps it that way.

The list lives in
nc-systems/general-tools/git-redirecting-environment-variables-removal-common.py.
A program that writes out its own copy can fall behind the module: a copy that
holds only some of the variables lets the others point that program's git at
another repository. So every Python file git lists, tracked or untracked and
not ignored, is read, and a tuple, list or set literal that names at least
MINIMUM_NAMES_THAT_MAKE_A_COPY of the variables fails here, unless its file is
in ALLOWED_COPIES with the reason it cannot load the module. Outside the tests,
a literal of two or more names that holds nothing but the variables fails too,
since a short copy falls behind the module the same way.

Not counted: a dict literal, which in the suites gives each variable a decoy
value to set rather than defining the list; a test's literal of fewer names,
such as its choice of two variables to set for one case; and a literal that
names a few of the variables among other strings, such as the keys a program
reads from a recorded git call.

Run: python3 scripts/git-redirecting-environment-variables-defined-once-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import ast
import importlib.util
import subprocess
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = "nc-systems/general-tools/git-redirecting-environment-variables-removal-common.py"

_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_variables_removal_common", REPOSITORY_ROOT / MODULE_PATH)
removal = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(removal)

# Four of six: a stale copy missing a variable or two still counts, and a
# test's pair of variables for one case does not.
MINIMUM_NAMES_THAT_MAKE_A_COPY = 4

# Each file allowed one written-out copy, with why it cannot load the module.
ALLOWED_COPIES = {
    MODULE_PATH: "the definition itself",
    "scripts/locate-file-copies-across-machines.py":
        "it is sent over ssh alone and run from stdin on the other machine, where it cannot "
        "load a sibling module; scripts/locate-file-copies-across-machines-test.py fails "
        "when its copy differs from the module's",
    "nc-systems/general-tools/tests/git-redirecting-environment-variables-removal-common-test.py":
        "the oracle the module is checked against, written out so a variable dropped from "
        "the module fails there",
    "scripts/git-redirecting-environment-variables-removed-by-every-caller-test.py":
        "the oracle every caller is checked against, for the same reason",
    "scripts/find-deleted-path-across-backups-test.py":
        "the oracle the backup search's own removal is checked against, for the same reason",
}

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def is_a_test_file(filename):
    return filename.endswith("-test.py") or "/tests/" in filename


def copies_of_the_list(source, filename):
    """Line numbers of the collection literals in `source` that copy the list."""
    variables = set(removal.GIT_REDIRECTING_ENVIRONMENT_VARIABLES)
    lines = []
    for node in ast.walk(ast.parse(source, filename=filename)):
        if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            strings = [element.value for element in node.elts
                       if isinstance(element, ast.Constant) and isinstance(element.value, str)]
            named = set(strings) & variables
            short_copy = (not is_a_test_file(filename) and len(named) >= 2
                          and len(strings) == len(node.elts) and set(strings) <= variables)
            if len(named) >= MINIMUM_NAMES_THAT_MAKE_A_COPY or short_copy:
                lines.append(node.lineno)
    return sorted(lines)


def python_files_git_lists():
    listed = subprocess.run(
        ["git", "-C", str(REPOSITORY_ROOT), "ls-files", "-z", "--cached", "--others",
         "--exclude-standard", "--", "*.py"],
        capture_output=True, text=True, check=False,
        env=removal.environment_without_git_redirecting_variables())
    if listed.returncode != 0:
        print(f"git ls-files in {REPOSITORY_ROOT} exited {listed.returncode}: "
              f"{listed.stderr.strip()}", file=sys.stderr)
        sys.exit(2)
    return sorted({path for path in listed.stdout.split("\0") if path})


# --- The detector finds what it is meant to find ----------------------------
check("a planted tuple of the six is found",
      copies_of_the_list('X = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE",\n'
                         '     "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES",\n'
                         '     "GIT_COMMON_DIR")\n', "<planted>") == [1])
check("a planted list missing two of the six is found",
      copies_of_the_list('X = ["GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR"]\n',
                         "<planted>") == [1])
check("a program's short copy of three of the six is found",
      copies_of_the_list('X = ("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR")\n',
                         "scripts/planted.py") == [1])
check("a program's tuple naming two of the six among other keys is not counted",
      copies_of_the_list('X = ("arguments", "directory", "GIT_DIR", "GIT_WORK_TREE")\n',
                         "scripts/planted.py") == [])
check("a test's pair of the six, and a dict of all six, are not counted",
      copies_of_the_list('X = ("GIT_DIR", "GIT_WORK_TREE")\n'
                         'Y = {"GIT_DIR": 1, "GIT_WORK_TREE": 2, "GIT_INDEX_FILE": 3,\n'
                         '     "GIT_OBJECT_DIRECTORY": 4, "GIT_ALTERNATE_OBJECT_DIRECTORIES": 5,\n'
                         '     "GIT_COMMON_DIR": 6}\n', "scripts/planted-test.py") == [])

# --- No file outside ALLOWED_COPIES writes the list out ----------------------
copies_found = {}
for relative_path in python_files_git_lists():
    path = REPOSITORY_ROOT / relative_path
    if not path.is_file():
        continue    # deleted in the working tree, not yet in the index
    try:
        found = copies_of_the_list(path.read_text(encoding="utf-8"), relative_path)
    except (SyntaxError, UnicodeDecodeError) as error:
        check(f"{relative_path} can be read", False, f"{type(error).__name__}: {error}")
        continue
    if found:
        copies_found[relative_path] = found

check("the module still defines the list",
      MODULE_PATH in copies_found, sorted(copies_found))
unexplained = {path: lines for path, lines in copies_found.items() if path not in ALLOWED_COPIES}
check("no file outside the allowed copies writes out the list of variables that redirect git",
      not unexplained,
      "; ".join(f"{path} line(s) {lines}" for path, lines in sorted(unexplained.items()))
      + f" -- load {MODULE_PATH} and use its GIT_REDIRECTING_ENVIRONMENT_VARIABLES or "
        "environment_without_git_redirecting_variables() instead")
over_allowed = {path: lines for path, lines in copies_found.items()
                if path in ALLOWED_COPIES and len(lines) > 1}
check("each allowed file holds one copy", not over_allowed, over_allowed)
stale = sorted(set(ALLOWED_COPIES) - set(copies_found))
check("every allowed copy still exists, so the allowance can be removed when it does not",
      not stale, stale)

print()
if failures:
    print(f"{len(failures)} case(s) failed:")
    for failure in failures:
        print(f"  {failure}")
    sys.exit(1)
print("all cases passed")
