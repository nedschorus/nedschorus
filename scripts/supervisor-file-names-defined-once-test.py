#!/usr/bin/env python3
"""The supervisor's state and lock file names have one definition each, and
this test keeps it that way.

Five programs need the path of a seat's supervisor state file: the supervisor
itself, the recovery tool, resupervise-seat.py, the login restart and the
handoff writer. Until 2026-09-19 each built the name from its own f-string --
eleven sites across the five, plus a second copy of the suffix constant in
scripts/restart-live-seats-at-login.py -- so a rename had eleven places to
find and nothing that failed when it missed one. The suffixes now live in
scripts/handoff-supervisor.py alone, and the path is composed only by its
supervisor_state_path() and supervisor_lock_path() (user-ruled 2026-09-19,
walk file-naming-and-location-standards-cold-read-findings, item 4: reduce
each repeated name to one definition).

A name can be composed two ways, and the first version of this test caught
only one. It looked for the suffix spelled out inside an f-string, so a
twelfth site written f"{name}{SUPERVISOR_STATE_FILE_SUFFIX}" -- following the
constant, but composing the path itself -- passed it. The reviewers of PR 545
found the blind spot and a live instance of the second form in the supervisor
itself. Both forms now fail, and that instance calls supervisor_lock_path()
instead.

Widening the pattern found a second site the first version missed: the login
restart searched for every seat's state file with glob(f"*{SUFFIX}"), which
spells the name out as surely as a path does. It calls the new
supervisor_state_paths() instead, and no longer needs the suffix at all.

The three helpers compose the name, which is their whole job, so their bodies
are the one exemption. Their line ranges are read from the syntax tree rather
than matched as text, so renaming or moving one does not silently widen the
exemption -- a helper renamed without being renamed here fails the second
case instead.

This test reads the scripts as source rather than importing them, because
what it checks is how the name is written, not what the programs compute.

Run: python3 scripts/supervisor-file-names-defined-once-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import ast
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIRECTORY = REPO_ROOT / "scripts"
SUPERVISOR_SCRIPT = SCRIPTS_DIRECTORY / "handoff-supervisor.py"
# The functions that compose the names, and so the only code allowed to.
COMPOSING_HELPERS = ("supervisor_state_path", "supervisor_lock_path",
                     "supervisor_state_paths")

# The file name written out inside a quoted string, e.g. "-supervisor.lock"
# or f"{agent}-supervisor-state.json". Docstrings and comments write the
# pattern as <agent>-supervisor-state.json, unquoted, which this does not
# match.
SPELLED_OUT = re.compile(r"""["'][^"'\n]*-supervisor(?:-state\.json|\.lock)""")
# The suffix constant used to build a name: inside an f-string replacement
# field, or concatenated. `endswith(suffix)` and `len(suffix)`, which take a
# name apart rather than build one, do not match.
COMPOSED_FROM_CONSTANT = re.compile(
    r"\{[^{}\n]*SUPERVISOR_(?:STATE|LOCK)_FILE_SUFFIX[^{}\n]*\}"
    r"|\+\s*(?:\w+\.)?SUPERVISOR_(?:STATE|LOCK)_FILE_SUFFIX")
# The suffix constants where they are defined, at the start of a line.
SUFFIX_DEFINITION = re.compile(
    r'^SUPERVISOR_(?:STATE|LOCK)_FILE_SUFFIX\s*=\s*["\']', re.MULTILINE)

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def production_scripts():
    """Every script a seat runs -- test files excluded.

    A test file spells the real file name on purpose: that literal is the
    assertion, and it is what fails loudly if the name is ever changed.
    """
    return sorted(path for path in SCRIPTS_DIRECTORY.glob("*.py")
                  if not path.name.endswith("-test.py"))


def exempt_line_numbers(path):
    """The lines the helpers occupy, which may compose the name.

    Read from the syntax tree, so a helper that is renamed stops being
    exempt instead of exempting whatever takes its place.
    """
    if path != SUPERVISOR_SCRIPT:
        return set(), []
    tree = ast.parse(path.read_text())
    exempt, found = set(), []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in COMPOSING_HELPERS:
            found.append(node.name)
            exempt.update(range(node.lineno, (node.end_lineno or node.lineno) + 1))
    return exempt, found


composing = []
helpers_found = []
for path in production_scripts():
    exempt, found = exempt_line_numbers(path)
    helpers_found.extend(found)
    source = path.read_text()
    definition_lines = {source[:match.start()].count("\n") + 1
                        for match in SUFFIX_DEFINITION.finditer(source)}
    for line_number, line in enumerate(source.splitlines(), start=1):
        if line_number in exempt or line_number in definition_lines:
            continue
        if SPELLED_OUT.search(line) or COMPOSED_FROM_CONSTANT.search(line):
            composing.append(f"{path.name}:{line_number}")

check("no production script composes either file name itself",
      not composing,
      "composed at " + ", ".join(composing) + " -- call "
      "supervisor_state_path() or supervisor_lock_path() instead, whether the "
      "name is spelled out or built from the suffix constant")

check("every composing helper was found in the syntax tree",
      sorted(helpers_found) == sorted(COMPOSING_HELPERS),
      f"found {sorted(helpers_found)} in {SUPERVISOR_SCRIPT.name}, expected "
      f"{sorted(COMPOSING_HELPERS)}; a helper that is renamed must be renamed "
      f"in COMPOSING_HELPERS here, or its body stops being checked")

defining = [path.name for path in production_scripts()
            if SUFFIX_DEFINITION.search(path.read_text())]
check("the suffix constants are defined in one script",
      defining == [SUPERVISOR_SCRIPT.name],
      f"defined in {defining or 'no script'}, expected only "
      f"{SUPERVISOR_SCRIPT.name}")

print()
if failures:
    print(f"{len(failures)} case(s) failed")
    sys.exit(1)
print("all cases passed")
