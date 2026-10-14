#!/usr/bin/env python3
"""Tests for .claude/hooks/guard_approval_marker.py, the one-use approval marker
every write guard reads.

The guards' own suites reach this module only through their callers. These
cases pin its three functions directly, so a change that keeps one guard's
suite passing but breaks the marker's rules for another guard fails here.

Run: python3 .claude/hooks/guard-approval-marker-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import importlib.util
import os
import sys
import tempfile
from pathlib import Path

MODULE_PATH = Path(os.environ.get(
    "GUARD_APPROVAL_MARKER_MODULE_PATH",
    Path(__file__).resolve().parent / "guard_approval_marker.py"))
_spec = importlib.util.spec_from_file_location("guard_approval_marker", MODULE_PATH)
marker = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(marker)

failures = 0


def check(name, condition, detail=None):
    global failures
    if condition:
        print(f"PASS  {name}")
    else:
        failures += 1
        print(f"FAIL  {name}: {detail!r}")


with tempfile.TemporaryDirectory() as scratch:
    scratch = Path(scratch)

    absent = scratch / "absent-marker"
    check("an absent marker approves nothing",
          marker.read_marker_approval(absent) is None, marker.read_marker_approval(absent))
    check("an absent marker would not pass", marker.marker_would_pass(absent) is False)
    check("consuming an absent marker reports no approval",
          marker.consume_approval_marker(absent) is False)

    empty = scratch / "empty-marker"
    empty.write_text("", encoding="utf-8")
    check("an empty marker approves nothing", marker.read_marker_approval(empty) is None)
    check("consuming an empty marker reports no approval and leaves the file",
          marker.consume_approval_marker(empty) is False and empty.exists())

    blank = scratch / "blank-marker"
    blank.write_text(" \n\t\n", encoding="utf-8")
    check("a marker holding only whitespace approves nothing",
          marker.read_marker_approval(blank) is None)

    worded = scratch / "worded-marker"
    worded.write_text('\n  the user said "y"  \n', encoding="utf-8")
    check("a marker's words come back stripped",
          marker.read_marker_approval(worded) == 'the user said "y"',
          marker.read_marker_approval(worded))
    check("a worded marker would pass, and checking does not spend it",
          marker.marker_would_pass(worded) is True and worded.exists())
    check("consuming a worded marker reports approval and deletes it",
          marker.consume_approval_marker(worded) is True and not worded.exists())
    check("a consumed marker approves nothing the second time",
          marker.consume_approval_marker(worded) is False)

    directory = scratch / "a-directory-not-a-marker"
    directory.mkdir()
    check("a marker path that is a directory approves nothing (an OSError is not approval)",
          marker.read_marker_approval(directory) is None)

    undecodable = scratch / "undecodable-marker"
    undecodable.write_bytes(b"\xff\xfe approval")
    try:
        result = marker.read_marker_approval(undecodable)
        check("a marker that is not UTF-8 approves nothing, without crashing the guard",
              result is None, result)
        check("a marker that is not UTF-8 would not pass", marker.marker_would_pass(undecodable) is False)
        check("consuming a marker that is not UTF-8 reports no approval and leaves the file",
              marker.consume_approval_marker(undecodable) is False and undecodable.exists())
    except UnicodeDecodeError as error:
        check("a marker that is not UTF-8 approves nothing, without crashing the guard", False,
              f"raised {error.__class__.__name__}")

    if os.geteuid() != 0:
        locked_directory = scratch / "read-only-directory"
        locked_directory.mkdir()
        locked = locked_directory / "marker"
        locked.write_text("approved", encoding="utf-8")
        locked_directory.chmod(0o500)
        try:
            check("approval stands when the marker cannot be deleted",
                  marker.consume_approval_marker(locked) is True and locked.exists())
        finally:
            locked_directory.chmod(0o700)
    else:
        print("SKIP  approval stands when the marker cannot be deleted: running as root, "
              "which can delete from a read-only directory")

print(f"{failures} failure(s)" if failures else "all cases pass")
sys.exit(1 if failures else 0)
