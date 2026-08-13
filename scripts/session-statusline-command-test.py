#!/usr/bin/env python3
"""Tests for the status line (session-statusline-command.py).

Field set and format are the user's, walked 2026-08-08; see the script's
module docstring for what each field is and why the rest were dropped.

Run: python3 scripts/session-statusline-command-test.py
"""

import importlib.util
import os
import sys
from pathlib import Path

STATUSLINE_SCRIPT = Path(__file__).with_name("session-statusline-command.py")

_statusline_spec = importlib.util.spec_from_file_location(
    "session_statusline_command", STATUSLINE_SCRIPT
)
statusline = importlib.util.module_from_spec(_statusline_spec)
_statusline_spec.loader.exec_module(statusline)

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


payload = {
    "session_id": "test-session",
    "workspace": {"current_dir": "/Users/el/Projects/nedschorus"},
    "model": {"display_name": "Fable 5"},
    "effort": {"level": "high"},
    "context_window": {"remaining_percentage": 62.4},
}
line = statusline.status_line_text(payload)
check("status line names the working directory", "nedschorus" in line, line)
check("status line names the host", os.uname().nodename.split(".")[0] in line, line)
check("status line names the model", "Fable 5" in line, line)
check("status line names the effort level", "high" in line, line)
check("status line reports context remaining, not used", "62%" in line, line)

# Quota windows: both percentages are REMAINING, so a payload reporting
# 23% used must render 77%. Getting this backwards is the likely bug, and
# it is invisible by inspection because both are plausible numbers.
quota_payload = dict(payload)
quota_payload["rate_limits"] = {
    "five_hour": {"used_percentage": 23.0, "resets_at": "2099-01-01T00:00:00Z"},
    "seven_day": {"used_percentage": 11.0, "resets_at": "2099-01-01T00:00:00Z"},
}
quota_line = statusline.status_line_text(quota_payload)
check("five-hour window renders remaining, not used", "77%" in quota_line, quota_line)
check("seven-day window renders remaining, not used", "89%" in quota_line, quota_line)

check("a quota reset in the past reads as now", statusline.time_until("2000-01-01T00:00:00Z") == "now")
check("an unparseable quota reset is dropped", statusline.time_until("not-a-timestamp") == "")

# agent.name is absent for an ordinary session and must not print an
# empty separator-bounded segment when it is.
check("no agent segment without an agent name", statusline.agent_segment(payload) == "")
check(
    "the agent name appears when the session has one",
    "choirmaster" in statusline.status_line_text({**payload, "agent": {"name": "choirmaster"}}),
)

# An empty payload no longer renders empty: the host is derived locally,
# not from the payload, so the line degrades to it rather than vanishing.
empty_line = statusline.status_line_text({})
check("status line survives an empty payload", os.uname().nodename.split(".")[0] in empty_line, empty_line)
check("an empty payload adds no stray separators", statusline.SEPARATOR not in empty_line, empty_line)

print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
