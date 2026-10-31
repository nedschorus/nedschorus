#!/usr/bin/env python3
"""The closing lines of a failure message from an nc-test-suite that checks a repository-wide rule.

Such a suite fails when the repository breaks a rule that spans files, such as
two tracked files sharing a name, and the agent reading the failure often broke
the rule in a file it has not read. Every such message ends with the lines here,
so a correction to their wording reaches every suite at once:

- guarded_file_fix_failure_message_line_pointing_to_approval_page_and_guard_refusal,
  when the fix lands in a file the instruction-file guard protects: the steps
  live in the guard's refusal, so this line only points there;
- FAILURE_MAY_COME_FROM_MAIN_NOT_YOUR_CHANGE_REPORT_IT_CLOSING_LINE, last in
  every message, because the suite selection can let two pull requests that each pass break a rule
  together on main, and the reader must not fold that fix into its own pull
  request.

Load it by path, under the snake_case form of its file name:

    spec = importlib.util.spec_from_file_location(
        "rule_enforcing_nc_test_suite_failure_message_closing_lines_text_common", <path>)
"""

import importlib.util
from pathlib import Path

_report_lines_spec = importlib.util.spec_from_file_location(
    "failed_command_agent_facing_message_rerun_once_then_stop_and_report_lines_common",
    Path(__file__).resolve().parent
    / "failed-command-agent-facing-message-rerun-once-then-stop-and-report-lines-common.py")
_report_lines = importlib.util.module_from_spec(_report_lines_spec)
_report_lines_spec.loader.exec_module(_report_lines)

APPROVAL_PAGE_PATH = (
    "docs/nedschorus-wiki/nedschorus-which-changes-need-the-users-approval.md")

FAILURE_MAY_COME_FROM_MAIN_NOT_YOUR_CHANGE_REPORT_IT_CLOSING_LINE = (
    "If your change touched none of the files named above, the failure may not come from "
    f"your change: tell {_report_lines.REPORT_RECIPIENT_PHRASE_USER_OR_DISPATCHING_AGENT} "
    "this message and what your change touched, and leave the fix out of your own pull "
    "request unless the user says otherwise.")


def guarded_file_fix_failure_message_line_pointing_to_approval_page_and_guard_refusal(file):
    """The line for a fix that lands in `file`, a path the instruction-file guard protects."""
    return (f"{file} is protected by the instruction-file guard; whether your fix needs the "
            f"user's approval is decided by {APPROVAL_PAGE_PATH}, "
            f"and the guard's refusal gives the steps.")
