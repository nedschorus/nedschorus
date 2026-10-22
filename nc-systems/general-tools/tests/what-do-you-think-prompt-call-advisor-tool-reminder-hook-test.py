#!/usr/bin/env python3
"""Tests for nc-systems/general-tools/what-do-you-think-prompt-call-advisor-tool-reminder-hook.py.

Run: python3 nc-systems/general-tools/tests/what-do-you-think-prompt-call-advisor-tool-reminder-hook-test.py
Prints one line per case and exits non-zero if any case fails. Every case runs
the hook as Claude Code does, as a subprocess reading a payload on stdin.
"""

import json
import subprocess
import sys
from pathlib import Path

HOOK_PATH = Path(__file__).resolve().parents[1] / "what-do-you-think-prompt-call-advisor-tool-reminder-hook.py"

failures = []


def check(case_name, condition, detail=""):
    print(("ok   " if condition else "FAIL ") + case_name + ("" if condition else f": {detail}"))
    if not condition:
        failures.append(case_name)


def run_hook(stdin_text):
    return subprocess.run([sys.executable, str(HOOK_PATH)], input=stdin_text,
                          capture_output=True, text=True, timeout=30)


def advisor_request_in(result):
    try:
        output = json.loads(result.stdout)["hookSpecificOutput"]
    except (ValueError, KeyError, TypeError):
        return False
    return (output.get("hookEventName") == "UserPromptSubmit"
            and "call the advisor tool" in output.get("additionalContext", ""))


for prompt in ("What do you think?", "item 7: WHAT DO YOU THINK", "so what\ndo  you think about it"):
    result = run_hook(json.dumps({"prompt": prompt}))
    check(f"the phrase asks for the advisor: {prompt!r}",
          result.returncode == 0 and advisor_request_in(result) and not result.stderr,
          f"exit {result.returncode}, stdout {result.stdout!r}, stderr {result.stderr!r}")

for prompt in ("A", "what do you want", "I think you should"):
    result = run_hook(json.dumps({"prompt": prompt}))
    check(f"no phrase prints nothing: {prompt!r}",
          result.returncode == 0 and result.stdout == "" and result.stderr == "",
          f"exit {result.returncode}, stdout {result.stdout!r}, stderr {result.stderr!r}")

for stdin_text, case_name in (("not json", "input that is not JSON"),
                              ("[]", "a JSON value that is not an object"),
                              (json.dumps({"session_id": "x"}), "an object with no prompt"),
                              (json.dumps({"prompt": 7}), "a prompt that is not a string")):
    result = run_hook(stdin_text)
    check(f"{case_name} is reported as a non-blocking error",
          result.returncode == 1 and result.stdout == ""
          and result.stderr.startswith("what-do-you-think-prompt-call-advisor-tool-reminder-hook: ")
          and "call the advisor tool before you answer" in result.stderr,
          f"exit {result.returncode}, stdout {result.stdout!r}, stderr {result.stderr!r}")

if failures:
    print(f"\n{len(failures)} case(s) failed")
    sys.exit(1)
print("\nall cases passed")
