#!/usr/bin/env python3
"""Fails while a test file keeps its own copy of wording that one of WORDING_MODULES holds.

Each test file other than a module's own test gets the module's wording by calling the module, so a change to the
wording fails one suite. This suite reads every tracked test file, so it is kept apart from each module's own test:
a change to any test file then selects only this small suite.

Run: python3 nc-systems/general-tools/tests/common-module-wording-copied-into-other-test-files-guard-for-each-wording-module-test.py
Prints one line per module and exits non-zero if any module's wording is copied.
"""

import importlib.util
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
WORDING_MODULES = (
    "nc-systems/cold-read/cold-read-cell-common.py",
    "nc-systems/general-tools/failed-command-agent-facing-message-rerun-once-then-stop-and-report-lines-common.py",
    "nc-systems/general-tools/shell-command-tree-sitter-bash-reader-common.py",
    "nc-systems/general-tools/tmux-target-or-server-does-not-exist-error-pattern-common.py",
)

_finder_spec = importlib.util.spec_from_file_location(
    "common_module_wording_copied_into_other_test_files_finder_common",
    REPOSITORY_ROOT / "nc-systems" / "general-tools" / "common-module-wording-copied-into-other-test-files-finder-common.py")
finder = importlib.util.module_from_spec(_finder_spec)
_finder_spec.loader.exec_module(finder)

failures = 0
for module in WORDING_MODULES:
    copies = finder.common_module_wording_copies_in_other_test_files(REPOSITORY_ROOT / module, REPOSITORY_ROOT)
    if copies:
        failures += 1
        print(f"FAIL  {module}: another test file keeps its own copy of its wording:")
        for copy in copies:
            print(f"      {finder.copied_wording_report_line(copy)}")
    else:
        print(f"PASS  {module}: no other test file keeps its own copy of its wording")

print(f"{failures} failure(s)" if failures else "all cases pass")
sys.exit(1 if failures else 0)
