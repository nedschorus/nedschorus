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

This test reads the scripts as text rather than importing them, because what
it checks is how the name is written, not what the programs compute.

Run: python3 scripts/supervisor-file-names-defined-once-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIRECTORY = REPO_ROOT / "scripts"
SUPERVISOR_SCRIPT = SCRIPTS_DIRECTORY / "handoff-supervisor.py"

# An f-string that composes either file name from a seat name, e.g.
# f"{agent}-supervisor-state.json". Docstrings and comments write the pattern
# as <agent>-supervisor-state.json, which this does not match.
COMPOSED_NAME = re.compile(r"\{[^}]*\}-supervisor(?:-state\.json|\.lock)")
# The suffix constants, at the start of a line, where they are defined.
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


composing = []
for path in production_scripts():
    for line_number, line in enumerate(path.read_text().splitlines(), start=1):
        if COMPOSED_NAME.search(line):
            composing.append(f"{path.name}:{line_number}")
check("no production script composes the file name itself",
      not composing,
      "composed in " + ", ".join(composing) + " -- call "
      "supervisor.supervisor_state_path() or supervisor_lock_path() instead")

defining = [path.name for path in production_scripts()
            if SUFFIX_DEFINITION.search(path.read_text())]
check("the suffix constants are defined in one script",
      defining == [SUPERVISOR_SCRIPT.name],
      f"defined in {defining or 'no script'}, expected only "
      f"{SUPERVISOR_SCRIPT.name}")

supervisor_source = SUPERVISOR_SCRIPT.read_text()
for helper in ("supervisor_state_path", "supervisor_lock_path"):
    check(f"{helper}() exists to compose the path",
          f"def {helper}(" in supervisor_source,
          f"{SUPERVISOR_SCRIPT.name} defines no {helper}()")

print()
if failures:
    print(f"{len(failures)} case(s) failed")
    sys.exit(1)
print("all cases passed")
