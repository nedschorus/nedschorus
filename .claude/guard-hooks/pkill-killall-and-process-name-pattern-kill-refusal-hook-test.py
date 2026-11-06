#!/usr/bin/env python3
"""Tests for .claude/guard-hooks/pkill-killall-and-process-name-pattern-kill-refusal-hook.py.

Each case drives main() with the JSON payload the harness sends, and two cases
pipe a payload into the hook as a real process.

Run: python3 .claude/guard-hooks/pkill-killall-and-process-name-pattern-kill-refusal-hook-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import contextlib
import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path

HOOK_SCRIPT = Path(__file__).with_name("pkill-killall-and-process-name-pattern-kill-refusal-hook.py")
_spec = importlib.util.spec_from_file_location("pkill_pattern_kill_refusal", HOOK_SCRIPT)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def hook_output(payload_text):
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        code = hook.main(stdin=io.StringIO(payload_text))
    return code, stdout.getvalue().strip()


def refusal(command, tool_name="Bash"):
    code, text = hook_output(json.dumps({"tool_name": tool_name, "tool_input": {"command": command}}))
    if code != 0:
        return f"<exit {code}>"
    if not text:
        return None
    output = json.loads(text)["hookSpecificOutput"]
    return output.get("permissionDecisionReason") if output.get("permissionDecision") == "deny" else None


REFUSED = [
    ("pkill -f", "pkill -f run-all-test-suites.py", "`pkill`"),
    ("pkill on a full command line, as in the reboot-test incident",
        "pkill -f 'python3 scripts/run-all-test-suites.py --only-suites-whose-recorded-inputs-changed-since origin/main'",
        "`pkill`"),
    ("pkill with a signal", "pkill -TERM -u nedlern python3", "`pkill`"),
    ("pkill by full path", "/usr/bin/pkill -f x", "`pkill`"),
    ("pkill behind sudo", "sudo pkill x", "`pkill`"),
    ("pkill behind timeout", "timeout 5 pkill -f x", "`pkill`"),
    ("pkill after &&", "cd /tmp && pkill -f x", "`pkill`"),
    ("pkill after ; with || true", "sleep 1; pkill -f x || true", "`pkill`"),
    ("pkill inside bash -c", "bash -c 'pkill -f x'", "`pkill`"),
    ("pkill inside an ssh remote command", "ssh nedlern@ned-box 'pkill -f run-all-test-suites.py'", "`pkill`"),
    ("pkill inside bash -c inside ssh", "ssh ned-box \"bash -c 'pkill x'\"", "`pkill`"),
    ("killall", "killall python3", "`killall`"),
    ("killall with a signal", "killall -9 node", "`killall`"),
    ("kill $(pgrep ...)", "kill $(pgrep -f run-all-test-suites.py)", "`kill $(pgrep ...)`"),
    ("kill with a signal and backticks", "kill -9 `pgrep x`", "`kill $(pgrep ...)`"),
    ("kill of a quoted pidof substitution", 'kill "$(pidof python3)"', "`kill $(pgrep ...)`"),
    ("kill of a ps | grep | awk substitution",
        "kill $(ps aux | grep run-all | awk '{print $2}')", "`kill $(pgrep ...)`"),
    ("kill of a pgrep | head substitution", "kill $(pgrep -f x | head -1)", "`kill $(pgrep ...)`"),
    ("kill -s TERM of pgrep, a signal other than 0", "kill -s TERM $(pgrep x)", "`kill $(pgrep ...)`"),
    ("kill of a nested substitution","kill $(echo $(pgrep x))", "`kill $(pgrep ...)`"),
    ("pgrep | xargs kill", "pgrep -f run-all-test-suites.py | xargs kill", "`pgrep ... | xargs kill`"),
    ("pgrep | xargs -r kill -9", "pgrep x | xargs -r kill -9", "`pgrep ... | xargs kill`"),
    ("pgrep | xargs -I{} kill {}", "pgrep x | xargs -I{} kill -TERM {}", "`pgrep ... | xargs kill`"),
    ("ps | grep | awk | xargs kill", "ps aux | grep foo | awk '{print $2}' | xargs kill",
        "`pgrep ... | xargs kill`"),
    ("pgrep in a subshell stage | xargs kill", "(pgrep x) | xargs kill", "`pgrep ... | xargs kill`"),
    ("pkill -P with a name pattern", "pkill -P 4321 -f worker", "`pkill`"),
    ("pkill -P with a name pattern after --", "pkill -P 4321 -- worker", "`pkill`"),
    ("pkill --signal and -P with a name pattern", "pkill --signal TERM -P 4321 worker", "`pkill`"),
    ("pkill -v -P, which signals every process but the children", "pkill -v -P 4321", "`pkill`"),
    ("pkill -P with another selector", "pkill -P 4321 -u nedlern", "`pkill`"),
    ("pkill -P with no process id", "pkill -P", "`pkill`"),
    ("pkill --signal with no value", "pkill -P 4321 --signal", "`pkill`"),
    ("pkill -P of a pgrep substitution", "pkill -P $(pgrep -f worker)", "`pkill`"),
    ("pkill --parent= of a pgrep substitution", "pkill --parent=$(pgrep -f worker)", "`pkill`"),
    ("pkill -P attached to a pgrep substitution", "pkill -P$(pgrep -f worker)", "`pkill`"),
    ("pkill -P run by xargs on pgrep's output", "pgrep -f worker | xargs pkill -P", "`pkill`"),
    ("pkill -P from a pgrep substitution with a pid listed too", "pkill -9 -P $(pgrep -f worker) -P 4321", "`pkill`"),
    ("pkill with only a signal and no -P", "pkill -TERM -f", "`pkill`"),
]

for name, command, what in REFUSED:
    got = refusal(command)
    check(f"refused: {name}", got is not None and what in got, f"got {got!r}")

ALLOWED = [
    ("plain kill of a pid", "kill 1234"),
    ("kill -9 of a pid", "kill -9 1234"),
    ("kill of a recorded pid variable", 'kill "$pid"'),
    ("kill of a pid read from a pid file", "kill $(cat /tmp/run.pid)"),
    ("kill of a background job", "kill %1"),
    ("xargs kill reading a pid file", "xargs kill < pids.txt"),
    ("pgrep alone, to look", "pgrep -fa run-all-test-suites.py"),
    ("pgrep, then an unrelated pipeline with xargs kill", "pgrep x; cat pids | xargs kill"),
    ("pgrep in a different pipeline from xargs kill", "pgrep x | wc -l && cat pids | xargs kill"),
    ("ps piped to grep", "ps aux | grep run-all"),
    ("echo of pkill", "echo pkill -f x"),
    ("grep for pkill", "grep -rn pkill scripts/"),
    ("pkill in a commit message", 'git commit -m "refuse pkill and killall"'),
    ("kill of a pid inside ssh", "ssh ned-box 'kill 1234'"),
    ("kill -0 of pgrep in a wait loop",
        'until ! kill -0 $(pgrep -f "git push -q -u origin HEAD" | head -1) 2>/dev/null; do sleep 5; done'),
    ("kill -s 0 of pgrep", "kill -s 0 $(pgrep x)"),
    ("kill -n 0 of pgrep", "kill -n 0 $(pgrep x)"),
    ("pgrep | xargs kill -0", "pgrep x | xargs kill -0"),
    ("pkill -P of a process id", "pkill -P 4321"),
    ("pkill -P of a recorded pid variable", 'pkill -P "$pid"'),
    ("pkill -P with the process id attached", "pkill -P4321"),
    ("pkill -TERM -P", "pkill -TERM -P 4321"),
    ("pkill -9 -P", "pkill -9 -P $p 2>/dev/null"),
    ("pkill -SIGUSR1 -P", "pkill -SIGUSR1 -P 4321"),
    ("pkill --signal TERM --parent", "pkill --signal TERM --parent 4321"),
    ("pkill --signal= and --parent=", "pkill --signal=KILL --parent=4321"),
    ("pkill -f -P, -f giving no pattern", "pkill -f -P 3989343 2>/dev/null"),
    ("pkill -P with --full and -n", "pkill --full -n -P 4321"),
    ("pkill -P inside an ssh remote command", "ssh nedlern@ned-box 'pkill -TERM -P 3718698 2>/dev/null; kill 3718698'"),
]

for name, command in ALLOWED:
    got = refusal(command)
    check(f"allowed: {name}", got is None, f"got {got!r}")

check("the refusal names the TaskStop tool and killing by the recorded process id",
      "TaskStop tool" in hook.REFUSAL_TEMPLATE and "process id you recorded" in hook.REFUSAL_TEMPLATE)

check("a tool other than Bash is ignored", refusal("pkill -f x", tool_name="Read") is None)

for name, payload_text in [("a payload that is not JSON", "not json {"),
                           ("a payload that is a JSON list", "[]"),
                           ("a command that is not a string",
                            json.dumps({"tool_name": "Bash", "tool_input": {"command": ["pkill", "x"]}})),
                           ("a payload with no tool_input", json.dumps({"tool_name": "Bash"}))]:
    code, text = hook_output(payload_text)
    check(f"{name} exits 0 and prints nothing", code == 0 and text == "", f"exit {code}, stdout {text!r}")

saved_simple_commands = hook.shell_reader.simple_commands


def parser_missing(_command):
    raise hook.shell_reader.ShellParserUnavailable("pip: no network")


hook.shell_reader.simple_commands = parser_missing
try:
    code, text = hook_output(json.dumps({"tool_name": "Bash", "tool_input": {"command": "pkill -f x"}}))
finally:
    hook.shell_reader.simple_commands = saved_simple_commands
output = json.loads(text or "{}").get("hookSpecificOutput", {})
check("without the shell parser the hook exits 0, lets the command through and says so",
      code == 0 and "permissionDecision" not in output
      and "pkill and name-pattern kill guard" in output.get("additionalContext", "")
      and "pip: no network" in output.get("additionalContext", ""), repr(output))

process = subprocess.run(
    [sys.executable, str(HOOK_SCRIPT)],
    input=json.dumps({"tool_name": "Bash", "tool_input": {"command": "pkill -f run-all-test-suites.py"}}),
    capture_output=True, text=True, check=False)
decision = json.loads(process.stdout)["hookSpecificOutput"] if process.stdout.strip() else {}
check("as a process, the hook denies pkill and exits 0",
      process.returncode == 0 and decision.get("permissionDecision") == "deny",
      f"exit {process.returncode}, stdout {process.stdout!r}")

process = subprocess.run(
    [sys.executable, str(HOOK_SCRIPT)],
    input=json.dumps({"tool_name": "Bash", "tool_input": {"command": "kill 1234"}}),
    capture_output=True, text=True, check=False)
check("as a process, the hook allows kill 1234 silently",
      process.returncode == 0 and not process.stdout.strip(),
      f"exit {process.returncode}, stdout {process.stdout!r}")

if failures:
    print(f"{len(failures)} case(s) failed: " + ", ".join(failures))
    sys.exit(1)
print("all cases passed")
