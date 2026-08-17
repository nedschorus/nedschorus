#!/usr/bin/env python3
"""Tests for the synthetic-keystroke guard (synthetic-keystroke-guard-hook.py).

Decision cases drive main() in-process with a stubbed tmux probe, so no test
ever creates, attaches, or types at a real tmux session — the guard exists
because doing that carelessly is dangerous. Parse-only cases (deny on
`write text`, pass-through on non-Bash payloads) also run end-to-end as a
subprocess, exactly as the harness invokes the hook.

Cases named F1..F11 are regressions from the 2026-08-17 PR #82 review round:
the original fixture modeled the guard's idea of commands, not the commands
the field writes. Each such case uses the review's command verbatim.

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
        self.call_kwargs = []

    def __call__(self, argv, **kwargs):
        self.calls.append(argv)
        self.call_kwargs.append(kwargs)
        return subprocess.CompletedProcess(argv, self.returncode, self.stdout, self.stderr)


class TickingClock:
    """A clock the test advances by hand."""

    def __init__(self, start=0.0):
        self.now = start

    def __call__(self):
        return self.now


class SlowProbeRunner(StubRunner):
    """A probe that costs wall time: advances the clock on every call."""

    def __init__(self, clock, cost_seconds, **kwargs):
        super().__init__(**kwargs)
        self.clock, self.cost_seconds = clock, cost_seconds

    def __call__(self, argv, **kwargs):
        self.clock.now += self.cost_seconds
        return super().__call__(argv, **kwargs)


class HangingProbeRunner(StubRunner):
    """A probe that hangs until its own timeout kills it."""

    def __init__(self, clock, **kwargs):
        super().__init__(**kwargs)
        self.clock = clock

    def __call__(self, argv, **kwargs):
        self.calls.append(argv)
        self.call_kwargs.append(kwargs)
        self.clock.now += kwargs.get("timeout", 0)
        raise subprocess.TimeoutExpired(argv, kwargs.get("timeout"))


def decide(command, runner, clock=None):
    """Run main() in-process; return the deny reason, or None when allowed."""
    payload = {"tool_name": "Bash", "tool_input": {"command": command}}
    captured = io.StringIO()
    original_stdout = sys.stdout
    sys.stdout = captured
    try:
        guard.main(stdin=io.StringIO(json.dumps(payload)), runner=runner,
                   clock=clock or (lambda: 0.0))
    finally:
        sys.stdout = original_stdout
    output = captured.getvalue().strip()
    if not output:
        return None
    return json.loads(output)["hookSpecificOutput"]["permissionDecisionReason"]


# --- AppleScript synthetic typing: always denied when osascript runs it ---

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

result = run_hook_subprocess({"tool_name": "Bash", "tool_input": {
    "command": 'osascript -e \'tell application "System Events" to keystroke "hello"\''}})
check("F10: System Events keystroke is denied end-to-end",
      '"deny"' in result.stdout and "open-iterm-window-running-command" in result.stdout,
      result.stdout or result.stderr)

reason = decide('osascript -e \'tell application "System Events" to key code 36\'', StubRunner())
check("F10: System Events key code is denied",
      reason is not None and "write text" in reason, reason)

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

# F6: banned words inside quoted arguments of other programs are prose.
runner = StubRunner()
check("F6: grep for the tmux form in quotes passes",
      decide('grep -rn "tmux send-keys" scripts/', runner) is None and not runner.calls,
      runner.calls)
check("F6: a commit -m mentioning osascript write text passes",
      decide('git commit -m "document the osascript write text rule"', StubRunner()) is None)
check("F6: a gh issue comment about the rule passes",
      decide('gh issue comment 27 --body "the guard denies osascript write text '
             'and tmux send-keys at attached sessions"', StubRunner()) is None)

# F7: a heredoc body handed to a shell is a command, not prose.
sh_heredoc_write_text = (
    "sh <<'EOF'\n"
    "osascript -e 'tell application \"iTerm\" to write text \"ls\"'\n"
    "EOF"
)
reason = decide(sh_heredoc_write_text, StubRunner())
check("F7: sh consuming a heredoc that runs osascript write text is denied",
      reason is not None and "write text" in reason, reason)

runner = StubRunner(stdout="1\n")
reason = decide("cat <<'EOF' | sh\ntmux send-keys -t seat-a x\nEOF", runner)
check("F7: a heredoc piped to sh with attached-target send-keys inside is denied",
      reason is not None and "attached client" in reason, reason)

# The old substring scan caught these incidentally; the parser must catch
# them deliberately (found in the fix round's own review).
reason = decide("sh -c 'tmux send-keys -t seat-a x'", StubRunner(stdout="1\n"))
check("an sh -c execution string is a command, not data",
      reason is not None and "attached client" in reason, reason)
reason = decide('eval "tmux send-keys -t seat-a x"', StubRunner(stdout="1\n"))
check("an eval argument is a command, not data",
      reason is not None and "attached client" in reason, reason)
runner = StubRunner()
check("a benign sh -c string stays untouched (no probes)",
      decide("sh -c 'echo harmless'", runner) is None and not runner.calls,
      runner.calls)


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

# F5: the documented aliases are the same verbs.
reason = decide("tmux send -t seat-a x", StubRunner(stdout="1\n"))
check("F5: the send alias at an attached session is denied",
      reason is not None and "attached client" in reason, reason)
reason = decide("tmux pasteb -t seat-a", StubRunner(stdout="1\n"))
check("F5: the pasteb alias at an attached session is denied",
      reason is not None and "attached client" in reason, reason)
runner = StubRunner()
check("F5: a -t value that happens to spell 'send' is not a verb (kill-session -t send)",
      decide("tmux kill-session -t send", runner) is None and not runner.calls,
      runner.calls)

# F8: target value forms the field actually writes.
runner = StubRunner()
reason = decide('tmux send-keys -t "$SEAT" x', runner)
check("F8a: an unexpanded variable target is denied naming the variable case",
      reason is not None and "unexpanded shell variable" in reason
      and "CLAUDE_VERIFIED_DETACHED=1" in reason and not runner.calls,
      reason)

runner = StubRunner(stdout="0\n")
check("F8b: the glued -tseat-a form probes seat-a",
      decide("tmux send-keys -tseat-a x", runner) is None
      and "seat-a" in runner.calls[0],
      runner.calls)

runner = StubRunner(stdout="1\n")
reason = decide("tmux send-keys -t 'seat a' x", runner)
check("F8c: a quoted target with a space probes the whole name",
      reason is not None and "'seat a'" in reason and "seat a" in runner.calls[0],
      (reason, runner.calls))

runner = StubRunner(stdout="0\n")
check("F8c: over ssh the spaced target survives the remote shell's re-split",
      decide('ssh ned \'tmux send-keys -t "seat a" x\'', runner) is None
      and "'seat a'" in runner.calls[0][-1],
      runner.calls)

runner = StubRunner()
reason = decide("tmux send-keys ls Enter; tmux kill-session -t old-seat", runner)
check("F8d: a -t on another tmux subcommand does not cover an untargeted send-keys",
      reason is not None and "no -t target" in reason and not runner.calls,
      (reason, runner.calls))

# F9: the escape hatch is an environment-assignment prefix, not a magic string.
reason = decide("tmux send-keys -t seat-a 'CLAUDE_VERIFIED_DETACHED=1 foo' Enter",
                StubRunner(stdout="1\n"))
check("F9: the override inside a keystroke payload does not count",
      reason is not None and "attached client" in reason, reason)
runner = StubRunner(stderr="unreachable", returncode=255)
check("F9: the override as a prefix inside the ssh remote command counts",
      decide("ssh ned 'CLAUDE_VERIFIED_DETACHED=1 tmux send-keys -t gatekeeper x'",
             runner) is None and not runner.calls,
      runner.calls)

# F4: only the ssh that wraps the tmux invocation attributes the probe.
runner = StubRunner(stdout="0\n")
check("F4: ssh inside a keystroke payload does not move the probe off this Mac",
      decide("tmux send-keys -t seat-a 'ssh ned uptime' Enter", runner) is None
      and runner.calls[0][0] == "tmux",
      runner.calls)

runner = StubRunner(stdout="0\n")
check("F4: mixed local and remote invocations probe their own hosts",
      decide("tmux send-keys -t local-seat x && ssh ned 'tmux send-keys -t remote-seat y'",
             runner) is None
      and runner.calls[0][0] == "tmux" and runner.calls[1][0] == "ssh",
      runner.calls)

# F1: probe count and the global wall-clock budget (a timed-out hook fails open).
runner = StubRunner(stdout="0\n")
check("F1: ssh's own -t flag is not harvested as a tmux target (one probe, not two)",
      decide("ssh -t ned 'tmux send-keys -t gatekeeper Enter'", runner) is None
      and len(runner.calls) == 1 and runner.calls[0][0] == "ssh",
      runner.calls)

clock = TickingClock()
runner = HangingProbeRunner(clock)
reason = decide("tmux send-keys -t seat-a x", runner, clock=clock)
check("F1: a hanging probe is killed by its own timeout and denies, fail-closed",
      reason is not None and "could not verify" in reason
      and clock.now <= guard.PROBE_BUDGET_SECONDS, (reason, clock.now))

clock = TickingClock()
runner = SlowProbeRunner(clock, cost_seconds=9.0, stdout="0\n")
reason = decide("tmux send-keys -t seat-a x; tmux send-keys -t seat-b y; "
                "tmux send-keys -t seat-c z", runner, clock=clock)
check("F1: slow probes exhaust the shared budget and the remainder denies",
      reason is not None and "probe budget exhausted" in reason
      and len(runner.calls) == 2, (reason, runner.calls))
check("F1: a probe near the deadline gets only the remaining time",
      runner.call_kwargs[1].get("timeout") is not None
      and runner.call_kwargs[1]["timeout"] <= 9.0 + 1e-9,
      runner.call_kwargs)

runner = StubRunner(stdout="0\n")
check("repeated targets are probed once (cached per host and target)",
      decide("tmux send-keys -t seat-a x; tmux send-keys -t seat-a y", runner) is None
      and len(runner.calls) == 1,
      runner.calls)

# F2/F3: things that look like heredoc markers but are not, and real
# terminators the old splitter missed — later lines must stay visible.
runner = StubRunner(stdout="1\n")
reason = decide("echo $((1<<20))\ntmux send-keys -t seat-a x", runner)
check("F2: arithmetic 1<<20 opens no heredoc; the next line is still guarded",
      reason is not None and "attached client" in reason, reason)

runner = StubRunner(stdout="1\n")
reason = decide('echo "x<<EOF"\ntmux send-keys -t seat-a x', runner)
check("F2: a quoted <<EOF opens no heredoc; the next line is still guarded",
      reason is not None and "attached client" in reason, reason)

runner = StubRunner(stdout="1\n")
reason = decide('grep foo <<< "bar baz"\ntmux send-keys -t seat-a x', runner)
check("F2: a here-string opens no heredoc; the next line is still guarded",
      reason is not None and "attached client" in reason, reason)

runner = StubRunner(stdout="1\n")
reason = decide('git commit -m "line one\nx<<EOF inside a string"\ntmux send-keys -t seat-a x',
                runner)
check("F2: quote state carries across lines (marker inside a multi-line -m string)",
      reason is not None and "attached client" in reason, reason)

runner = StubRunner(stdout="1\n")
reason = decide("cat <<'EOF-1'\nprose about tmux send-keys -t seat-a\nEOF-1\n"
                "tmux send-keys -t seat-a x", runner)
check("F3: a dashed terminator closes its heredoc; the line after is still guarded",
      reason is not None and "attached client" in reason, reason)

runner = StubRunner()
check("F3: prose inside a dashed-terminator heredoc stays data (no probes)",
      decide("cat <<'EOF-1'\ntmux send-keys -t seat-a prose\nEOF-1", runner) is None
      and not runner.calls,
      runner.calls)


# --- the ssh invocation parser ---

host, carried, remote = guard.parse_ssh_invocation(
    ["-o", "ConnectTimeout=5", "-t", "ned", "tmux ls"])
check("ssh host found past value-taking options and bare flags",
      host == "ned" and remote == ["tmux ls"], (host, carried, remote))
host, carried, remote = guard.parse_ssh_invocation(
    ["-p", "2222", "-i", "/tmp/key", "ned", "tmux ls"])
check("ssh -p and -i are carried into the probe's own dial",
      host == "ned" and carried == ["-p", "2222", "-i", "/tmp/key"],
      (host, carried))
check("no remote command means nothing to analyze",
      guard.parse_ssh_invocation(["ned"]) == ("ned", [], []))


print()
if failures:
    print(f"{len(failures)} case(s) failed")
    sys.exit(1)
print(f"all cases passed")
