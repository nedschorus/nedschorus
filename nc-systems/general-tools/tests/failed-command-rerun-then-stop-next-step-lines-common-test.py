#!/usr/bin/env python3
"""Tests for nc-systems/general-tools/failed-command-rerun-then-stop-next-step-lines-common.py.

The programs that print these lines reach this module through their own
suites. These cases pin the wording itself, word for word, so a change to it
is a change a reviewer sees here.

Run: python3 nc-systems/general-tools/tests/failed-command-rerun-then-stop-next-step-lines-common-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import importlib.util
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location(
    "failed_command_rerun_then_stop_next_step_lines_common",
    REPOSITORY_ROOT / "nc-systems" / "general-tools"
    / "failed-command-rerun-then-stop-next-step-lines-common.py")
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


SUBAGENT = "A subagent tells the agent that dispatched it, not the user."

lines = next_step_lines.git_failure_next_step_lines("`p --x`", "p").splitlines()
check("a git failure in a program the agent ran gets four lines, ending in when to stop, "
      "whose output to report, and that a subagent only reports to someone else",
      lines == [
          "If git's error names a lock file, such as .git/index.lock, wait one minute, "
          "then run `p --x`; do not delete the lock file yourself.",
          "If git's error names a branch, commit or path that does not exist, and you gave "
          "that name to p, correct it in your command, then run the corrected command.",
          "In any other case, run `p --x` once more.",
          "If `p --x` fails again, stop, and tell the user what p printed and what the rerun "
          f"printed, git's error included. {SUBAGENT}"], lines)

lines = next_step_lines.git_failure_next_step_lines(
    "`git -C d status`", "the sync", agent_gave_the_names=False).splitlines()
check("when the agent gave the program no names, the misspelt-name line is left out",
      len(lines) == 3 and not any("you gave that name" in line for line in lines)
      and lines[-1].startswith("If `git -C d status` fails again, stop,"), lines)

line = next_step_lines.rerun_then_stop_line(
    "`r`", "q", failure="prints NOT CHECKED again", error_included=None)
check("a stop line for a failure with no error text names the failure it waits for and "
      "claims no error was included",
      line == "If `r` prints NOT CHECKED again, stop, and tell the user what q printed and "
              f"what the rerun printed. {SUBAGENT}", line)

line = next_step_lines.same_failure_again_line("at your next Edit", "h.py")
check("a hook's line says its check runs again by itself and to report both times' output",
      line == "If the same failure is reported again at your next Edit, tell the user what "
              f"h.py printed both times, git's error included. {SUBAGENT}", line)

print(f"{failures} failure(s)" if failures else "all cases pass")
sys.exit(1 if failures else 0)
