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

WHAT IT FAILS, in a cold-read program:

  * a path join whose string operand holds `cold-read-records` anywhere, or
    is exactly the frozen target's `target`, or is a name this program bound
    to such a string itself;
  * a `def` of one of the module's names;
  * a binding of one of the module's names -- plain, annotated, augmented,
    walrus, or one element of an unpacking -- to anything but an attribute
    read off the shared module. The object is checked, not just the
    attribute, so `RECORDS_DIR = cell_common.RECORDS_DIR` fails: the name a
    program gave the module is read from its own loader block, so a program
    that never loads it has no such object and every owned name it binds is
    a copy;
  * a `while` loop whose test is a bare `<path>.exists()` call, which is the
    same-day collision loop, under whatever name the function around it
    carries. The three copies this change deleted were each written that way
    inside a differently named wrapper, so a list of names would not have
    found them.

WHAT IT DOES NOT FAIL, said plainly so no one reads cover into it:

  * prose. These programs name the directory in a reviewer's instructions,
    the store's README, an argument's help text, and the shipper's scp
    destination on ned-box, which is the log-store's path rather than a
    checkout's. Naming a directory is not composing a path, and a guard that
    refused prose would be worse than one that misses a shape. All four were
    measured.
  * the collision rule rewritten in another shape: a `for` over a counter,
    recursion, or a `while` testing `is_dir()`. The signature is the one
    shape the deleted copies were written in, not the idea behind them.
  * `while not <path>.exists()` -- a program waiting for a file to appear
    asks the opposite question and is left alone.
  * the frozen target's name used anywhere but as a path join's operand:
    `if "target" in directory.name` passes.
  * an owned name that arrives as a function parameter, a class attribute or
    an `import ... as`, rather than as a binding of its own.
  * a copy of the value written out at a second remove: a name bound to a
    name bound to the string. Only the first hop is followed.

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
# The records directory's name, as it reads on disk. Matched as a substring
# of a path join's string operand, because `"cold-read-records/<name>"`
# spells the name out as surely as `"cold-read-records"` alone.
SPELLED_OUT_VALUES = ("cold-read-records",)
# The frozen target's name, matched EXACTLY and only as a path join's whole
# string operand. `record_dir / "target"` is the copy this guard is for,
# while `record_dir / "target-with-sentence-ids.md"` is a different file
# whose name merely starts with the word; a substring search would refuse
# the second along with the first, and the word is too common for that.
JOINED_SEGMENT_VALUES = ("target",)
# The constants that hold the names, and the helpers that build them. A
# program may bind these to its own module-level name -- the grid keeps
# RECORDS_DIR -- but only as a reference to the module's, never as a copy.
OWNED_NAMES = frozenset({
    "RECORDS_DIR", "FROZEN_TARGET_DIRECTORY_NAME", "record_name_for_target",
    "record_directory_name_for_target", "fresh_record_directory"})
# How a program loads the shared module: a spec from the file's name, then a
# module from the spec. Followed rather than assumed, so a program that calls
# its binding something other than `record_names` is still checked.
SPEC_CALL = "spec_from_file_location"
MODULE_CALL = "module_from_spec"
# The question a search for a free name asks of a candidate path.
PATH_TAKEN_CALL = "exists"

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


def call_attribute(call):
    """The attribute a call goes through -- `module_from_spec` for
    `importlib.util.module_from_spec(...)` -- or None for a plain call."""
    return call.func.attr if isinstance(call.func, ast.Attribute) else None


def assigned_names(target):
    """Every name an assignment target binds, unpacking included: both of
    `RECORDS_DIR, other = ...`, the nested names of a nested unpacking, and
    the name behind a `*rest`."""
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, ast.Starred):
        return assigned_names(target.value)
    if isinstance(target, (ast.Tuple, ast.List)):
        names = []
        for element in target.elts:
            names.extend(assigned_names(element))
        return names
    return []


def shared_module_bindings(tree):
    """What this program called the shared module, read from its loader block.

    A program that does not load the module gets an empty set, so every owned
    attribute it reads comes from some other object and counts as a copy.
    """
    spec_names = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Assign) and isinstance(node.value, ast.Call)
                and call_attribute(node.value) == SPEC_CALL
                and any(isinstance(inner, ast.Constant)
                        and inner.value == NAMES_MODULE.name
                        for inner in ast.walk(node.value))):
            for target in node.targets:
                spec_names.update(assigned_names(target))
    bindings = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Assign) and isinstance(node.value, ast.Call)
                and call_attribute(node.value) == MODULE_CALL
                and any(isinstance(argument, ast.Name)
                        and argument.id in spec_names
                        for argument in node.value.args)):
            for target in node.targets:
                bindings.update(assigned_names(target))
    return bindings


def names_holding_the_value(tree):
    """The program's own names for the records directory's spelled-out value.

    `MY_RECORDS = "cold-read-records"` and then `REPO_ROOT / MY_RECORDS`
    builds the path from the value as surely as writing it in the join does,
    so the first hop is followed. The shipper's scp destination holds the
    value too and is never joined onto, which is why the name alone is not
    the finding.
    """
    holders = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Assign)
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)):
            continue
        if not any(value in node.value.value for value in SPELLED_OUT_VALUES):
            continue
        for target in node.targets:
            holders.update(assigned_names(target))
    return holders


def owned_bindings(node):
    """(name, value) for every owned name this statement binds.

    `value` is what the name is bound to when the statement says so plainly,
    and None when it does not -- an unpacking, a bare annotation, an
    augmented assignment -- none of which is a reference to the module.
    """
    if isinstance(node, ast.Assign):
        pairs = []
        for target in node.targets:
            if isinstance(target, ast.Name):
                pairs.append((target.id, node.value))
            else:
                pairs.extend((name, None) for name in assigned_names(target))
        return [pair for pair in pairs if pair[0] in OWNED_NAMES]
    if isinstance(node, ast.AnnAssign):
        if isinstance(node.target, ast.Name) and node.target.id in OWNED_NAMES:
            return [(node.target.id, node.value)]
        return []
    if isinstance(node, ast.AugAssign):
        if isinstance(node.target, ast.Name) and node.target.id in OWNED_NAMES:
            return [(node.target.id, None)]
        return []
    if isinstance(node, ast.NamedExpr):
        if isinstance(node.target, ast.Name) and node.target.id in OWNED_NAMES:
            return [(node.target.id, node.value)]
        return []
    return []


def reads_from_the_module(node, module_bindings):
    """True when this expression reaches into the shared module.

    `record_names.RECORDS_DIR` is a reference. A fresh string is a copy, and
    so is `cell_common.RECORDS_DIR` -- the same attribute read off a
    different object -- which is why the object is checked and not only the
    attribute's name.
    """
    return (isinstance(node, ast.Attribute) and node.attr in OWNED_NAMES
            and isinstance(node.value, ast.Name)
            and node.value.id in module_bindings)


def searches_for_a_free_name(test):
    """True when a `while` test asks whether a candidate path is taken, which
    is how the same-day collision rule is written: `while candidate.exists()`.

    `while not candidate.exists()`, a program waiting for a file to appear,
    asks the opposite question; requiring the bare call leaves it alone.
    """
    return (isinstance(test, ast.Call) and isinstance(test.func, ast.Attribute)
            and test.func.attr == PATH_TAKEN_CALL)


own_copies = []
for script in cold_read_scripts():
    source = script.read_text()
    # Every parse names its file, so a script that is unparseable -- one an
    # agent is part-way through editing -- raises a SyntaxError that says
    # which file and line, rather than `File "<unknown>", line 1`.
    tree = ast.parse(source, filename=str(script))
    module_bindings = shared_module_bindings(tree)
    value_holders = names_holding_the_value(tree)

    for node in ast.walk(tree):
        # A path built from the value: `REPO_ROOT / "cold-read-records"`, or
        # `record_dir / "target"`. Only a pathlib join counts. These programs
        # also write both names in prose -- a reviewer's instructions, the
        # store's README, an argument's help text, and the shipper's scp
        # destination on ned-box, which is the log-store's path rather than a
        # checkout's -- and prose naming a directory is not a program
        # composing its path.
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            for side in (node.left, node.right):
                if isinstance(side, ast.Constant) and isinstance(side.value, str):
                    if any(value in side.value for value in SPELLED_OUT_VALUES):
                        own_copies.append(
                            f"{script.name}:{node.lineno} (a path built from "
                            f"the value written out)")
                    elif side.value in JOINED_SEGMENT_VALUES:
                        own_copies.append(
                            f"{script.name}:{node.lineno} (a path joined onto "
                            f'"{side.value}" written out)')
                elif isinstance(side, ast.Name) and side.id in value_holders:
                    own_copies.append(
                        f"{script.name}:{node.lineno} (a path built from "
                        f"{side.id}, this program's own copy of the value)")
        # A def of one of the module's functions.
        elif isinstance(node, ast.FunctionDef) and node.name in OWNED_NAMES:
            own_copies.append(f"{script.name}:{node.lineno} (its own {node.name}())")
        # The same-day collision rule written out again, whatever the
        # function around it is called.
        elif isinstance(node, ast.While) and searches_for_a_free_name(node.test):
            own_copies.append(
                f"{script.name}:{node.lineno} (its own loop over taken names)")
        # A binding of an owned name to anything but the module's copy.
        elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign,
                               ast.NamedExpr)):
            for name, value in owned_bindings(node):
                if not reads_from_the_module(value, module_bindings):
                    own_copies.append(
                        f"{script.name}:{node.lineno} ({name} not taken "
                        f"from the module)")

check("no cold-read program keeps its own copy of these names",
      not own_copies,
      "found " + ", ".join(own_copies) + f" -- import {NAMES_MODULE.name} and "
      "read the value from it")

# The module must actually define everything it is credited with, or the
# check above passes by finding nothing anywhere.
module_tree = ast.parse(NAMES_MODULE.read_text(), filename=str(NAMES_MODULE))
defined = set()
for node in ast.walk(module_tree):
    if isinstance(node, ast.FunctionDef):
        defined.add(node.name)
    elif isinstance(node, ast.Assign):
        defined.update(target.id for target in node.targets
                       if isinstance(target, ast.Name))
    elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        defined.add(node.target.id)
missing = sorted(OWNED_NAMES - defined)
check("the shared module defines every name it owns",
      not missing,
      f"{NAMES_MODULE.name} is missing {missing}")

# Every program that binds an owned name must have loaded the module under
# some name of its own, or the check above cannot tell a reference from a
# copy and would read the binding as a copy for the wrong reason.
unloaded = []
for script in cold_read_scripts():
    tree = ast.parse(script.read_text(), filename=str(script))
    if shared_module_bindings(tree):
        continue
    if any(owned_bindings(node) for node in ast.walk(tree)):
        unloaded.append(script.name)
check("every program that binds an owned name loads the shared module",
      not unloaded,
      f"{unloaded} bind one of the module's names without loading "
      f"{NAMES_MODULE.name}; load it the way the cold-read-cells load theirs")

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
