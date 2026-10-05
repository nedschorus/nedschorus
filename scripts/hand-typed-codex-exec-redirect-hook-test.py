#!/usr/bin/env python3
"""Tests for scripts/hand-typed-codex-exec-redirect-hook.py.

Each case drives main() with the JSON payload the harness sends, and one case
pipes a payload into the hook as a real process.

Run: python3 scripts/hand-typed-codex-exec-redirect-hook-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import contextlib
import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path

HOOK_SCRIPT = Path(__file__).with_name("hand-typed-codex-exec-redirect-hook.py")
_spec = importlib.util.spec_from_file_location("codex_exec_redirect", HOOK_SCRIPT)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def refusal(command, tool_name="Bash"):
    payload = {"tool_name": tool_name, "tool_input": {"command": command}}
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        code = hook.main(stdin=io.StringIO(json.dumps(payload)))
    if code != 0:
        return f"<exit {code}>"
    text = stdout.getvalue().strip()
    if not text:
        return None
    output = json.loads(text)["hookSpecificOutput"]
    return output["permissionDecisionReason"] if output["permissionDecision"] == "deny" else None


REFUSED = {
    "a bare codex exec with an argument prompt": 'codex exec -C /tmp/x "do the task"',
    "codex exec in the background": 'codex exec -s workspace-write -o r.md "task" &',
    "codex exec in a backgrounded subshell": '( codex exec -C x -o y "task"; echo done ) &',
    "codex exec with stdin closed": 'codex exec -C x "task" < /dev/null',
    "codex exec reading its prompt from a pipe": 'cat brief.md | codex exec -',
    "the exec alias e": 'codex e "task"',
    "codex exec by full path": '/opt/homebrew/bin/codex exec "task"',
    "codex exec after a global option with a value": 'codex -c model="x" exec "task"',
    "codex exec behind env, nohup and timeout": 'env A=1 nohup timeout 600 codex exec "task"',
    "codex exec after an environment assignment": 'CODEX_HOME=/tmp/h codex exec "task"',
    "codex exec after &&": 'cd /tmp && codex exec "task"',
    "codex exec inside a command substitution": 'out=$(codex exec "task")',
    "codex exec inside bash -c": "bash -c 'codex exec -C x \"task\"'",
    "codex exec inside an ssh command": "ssh nedlern@ned-box 'cd ~/x && codex exec \"task\"'",
    "codex exec reading a heredoc": 'codex exec - <<EOF\ndo the task\nEOF',
}

ALLOWED = {
    "the new program": "python3 scripts/run-codex-task-from-brief.py -C . --brief b.md -o r.md",
    "codex --version": "codex --version",
    "codex exec --help": "codex exec --help",
    "codex login status": "codex login status",
    "a grep for the words codex exec": 'grep -rn "codex exec" docs/',
    "an echo that mentions codex exec": "echo 'never type codex exec by hand'",
    "a heredoc body that mentions codex exec": "cat > notes.md <<'EOF'\ncodex exec \"x\"\nEOF",
    "a commit message that mentions codex exec": 'git commit -m "Refuse a hand-typed codex exec"',
    "ps listing codex processes": "ps -axo pid,command | grep codex",
}

for name, command in REFUSED.items():
    got = refusal(command)
    check(f"refused: {name}", got == hook.REFUSAL, f"got {got!r}")

for name, command in ALLOWED.items():
    got = refusal(command)
    check(f"allowed: {name}", got is None, f"got {got!r}")

check("a tool other than Bash is ignored",
      refusal('codex exec "task"', tool_name="Read") is None)

check("the refusal gives the program's usage line",
      hook.USAGE_LINE in hook.REFUSAL
      and "scripts/run-codex-task-from-brief.py" in hook.USAGE_LINE)

program_help = subprocess.run(
    [sys.executable, str(HOOK_SCRIPT.with_name("run-codex-task-from-brief.py")), "--help"],
    capture_output=True, text=True, check=False)
for flag in ("-C", "--brief", "-o", "--sandbox", "-m", "--effort", "--deadline-minutes"):
    check(f"the usage line's flag {flag} is one the program accepts",
          flag in hook.USAGE_LINE and flag in program_help.stdout,
          program_help.stdout[:200])

process = subprocess.run(
    [sys.executable, str(HOOK_SCRIPT)],
    input=json.dumps({"tool_name": "Bash",
                      "tool_input": {"command": 'codex exec "task" &'}}),
    capture_output=True, text=True, check=False)
decision = json.loads(process.stdout)["hookSpecificOutput"] if process.stdout.strip() else {}
check("as a process, the hook denies a hand-typed codex exec and exits 0",
      process.returncode == 0 and decision.get("permissionDecision") == "deny",
      f"exit {process.returncode}, stdout {process.stdout!r}")

process = subprocess.run(
    [sys.executable, str(HOOK_SCRIPT)],
    input=json.dumps({"tool_name": "Bash", "tool_input": {"command": "git status"}}),
    capture_output=True, text=True, check=False)
check("as a process, the hook allows an ordinary command silently",
      process.returncode == 0 and not process.stdout.strip(),
      f"exit {process.returncode}, stdout {process.stdout!r}")

if failures:
    print(f"{len(failures)} case(s) failed: " + ", ".join(failures))
    sys.exit(1)
print("all cases passed")
