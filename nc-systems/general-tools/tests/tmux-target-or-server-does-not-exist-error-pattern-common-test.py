#!/usr/bin/env python3
"""Tests for nc-systems/general-tools/tmux-target-or-server-does-not-exist-error-pattern-common.py.

The synthetic-keystroke guard and crash recovery reach this module through
their own suites. These cases pin the pattern directly: each "does not exist"
answer tmux 3.6 gives counts as absent, and each other failure, such as a
client and server of different versions, does not.

Run: python3 nc-systems/general-tools/tests/tmux-target-or-server-does-not-exist-error-pattern-common-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import importlib.util
import os
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = Path(os.environ.get(
    "TMUX_TARGET_OR_SERVER_DOES_NOT_EXIST_ERROR_PATTERN_COMMON_MODULE_PATH",
    REPOSITORY_ROOT / "nc-systems" / "general-tools"
    / "tmux-target-or-server-does-not-exist-error-pattern-common.py"))
_spec = importlib.util.spec_from_file_location(
    "tmux_target_or_server_does_not_exist_error_pattern_common", MODULE_PATH)
pattern = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pattern)
says_absent = pattern.tmux_error_text_says_target_or_server_does_not_exist

failures = 0


def check(name, condition, detail=None):
    global failures
    if condition:
        print(f"PASS  {name}")
    else:
        failures += 1
        print(f"FAIL  {name}: {detail!r}")


# Each line is what tmux 3.6 printed on ned-box for that case.
ABSENT_ANSWERS = {
    "another session holds the server": "can't find session: seat-a",
    "the window is gone": "can't find window: 3",
    "the pane is gone": "can't find pane: %7",
    "the server holds no session (has-session)": "no current target",
    "the socket refuses": "no server running on /tmp/tmux-1000/seat-a",
    "no socket file": "error connecting to /tmp/tmux-1000/seat-a (No such file or directory)",
}
for case, text in ABSENT_ANSWERS.items():
    check(f"absent: {case}", says_absent(text) is True, text)
    check(f"absent inside a longer stderr: {case}",
          says_absent(f"tmux: {text}\n") is True, text)

OTHER_FAILURES = {
    "a client and server of different versions":
        "server version is too old for client",
    "permission denied on the socket":
        "error connecting to /tmp/tmux-1000/seat-a (Permission denied)",
    "an unknown command": "unknown command: hsa-session",
    "a bad format": "invalid format",
}
for case, text in OTHER_FAILURES.items():
    check(f"not absent: {case}", says_absent(text) is False, text)

check("empty error text is not an absent answer", says_absent("") is False)
check("no error text at all (None) is not an absent answer and does not raise",
      says_absent(None) is False)
check("the answer is a real bool, not a match object",
      type(says_absent("no current target")) is bool)

print(f"{failures} failure(s)" if failures else "all cases pass")
sys.exit(1 if failures else 0)
