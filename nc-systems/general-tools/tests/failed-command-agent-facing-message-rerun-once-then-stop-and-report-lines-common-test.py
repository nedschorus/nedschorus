#!/usr/bin/env python3
"""Tests for nc-systems/general-tools/failed-command-agent-facing-message-rerun-once-then-stop-and-report-lines-common.py.

The programs that print these lines reach this module through their own
suites. These cases pin the wording itself, word for word, so a change to it
is a change a reviewer sees here.

Run: python3 nc-systems/general-tools/tests/failed-command-agent-facing-message-rerun-once-then-stop-and-report-lines-common-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import importlib.util
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location(
    "failed_command_agent_facing_message_rerun_once_then_stop_and_report_lines_common",
    REPOSITORY_ROOT / "nc-systems" / "general-tools"
    / "failed-command-agent-facing-message-rerun-once-then-stop-and-report-lines-common.py")
next_step_lines = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(next_step_lines)

failures = 0


def check(name, condition, detail=None):
    global failures
    if condition:
        print(f"PASS  {name}")
    else:
        failures += 1
        print(f"FAIL  {name}: {detail!r}")


WHO = "the user, or, if you are a subagent, the agent that dispatched you,"

lines = next_step_lines.git_failure_next_step_lines(
    "`p --x`", "p", text_the_failure_line_contains="p: could not",
    include_the_misspelt_branch_commit_or_path_line=True).splitlines()
check("a git failure in a program that takes names on its command line gets four lines: "
      "two cases, the unchanged rerun when neither applies, and the stop naming "
      "the text to look for, who is told, and which lines",
      lines == [
          "If git's error names a lock file, such as .git/index.lock, wait one minute, "
          "then run exactly `p --x`; do not delete the lock file yourself.",
          "If a branch, commit or path you gave p on its command line is misspelt or does "
          "not exist, correct it in your command, then run the corrected command.",
          "If neither applies, run exactly `p --x` once more.",
          'If the rerun, or the corrected command, prints a line containing "p: could not" '
          f'again, stop, and tell {WHO} word for word, the line containing "p: could not" '
          "from each run."], lines)

lines = next_step_lines.git_failure_next_step_lines(
    "`git -C d status`", "the sync", include_the_misspelt_branch_commit_or_path_line=False,
    rerun_fails_when="prints an error again", which_lines_to_quote_in_the_report="the sync line and the error",
    read_by_a_subagent=False,
    next_step_to_skip_when_the_rerun_fails_too="act on the rest of this prompt").splitlines()
check("a program that takes no names gets one case; a line no subagent reads names only "
      "the user; the stop holds back the work that follows; free text replaces the marker",
      lines[1:] == [
          "If git's error names no lock file, run exactly `git -C d status` once more.",
          "If the rerun prints an error again, stop, do not act on the rest of this prompt, "
          "and tell the user word for word, the sync line and the error."], lines)

for case_name, arguments in [
        ("neither the failure text nor the free-text pair", {}),
        ("the failure text and which lines to quote",
         {"text_the_failure_line_contains": "x", "which_lines_to_quote_in_the_report": "y"}),
        ("the failure text and when the rerun fails",
         {"text_the_failure_line_contains": "x", "rerun_fails_when": "fails"}),
        ("when the rerun fails without which lines to quote", {"rerun_fails_when": "fails"})]:
    try:
        line = next_step_lines.agent_instruction_if_rerun_fails_too_stop_and_report_both_runs_line(
            **arguments)
    except TypeError as error:
        line = None
        said = str(error)
    check(f"a call giving {case_name} is refused, naming the arguments",
          line is None and "text_the_failure_line_contains" in said
          and "which_lines_to_quote_in_the_report" in said, line)

line = next_step_lines.hook_agent_instruction_if_git_failure_recurs_tell_user_both_outputs_line(
    "at your next Edit", "h:")
check("a hook's line names the prefix to look for, says any git failure counts, when to "
      "tell, and that a clean check needs no report",
      line == 'If a line starting "h:" reports a git failure again at your next Edit, whether '
              f"this error or another, tell {WHO} word for word, every line of this message and "
              "of the new one, before you go on. If the check finds no git failure then, this "
              "failure needs no report.", line)

print(f"{failures} failure(s)" if failures else "all cases pass")
sys.exit(1 if failures else 0)
