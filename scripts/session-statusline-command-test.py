#!/usr/bin/env python3
"""Tests for the status line (session-statusline-command.py).

Field set and format are the user's, walked 2026-08-08; see the script's
module docstring for what each field is and why the rest were dropped.

Run: python3 scripts/session-statusline-command-test.py
"""

import importlib.util
import json
import os
import sys
import tempfile
import time
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
# resets_at is EPOCH SECONDS, a number — the shape the harness actually
# sends. This fixture used an ISO string until 2026-08-15, which is why the
# suite stayed green through a bug that blanked both countdowns in every
# real session: the tested shape was one the harness never produces.
FIVE_HOURS_AHEAD = int(time.time()) + 5 * 3600
THREE_DAYS_AHEAD = int(time.time()) + 3 * 86400

quota_payload = dict(payload)
quota_payload["rate_limits"] = {
    "five_hour": {"used_percentage": 23.0, "resets_at": FIVE_HOURS_AHEAD},
    "seven_day": {"used_percentage": 11.0, "resets_at": THREE_DAYS_AHEAD},
}
quota_line = statusline.status_line_text(quota_payload)
check("five-hour window renders remaining, not used", "77%" in quota_line, quota_line)
check("seven-day window renders remaining, not used", "89%" in quota_line, quota_line)
check("an epoch-seconds reset renders its countdown", "4h" in quota_line, quota_line)
check("the seven-day countdown renders too", "2d" in quota_line, quota_line)

check("a quota reset in the past reads as now", statusline.time_until("2000-01-01T00:00:00Z") == "now")
check("an unparseable quota reset is dropped", statusline.time_until("not-a-timestamp") == "")
check("an epoch number in the past reads as now", statusline.time_until(int(time.time()) - 60) == "now")
check("an ISO string still parses", statusline.time_until("2099-01-01T00:00:00Z") != "")
check("True is not read as epoch 1", statusline.time_until(True) == "")
check("an absurd epoch is dropped, not raised", statusline.time_until(1e18) == "")
check("a numeric STRING is dropped, never read as an epoch",
      statusline.time_until("1786953600") == "")

# agent.name is absent for an ordinary session and must not print an
# empty separator-bounded segment when it is.
check("no agent segment without an agent name", statusline.agent_segment(payload) == "")

# The freshness suffix displays the catch-up hook's stamp and never fetches.
with tempfile.TemporaryDirectory() as freshness_directory:
    fake_checkout = Path(freshness_directory)
    (fake_checkout / ".git").mkdir()
    (fake_checkout / ".git" / "HEAD").write_text("ref: refs/heads/seat\n", encoding="utf-8")
    check("no stamp, no freshness suffix",
          statusline.freshness_suffix(str(fake_checkout)) == "")
    stamp_path = fake_checkout / ".git" / "checkout-freshness-stamp.json"
    stamp_path.write_text('{"behind": 3, "fetch_ok": true}', encoding="utf-8")
    check("behind renders as a count",
          statusline.freshness_suffix(str(fake_checkout)) == "⇣3",
          statusline.freshness_suffix(str(fake_checkout)))
    stamp_path.write_text('{"behind": 3, "fetch_ok": false}', encoding="utf-8")
    check("a failed fetch marks the count as doubtful",
          statusline.freshness_suffix(str(fake_checkout)) == "⇣3?",
          statusline.freshness_suffix(str(fake_checkout)))
    stamp_path.write_text('{"behind": 0, "fetch_ok": true}', encoding="utf-8")
    check("a current checkout shows nothing",
          statusline.freshness_suffix(str(fake_checkout)) == "")
    stamp_path.write_text('{"behind": 0, "fetch_ok": false}', encoding="utf-8")
    check("current-but-unfetched shows doubt, not silence",
          statusline.freshness_suffix(str(fake_checkout)) == "⇣?",
          statusline.freshness_suffix(str(fake_checkout)))
    stamp_path.write_text('{"behind": null, "fetch_ok": true}', encoding="utf-8")
    check("an unknowable count with a good fetch shows nothing",
          statusline.freshness_suffix(str(fake_checkout)) == "")
check(
    "the agent name appears when the session has one",
    "choirmaster" in statusline.status_line_text({**payload, "agent": {"name": "choirmaster"}}),
)

# An empty payload no longer renders empty: the host is derived locally,
# not from the payload, so the line degrades to it rather than vanishing.
empty_line = statusline.status_line_text({})
check("status line survives an empty payload", os.uname().nodename.split(".")[0] in empty_line, empty_line)
check("an empty payload adds no stray separators", statusline.SEPARATOR not in empty_line, empty_line)

# Every case above asserts what this script BELIEVES the harness sends.
# That belief was wrong once and the suite could not tell: resets_at is epoch
# seconds, the fixture sent an ISO string, and both countdowns were blank in
# every real session while the tests ran green (2026-08-15). The same wrong
# belief wrote the code and the fixture, so no fixture can catch that class.
# The canary asserts against a payload the harness actually delivered.
#
# Field TYPES, not values: values change on every refresh, types are the
# contract. Absence is not failure -- rate_limits is documented as present
# only for subscribers after a first API response, and agent.name only for a
# session launched with --agent. A field that is present with the wrong type
# IS failure, and is exactly the drift that blanked the countdowns.
PAYLOAD_CONTRACT = [
    ("workspace.current_dir", str),
    ("model.display_name", str),
    ("effort.level", str),
    ("agent.name", str),
    ("context_window.remaining_percentage", (int, float)),
    ("rate_limits.five_hour.used_percentage", (int, float)),
    ("rate_limits.five_hour.resets_at", (int, float)),
    ("rate_limits.seven_day.used_percentage", (int, float)),
    ("rate_limits.seven_day.resets_at", (int, float)),
]


def dotted_get(payload, dotted_path):
    """Return (found, value) for a dotted path, without raising on a gap."""
    current = payload
    for piece in dotted_path.split("."):
        if not isinstance(current, dict) or piece not in current:
            return False, None
        current = current[piece]
    return True, current


def run_payload_contract_canary():
    capture_path = os.environ.get(statusline.PAYLOAD_CAPTURE_VARIABLE)
    if not capture_path:
        check(
            f"canary: {statusline.PAYLOAD_CAPTURE_VARIABLE} names a captured payload",
            False,
            "unset. In a live session: export "
            f"{statusline.PAYLOAD_CAPTURE_VARIABLE}=/tmp/statusline-payload.json, let the "
            "line refresh once, then rerun with --canary and the same variable set.",
        )
        return
    path = Path(capture_path)
    if not path.is_file():
        check("canary: the captured payload file exists", False,
              f"{path} — the variable is set but no session has written a payload there yet")
        return
    try:
        captured = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        check("canary: the captured payload is readable JSON", False, f"{path}: {error}")
        return

    check("canary: the captured payload is an object", isinstance(captured, dict), type(captured).__name__)
    present = 0
    for dotted_path, expected in PAYLOAD_CONTRACT:
        found, value = dotted_get(captured, dotted_path)
        if not found:
            print(f"       {dotted_path}: absent (allowed)")
            continue
        present += 1
        # bool is an int in Python; a bool here would be drift, not a number.
        wrong = isinstance(value, bool) or not isinstance(value, expected)
        names = expected.__name__ if isinstance(expected, type) else "/".join(t.__name__ for t in expected)
        check(f"canary: {dotted_path} is {names}", not wrong,
              f"got {type(value).__name__} = {value!r} — the harness changed shape")
    check("canary: the captured payload carried at least one contract field", present > 0,
          "every field absent — this may not be a status line payload")


if "--canary" in sys.argv:
    print("\n-- payload contract canary (against a captured live payload) --")
    run_payload_contract_canary()
else:
    print("\n(skipped the payload contract canary; pass --canary to run it)")

print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
