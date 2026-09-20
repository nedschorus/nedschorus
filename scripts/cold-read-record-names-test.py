#!/usr/bin/env python3
"""The cold-read-record's directory and frozen-target names have one
definition each, and this test keeps it that way.

Four programs create or find cold-read-records -- the cold-read-grid, the
cold-read-fast-read, the cold-read-restater-judge-runner and the record
shipper -- and the cold-read-cells' shared module looks for the frozen
target. Each used to hold its own copy of the names, so a rename had seven
places to find and nothing failed when it missed one. They now come from
scripts/cold-read-record-names.py (user-ruled 2026-09-19, walk
file-naming-and-location-standards-cold-read-findings, item 4).

This reads each script's syntax tree rather than its lines, which is what
scripts/supervisor-file-names-defined-once-test.py arrived at after three
rounds of a line-matching version being wrong in both directions: matching
text cannot tell a comment from code, a str.format from an f-string, or a
composition spread over two lines from one on a single line. Starting from
the tree skips those three rounds.

Only the cold-read family is checked. scripts/sanity-check-attacks.py and
scripts/design-to-main/design-to-main-state-tables.py name their own record
kinds, which are theirs to name.

Run: python3 scripts/cold-read-record-names-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIRECTORY = REPO_ROOT / "scripts"
NAMES_MODULE = SCRIPTS_DIRECTORY / "cold-read-record-names.py"
# The values the module owns, as they read on disk.
SPELLED_OUT_VALUES = ("cold-read-records",)
# The constants that hold the names, and the helpers that build them. A
# program may bind these to its own module-level name -- the grid keeps
# RECORDS_DIR -- but only as a reference to the module's, never as a copy.
OWNED_NAMES = frozenset({
    "RECORDS_DIR", "FROZEN_TARGET_DIRECTORY_NAME", "record_name_for_target",
    "record_directory_name_for_target", "fresh_record_directory"})

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def cold_read_scripts():
    """The cold-read family's programs, the shared module itself excluded."""
    return sorted(path for path in SCRIPTS_DIRECTORY.glob("cold-read-*.py")
                  if not path.name.endswith("-test.py") and path != NAMES_MODULE)


def reads_from_the_module(node):
    """True when this expression reaches into the shared module.

    `record_names.RECORDS_DIR` is a reference; a fresh string or a `def` of
    the same name is a copy.
    """
    return isinstance(node, ast.Attribute) and node.attr in OWNED_NAMES


own_copies = []
for script in cold_read_scripts():
    source = script.read_text()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        # A path built from the value: `REPO_ROOT / "cold-read-records"`.
        # Only a pathlib join counts. These programs also write the name in
        # prose -- a reviewer's instructions, the store's README, an
        # argument's help text, and the shipper's scp destination on ned-box,
        # which is the log-store's path rather than a checkout's -- and prose
        # naming a directory is not a program composing its path.
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            for side in (node.left, node.right):
                if (isinstance(side, ast.Constant) and isinstance(side.value, str)
                        and any(value in side.value for value in SPELLED_OUT_VALUES)):
                    own_copies.append(
                        f"{script.name}:{node.lineno} (a path built from the "
                        f"value written out)")
        # A def of one of the module's functions.
        elif isinstance(node, ast.FunctionDef) and node.name in OWNED_NAMES:
            own_copies.append(f"{script.name}:{node.lineno} (its own {node.name}())")
        # An assignment of an owned name to anything but the module's copy.
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if (isinstance(target, ast.Name) and target.id in OWNED_NAMES
                        and not reads_from_the_module(node.value)):
                    own_copies.append(
                        f"{script.name}:{node.lineno} ({target.id} not taken "
                        f"from the module)")

check("no cold-read program keeps its own copy of these names",
      not own_copies,
      "found " + ", ".join(own_copies) + f" -- import {NAMES_MODULE.name} and "
      "read the value from it")

# The module must actually define everything it is credited with, or the
# check above passes by finding nothing anywhere.
module_tree = ast.parse(NAMES_MODULE.read_text())
defined = set()
for node in ast.walk(module_tree):
    if isinstance(node, ast.FunctionDef):
        defined.add(node.name)
    elif isinstance(node, ast.Assign):
        defined.update(target.id for target in node.targets
                       if isinstance(target, ast.Name))
missing = sorted(OWNED_NAMES - defined)
check("the shared module defines every name it owns",
      not missing,
      f"{NAMES_MODULE.name} is missing {missing}")

# The module is a module: importing it must not run a program.
check("the shared module has no command-line entry point",
      "__main__" not in NAMES_MODULE.read_text(),
      f"{NAMES_MODULE.name} looks runnable; it is imported by five programs "
      f"and should do nothing on its own")

print()
if failures:
    print(f"{len(failures)} case(s) failed")
    sys.exit(1)
print("all cases passed")
