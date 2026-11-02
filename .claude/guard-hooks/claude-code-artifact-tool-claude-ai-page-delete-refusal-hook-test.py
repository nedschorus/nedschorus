#!/usr/bin/env python3
"""Tests for .claude/guard-hooks/claude-code-artifact-tool-claude-ai-page-delete-refusal-hook.py.

Each case drives main() with the JSON payload the harness sends, and one case
pipes a payload into the hook as a real process.

Run: python3 .claude/guard-hooks/claude-code-artifact-tool-claude-ai-page-delete-refusal-hook-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import contextlib
import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path

HOOK_SCRIPT = Path(__file__).with_name("claude-code-artifact-tool-claude-ai-page-delete-refusal-hook.py")
_spec = importlib.util.spec_from_file_location("artifact_delete_refusal", HOOK_SCRIPT)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)

PAGE_LINK = "https://claude.ai/artifact/7SNxQB3Q7vwr3ZLqSW1Mfk"

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def run_main(stdin_text):
    """Return (exit code, stdout) of main() on the given stdin."""
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        code = hook.main(stdin=io.StringIO(stdin_text))
    return code, stdout.getvalue().strip()


def refusal(tool_input, tool_name="Artifact"):
    """Return the deny reason the hook gives, None when it lets the call through."""
    code, text = run_main(json.dumps({"tool_name": tool_name, "tool_input": tool_input}))
    if code != 0:
        return f"<exit {code}>"
    if not text:
        return None
    output = json.loads(text)["hookSpecificOutput"]
    if output.get("hookEventName") != "PreToolUse" or output.get("permissionDecision") != "deny":
        return f"<unexpected output {text}>"
    return output.get("permissionDecisionReason")


reason = refusal({"action": "delete", "url": PAGE_LINK})
check("a delete is refused", reason is not None and reason.startswith(
    'REFUSED: an Artifact tool call with action "delete".'), reason)
check("the refusal names the page's link", reason is not None
      and f"give him its link, {PAGE_LINK}, and tell him" in reason, reason)
check("the refusal has its three lines", reason is not None and len(reason.splitlines()) == 3, reason)

for case_name, tool_input in [
        ("a delete with no url", {"action": "delete"}),
        ("a delete with an empty url", {"action": "delete", "url": "  "}),
        ("a delete with a url that is not text", {"action": "delete", "url": 7})]:
    reason = refusal(tool_input)
    check(f"{case_name} is refused, saying the call has no link", reason is not None
          and f"give him its link, {hook.NO_LINK_TEXT}, and tell him" in reason, reason)

for case_name, tool_input in [
        ("a publish with no action", {"file_path": "/tmp/page.html"}),
        ("an explicit publish", {"action": "publish", "file_path": "/tmp/page.html", "url": PAGE_LINK}),
        ("a read", {"action": "read", "url": PAGE_LINK}),
        ("a list", {"action": "list"}),
        ("an open", {"action": "open", "url": PAGE_LINK}),
        ("a tool_input that is not an object", "delete")]:
    check(f"{case_name} is let through", refusal(tool_input) is None, refusal(tool_input))

check("a delete by another tool is let through",
      refusal({"action": "delete", "url": PAGE_LINK}, tool_name="Bash") is None)

for case_name, stdin_text in [
        ("stdin that is not JSON", "not json {"),
        ("empty stdin", ""),
        ("a JSON payload that is not an object", "[1, 2]")]:
    code, text = run_main(stdin_text)
    check(f"{case_name} is let through with exit 0 and no output", code == 0 and text == "",
          f"exit {code}, output {text!r}")

process = subprocess.run(
    [sys.executable, str(HOOK_SCRIPT)],
    input=json.dumps({"tool_name": "Artifact", "tool_input": {"action": "delete", "url": PAGE_LINK}}),
    capture_output=True, text=True, timeout=30)
process_output = json.loads(process.stdout or "{}").get("hookSpecificOutput", {})
check("run as a process, a delete exits 0 with a deny",
      process.returncode == 0 and process_output.get("permissionDecision") == "deny",
      f"exit {process.returncode}, stdout {process.stdout!r}, stderr {process.stderr!r}")

if failures:
    print(f"\n{len(failures)} case(s) failed")
    sys.exit(1)
print("\nall cases passed")
