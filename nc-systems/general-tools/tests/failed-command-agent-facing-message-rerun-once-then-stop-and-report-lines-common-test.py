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


SUBAGENT = "A subagent reports to the agent that dispatched it, not to the user."

lines = next_step_lines.git_failure_next_step_lines(
    "`p --x`", "p", failure_again='prints "p: could not" again',
    takes_a_branch_commit_or_path=True).splitlines()
check("a git failure in a program that takes names gets four lines, ending in the failure "
      "the second run would print, both runs' lines word for word, and whom a subagent tells",
      lines == [
          "If git's error names a lock file, such as .git/index.lock, wait one minute, "
          "then run `p --x`; do not delete the lock file yourself.",
          "If git's error names a branch, commit or path that does not exist, and you gave "
          "that name to p, correct it in your command, then run the corrected command.",
          "If none of the cases above applies, run `p --x` once more, unchanged.",
          'If the run you made by following a line above prints "p: could not" again, stop, and tell the user, word for '
          "word, the lines p printed the first time and the lines that second run printed. "
          + SUBAGENT], lines)

lines = next_step_lines.git_failure_next_step_lines(
    "`git -C d status`", "the sync", failure_again="prints an error again",
    takes_a_branch_commit_or_path=False, read_by_a_subagent=False).splitlines()
check("a program that takes no names leaves out the misspelt-name line, and a line no "
      "subagent reads leaves out the subagent sentence",
      len(lines) == 3 and not any("you gave that name" in line for line in lines)
      and lines[-1] == "If the run you made by following a line above prints an error again, stop, and tell the user, "
                       "word for word, the lines the sync printed the first time and the "
                       "lines that second run printed.", lines)

line = next_step_lines.agent_instruction_if_rerun_fails_too_stop_and_report_both_runs_line(
    "prints an error again", "the sync", read_by_a_subagent=False,
    also_not="take the next step below")
check("a stop that holds back the work that follows says so in the stop itself",
      line == "If the run you made by following a line above prints an error again, stop, do "
              "not take the next step below, and tell the user, word for word, the lines the "
              "sync printed the first time and the lines that second run printed.", line)

line = next_step_lines.hook_agent_instruction_if_git_failure_recurs_tell_user_both_outputs_line(
    "at your next Edit", "h.py")
check("a hook's line says to keep this message, that any git failure counts, and to tell "
      "both messages word for word",
      line == "Keep this message: if h.py reports a git failure again at your next Edit, "
              "whether this error or another, tell the user both messages, word for word. "
              + SUBAGENT, line)

print(f"{failures} failure(s)" if failures else "all cases pass")
sys.exit(1 if failures else 0)
