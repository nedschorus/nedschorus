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
supervisor_state_path(), supervisor_lock_path() and supervisor_state_paths()
(user-ruled 2026-09-19, walk
file-naming-and-location-standards-cold-read-findings, item 4: reduce each
repeated name to one definition).

This reads each script's syntax tree rather than its lines, after two rounds
of the earlier line-matching version being wrong in both directions. Matching
text could not tell a comment from code: a comment containing an apostrophe
and the file name failed the suite, while the same comment without the
apostrophe passed. It also could not see a composition spread over two lines,
or one written with str.format instead of an f-string. The tree has no
comments in it at all, does not care where a line ends, and says what each
expression is, so all three go away together rather than one regex at a time.

What counts as composing the name, and so fails:

- a string that contains the file name, wherever it appears
- an f-string with either suffix constant in a replacement field
- either suffix constant on one side of a `+`
- either suffix constant passed to .format()

What does not: taking a name apart, as agent_name_from_supervisor_file() does
with endswith() and len(); a docstring that writes the pattern out for a
reader; and the bodies of the composing helpers, whose whole job this is.
Their line ranges come from the tree, so a helper renamed without being
renamed in COMPOSING_HELPERS below fails a case rather than silently
exempting whatever takes its place.

Test files keep their literals on purpose: that literal is the assertion, and
it is what fails loudly if the name is ever changed.

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
# The two file names, as they read on disk.
SPELLED_OUT_NAMES = ("-supervisor-state.json", "-supervisor.lock")
# The constants that hold them.
SUFFIX_CONSTANTS = frozenset(
    {"SUPERVISOR_STATE_FILE_SUFFIX", "SUPERVISOR_LOCK_FILE_SUFFIX"})
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
    """Every script a seat runs -- test files excluded."""
    return sorted(path for path in SCRIPTS_DIRECTORY.glob("*.py")
                  if not path.name.endswith("-test.py"))


def names_a_suffix_constant(node):
    """True when this expression is one of the suffix constants.

    Both `SUPERVISOR_STATE_FILE_SUFFIX` and the qualified
    `supervisor.SUPERVISOR_STATE_FILE_SUFFIX` count: a program that reaches
    for the constant through the imported module is composing the name just
    as surely as one that holds its own copy.
    """
    if isinstance(node, ast.Name):
        return node.id in SUFFIX_CONSTANTS
    if isinstance(node, ast.Attribute):
        return node.attr in SUFFIX_CONSTANTS
    return False


def docstring_nodes(tree):
    """Every docstring in the module, by identity.

    A docstring writes the file name out for a reader -- the supervisor's own
    explains that a state file and a lock file are named after the agent --
    and explaining a name is not composing one.
    """
    found = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                                 ast.AsyncFunctionDef)):
            continue
        body = getattr(node, "body", None)
        if (body and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)):
            found.add(id(body[0].value))
    return found


def definition_value_nodes(tree):
    """The right-hand side of each `SUPERVISOR_*_FILE_SUFFIX = "..."`.

    That string is the one definition this test exists to protect, so it is
    the one string allowed to spell the name out.
    """
    found = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if any(isinstance(target, ast.Name) and target.id in SUFFIX_CONSTANTS
               for target in node.targets):
            found.add(id(node.value))
    return found


def exempt_lines_and_helpers(tree, path):
    """The lines the composing helpers occupy, and which were found."""
    if path != SUPERVISOR_SCRIPT:
        return set(), []
    exempt, found = set(), []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in COMPOSING_HELPERS:
            found.append(node.name)
            exempt.update(range(node.lineno, (node.end_lineno or node.lineno) + 1))
    return exempt, found


def composing_sites(path):
    """Every place in `path` that builds either file name."""
    tree = ast.parse(path.read_text())
    exempt_lines, helpers = exempt_lines_and_helpers(tree, path)
    allowed = docstring_nodes(tree) | definition_value_nodes(tree)
    sites = []

    def report(node, how):
        line = getattr(node, "lineno", 0)
        if line not in exempt_lines:
            sites.append(f"{path.name}:{line} ({how})")

    for node in ast.walk(tree):
        if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                and id(node) not in allowed
                and any(name in node.value for name in SPELLED_OUT_NAMES)):
            report(node, "the name spelled out")
        elif isinstance(node, ast.JoinedStr):
            if any(isinstance(part, ast.FormattedValue)
                   and names_a_suffix_constant(part.value)
                   for part in node.values):
                report(node, "an f-string built from the suffix constant")
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            if names_a_suffix_constant(node.left) or names_a_suffix_constant(node.right):
                report(node, "the suffix constant concatenated")
        elif isinstance(node, ast.Call):
            if (isinstance(node.func, ast.Attribute) and node.func.attr == "format"
                    and any(names_a_suffix_constant(argument)
                            for argument in node.args)):
                report(node, "the suffix constant passed to .format()")
    return sites, helpers


composing = []
helpers_found = []
for script in production_scripts():
    sites, helpers = composing_sites(script)
    composing.extend(sites)
    helpers_found.extend(helpers)

check("no production script composes either file name itself",
      not composing,
      "composed at " + ", ".join(composing) + " -- call "
      "supervisor_state_path(), supervisor_lock_path() or "
      "supervisor_state_paths() instead")

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
