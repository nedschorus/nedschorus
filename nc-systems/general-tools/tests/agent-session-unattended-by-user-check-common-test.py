#!/usr/bin/env python3
"""Tests for nc-systems/general-tools/agent-session-unattended-by-user-check-common.py.

Run: python3 nc-systems/general-tools/tests/agent-session-unattended-by-user-check-common-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import importlib.util
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]

_spec = importlib.util.spec_from_file_location(
    "agent_session_unattended_by_user_check_common",
    REPOSITORY_ROOT / "nc-systems" / "general-tools" / "agent-session-unattended-by-user-check-common.py")
attendance_check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(attendance_check)

failures = 0


def check(name, condition, detail=""):
    global failures
    print(("PASS " if condition else "FAIL ") + name + ("" if condition else f": {detail!r}"))
    if not condition:
        failures += 1


# The variable names are written out here on purpose, as the oracle the module is checked against.
for name, environment, expected in (
        ("nothing set: attended", {}, False),
        ("CLAUDE_CODE_SESSION_ATTENDED=1: attended", {"CLAUDE_CODE_SESSION_ATTENDED": "1"}, False),
        ("CLAUDE_CODE_SESSION_ATTENDED=0: no user", {"CLAUDE_CODE_SESSION_ATTENDED": "0"}, True),
        ("CLAUDE_CODE_SESSION_ATTENDED empty: attended", {"CLAUDE_CODE_SESSION_ATTENDED": ""}, False),
        ("caller owns the session: no user",
         {"NEDSCHORUS_SESSION_REINCARNATION_OWNED_BY_CALLER": "scripts/ghi-guide-agent-ask.py"}, True),
        ("caller variable empty: attended", {"NEDSCHORUS_SESSION_REINCARNATION_OWNED_BY_CALLER": ""}, False),
        ("caller owns it though attended=1: no user",
         {"NEDSCHORUS_SESSION_REINCARNATION_OWNED_BY_CALLER": "1", "CLAUDE_CODE_SESSION_ATTENDED": "1"}, True)):
    result = attendance_check.agent_session_unattended_by_user(environment)
    check(name, result is expected, result)

original = {"CLAUDE_CODE_SESSION_ATTENDED": "0", "NEDSCHORUS_SESSION_REINCARNATION_OWNED_BY_CALLER": "1",
            "PATH": "/usr/bin"}
stripped = attendance_check.environment_without_agent_session_attendance_variables(original)
check("the copy keeps every other variable and drops both", stripped == {"PATH": "/usr/bin"}, stripped)
check("the mapping given is left unchanged", len(original) == 3, original)

print()
if failures:
    print(f"{failures} case(s) failed")
    sys.exit(1)
print("all cases passed")
