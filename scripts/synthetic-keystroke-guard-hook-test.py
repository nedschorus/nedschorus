#!/usr/bin/env python3
"""Tests for the synthetic-keystroke guard (synthetic-keystroke-guard-hook.py).

Decision cases drive main() in-process with a stubbed tmux probe, so no test
ever creates, attaches, or types at a real tmux session — the guard exists
because doing that carelessly is dangerous. Parse-only cases (deny on
`write text`, pass-through on non-Bash payloads) also run end-to-end as a
subprocess, exactly as the harness invokes the hook.

Run: python3 scripts/synthetic-keystroke-guard-hook-test.py
"""

import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path

HOOK_SCRIPT = Path(__file__).with_name("synthetic-keystroke-guard-hook.py")

_spec = importlib.util.spec_from_file_location("synthetic_keystroke_guard", HOOK_SCRIPT)
guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guard)

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def run_hook_subprocess(payload):
    return subprocess.run(
        [sys.executable, str(HOOK_SCRIPT)],
        input=json.dumps(payload), capture_output=True, text=True, check=False,
    )


class StubRunner:
    """Stands in for subprocess.run inside the guard's tmux probe."""

    def __init__(self, stdout="", stderr="", returncode=0):
        self.stdout, self.stderr, self.returncode = stdout, stderr, returncode
        self.calls = []

    def __call__(self, argv, **_kwargs):
        self.calls.append(argv)
        return subprocess.CompletedProcess(argv, self.returncode, self.stdout, self.stderr)


def decide(command, runner):
    """Run main() in-process; return the deny reason, or None when allowed."""
    payload = {"tool_name": "Bash", "tool_input": {"command": command}}
    captured = io.StringIO()
    original_stdout = sys.stdout
    sys.stdout = captured
    try:
        guard.main(stdin=io.StringIO(json.dumps(payload)), runner=runner)
    finally:
        sys.stdout = original_stdout
    output = captured.getvalue().strip()
    if not output:
        return None
    return json.loads(output)["hookSpecificOutput"]["permissionDecisionReason"]


# --- write text: always denied, and only with osascript alongside ---

result = run_hook_subprocess({"tool_name": "Bash", "tool_input": {
    "command": 'osascript -e \'tell app "iTerm" to tell current session of front window to write text "ls"\''}})
check("osascript write text is denied end-to-end",
      '"deny"' in result.stdout and "open-iterm-window-running-command" in result.stdout,
      result.stdout or result.stderr)

check("write text without osascript passes (a commit message is not a keystroke)",
      decide('git commit -m "docs: how to write text for humans"', StubRunner()) is None)

check("invoking the opener script passes (no osascript, no write text)",
      decide('scripts/open-iterm-window-running-command "ssh -t ned tmux attach -t gatekeeper"',
             StubRunner()) is None)

result = run_hook_subprocess({"tool_name": "Read", "tool_input": {"file_path": "/tmp/x"}})
check("non-Bash payloads pass untouched", result.stdout.strip() == "", result.stdout)

result = run_hook_subprocess({"tool_name": "Bash", "tool_input": {"command": "ls -la"}})
check("an innocuous command passes end-to-end", result.stdout.strip() == "", result.stdout)


commit_with_prose = (
    "git add x && git commit -F - <<'EOF'\n"
    "the guard denies osascript together with write text in one command\n"
    "and tmux send-keys -t seat-a at attached sessions\n"
    "EOF\n"
    "git push"
)
check("a commit message heredoc mentioning the banned forms passes (data, not keystrokes)",
      decide(commit_with_prose, StubRunner()) is None)

heredoc_osascript = (
    "osascript <<'EOF'\n"
    'tell application "iTerm" to tell current session of front window to write text "ls"\n'
    "EOF"
)
reason = decide(heredoc_osascript, StubRunner())
check("osascript consuming a heredoc with write text is denied (the original incident's form)",
      reason is not None and "write text" in reason, reason)


# --- tmux keystroke writes: ruled by the target's attachment ---

runner = StubRunner(stdout="0\n")
check("send-keys to a verified-detached session is allowed",
      decide("tmux send-keys -t seat-a Enter", runner) is None)
check("the probe asked tmux for session_attached",
      any("#{session_attached}" in argument for argument in runner.calls[0]),
      runner.calls)

reason = decide("tmux paste-buffer -t seat-a", StubRunner(stdout="1\n"))
check("paste-buffer at an attached session is denied",
      reason is not None and "attached client" in reason, reason)
check("the attached denial teaches the safe forms",
      reason is not None and "open-iterm-window-running-command" in reason and "#37" in reason,
      reason)

runner = StubRunner(stdout="0\n")
check("ssh-wrapped injection to a detached box session is allowed",
      decide("ssh ned 'tmux paste-buffer -t gatekeeper; tmux send-keys -t gatekeeper Enter'",
             runner) is None)
check("the probe for an ssh-wrapped command runs over ssh to that host",
      runner.calls and runner.calls[0][0] == "ssh" and "ned" in runner.calls[0],
      runner.calls)

reason = decide("ssh ned 'tmux send-keys -t gatekeeper Enter'", StubRunner(stdout="1\n"))
check("ssh-wrapped injection to an attached box session is denied",
      reason is not None and "attached client" in reason, reason)

check("a target tmux does not know is allowed (keystrokes land nowhere)",
      decide("tmux send-keys -t no-such-seat Enter",
             StubRunner(stderr="can't find pane: no-such-seat", returncode=1)) is None)

reason = decide("ssh ned 'tmux send-keys -t gatekeeper Enter'",
                StubRunner(stderr="ssh: connect to host ned: Operation timed out", returncode=255))
check("an unverifiable target is denied, fail-closed",
      reason is not None and "could not verify" in reason, reason)
check("the unverifiable denial carries the probe recipe and the override",
      reason is not None and "session_attached" in reason and "CLAUDE_VERIFIED_DETACHED=1" in reason,
      reason)

check("the CLAUDE_VERIFIED_DETACHED=1 override skips the probe",
      decide("CLAUDE_VERIFIED_DETACHED=1 ssh ned 'tmux send-keys -t gatekeeper Enter'",
             StubRunner(stderr="unreachable", returncode=255)) is None)

reason = decide("tmux paste-buffer", StubRunner())
check("keystrokes with no -t target are denied",
      reason is not None and "no -t target" in reason, reason)

check("tmux without keystroke verbs passes (capture-pane is reading, not typing)",
      decide("ssh ned 'tmux capture-pane -p -t gatekeeper'", StubRunner()) is None)

check("tmux lifecycle with a command argument passes (new-session is not typing)",
      decide('tmux new-session -d -s seat-b "claude --resume abc"', StubRunner()) is None)


# --- the ssh-host extractor ---

check("ssh host found past value-taking options",
      guard.extract_ssh_host("ssh -o ConnectTimeout=5 -t ned 'tmux ls'") == "ned")
check("no ssh means no host", guard.extract_ssh_host("tmux ls") is None)


print()
if failures:
    print(f"{len(failures)} case(s) failed")
    sys.exit(1)
print(f"all cases passed")
