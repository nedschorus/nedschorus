#!/usr/bin/env python3
"""Tests for nc-systems/general-tools/rule-enforcing-nc-test-suite-failure-message-closing-lines-text-common.py.

The rule-enforcing nc-test-suites print these lines through their own cases.
These cases pin the wording word for word, and check that no other test file
keeps its own copy of it.

Run: python3 nc-systems/general-tools/tests/rule-enforcing-nc-test-suite-failure-message-closing-lines-text-common-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import importlib.util
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = (REPOSITORY_ROOT / "nc-systems" / "general-tools"
               / "rule-enforcing-nc-test-suite-failure-message-closing-lines-text-common.py")
_spec = importlib.util.spec_from_file_location(
    "rule_enforcing_nc_test_suite_failure_message_closing_lines_text_common", MODULE_PATH)
lines = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lines)

_report_lines_spec = importlib.util.spec_from_file_location(
    "failed_command_agent_facing_message_rerun_once_then_stop_and_report_lines_common",
    REPOSITORY_ROOT / "nc-systems" / "general-tools"
    / "failed-command-agent-facing-message-rerun-once-then-stop-and-report-lines-common.py")
report_lines = importlib.util.module_from_spec(_report_lines_spec)
_report_lines_spec.loader.exec_module(report_lines)

failures = 0


def check(name, condition, detail=None):
    global failures
    if condition:
        print(f"PASS  {name}")
    else:
        failures += 1
        print(f"FAIL  {name}: {detail!r}")


check("the guarded-file line names the file, the approval page and the guard's refusal",
      lines.guarded_file_fix_failure_message_line_pointing_to_approval_page_and_guard_refusal("CLAUDE.md") == (
          "CLAUDE.md is protected by the instruction-file guard; whether your fix needs the "
          "user's approval is decided by "
          "docs/nedschorus-wiki/nedschorus-which-changes-need-the-users-approval.md, and the "
          "guard's refusal gives the steps."),
      lines.guarded_file_fix_failure_message_line_pointing_to_approval_page_and_guard_refusal("CLAUDE.md"))
check("the approval page the guarded-file line names is in the repository",
      (REPOSITORY_ROOT / lines.APPROVAL_PAGE_PATH).is_file(),
      lines.APPROVAL_PAGE_PATH)
check("the closing line names who to tell, with the shared phrase, and keeps the fix out",
      lines.FAILURE_MAY_COME_FROM_MAIN_NOT_YOUR_CHANGE_REPORT_IT_CLOSING_LINE == (
          "If your change touched none of the files named above, the failure may not come "
          f"from your change: tell {report_lines.REPORT_RECIPIENT_PHRASE_USER_OR_DISPATCHING_AGENT} "
          "this message and what your change touched, and leave the fix out "
          "of your own pull request unless the user says otherwise."),
      lines.FAILURE_MAY_COME_FROM_MAIN_NOT_YOUR_CHANGE_REPORT_IT_CLOSING_LINE)

_wording_copies_finder_spec = importlib.util.spec_from_file_location(
    "common_module_wording_copied_into_other_test_files_finder_common",
    REPOSITORY_ROOT / "nc-systems" / "general-tools" / "common-module-wording-copied-into-other-test-files-finder-common.py")
wording_copies_finder = importlib.util.module_from_spec(_wording_copies_finder_spec)
_wording_copies_finder_spec.loader.exec_module(wording_copies_finder)
wording_copies = wording_copies_finder.common_module_wording_copies_in_other_test_files(
    MODULE_PATH, REPOSITORY_ROOT)
check("no other test file keeps its own copy of this module's wording: each gets the wording by calling the module",
      wording_copies == [], "\n".join(map(wording_copies_finder.copied_wording_report_line, wording_copies)))

print(f"{failures} failure(s)" if failures else "all cases pass")
sys.exit(1 if failures else 0)
