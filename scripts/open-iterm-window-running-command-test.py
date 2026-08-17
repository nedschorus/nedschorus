#!/usr/bin/env python3
"""Tests for open-iterm-window-running-command.

Every generation case runs with OPEN_ITERM_WINDOW_DRY_RUN=1, which prints the
AppleScript instead of executing it, and the remaining cases are argument-
validation failures — so no test ever opens a real window on the user's Mac.
The validation rules under test are the PR #82 review's F11: joining multiple
arguments must never silently change the command's word boundaries.

Run: python3 scripts/open-iterm-window-running-command-test.py
"""

import os
import subprocess
import sys
from pathlib import Path

OPENER_SCRIPT = Path(__file__).with_name("open-iterm-window-running-command")

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def run_opener(arguments, dry_run=True):
    environment = dict(os.environ)
    if dry_run:
        environment["OPEN_ITERM_WINDOW_DRY_RUN"] = "1"
    else:
        environment.pop("OPEN_ITERM_WINDOW_DRY_RUN", None)
    return subprocess.run(["sh", str(OPENER_SCRIPT), *arguments],
                          capture_output=True, text=True, env=environment)


result = run_opener([])
check("no arguments is a usage error",
      result.returncode == 2 and "usage:" in result.stderr, result.stderr)

result = run_opener(["ssh -t ned tmux attach -t gatekeeper"])
check("a single command string lands verbatim in the AppleScript",
      result.returncode == 0
      and 'create window with default profile command "ssh -t ned tmux attach -t gatekeeper"'
      in result.stdout,
      result.stdout or result.stderr)

result = run_opener(["ssh", "-t", "ned", "tmux", "attach"])
check("several simple arguments join with single spaces",
      result.returncode == 0
      and 'command "ssh -t ned tmux attach"' in result.stdout,
      result.stdout or result.stderr)

result = run_opener(['echo "a\\b"'])
check("double quotes and backslashes are escaped for the AppleScript string",
      result.returncode == 0
      and 'command "echo \\"a\\\\b\\""' in result.stdout,
      result.stdout or result.stderr)

result = run_opener(["tmux", "attach", "-t", "seat a"])
check("F11: multiple arguments where one contains a space are refused",
      result.returncode == 2 and "one quoted argument" in result.stderr,
      result.stderr)

result = run_opener(["echo", "don't"])
check("F11: multiple arguments where one contains a quote are refused",
      result.returncode == 2 and "one quoted argument" in result.stderr,
      result.stderr)

result = run_opener(["echo hi\necho bye"])
check("a raw newline in the command is refused (AppleScript cannot hold it)",
      result.returncode == 2 and "raw newline" in result.stderr, result.stderr)

result = run_opener(["tmux attach -t 'seat a'"])
check("a single argument may of course contain spaces and quotes",
      result.returncode == 0 and "seat a" in result.stdout,
      result.stdout or result.stderr)


print()
if failures:
    print(f"{len(failures)} case(s) failed")
    sys.exit(1)
print(f"all cases passed")
