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


class ScriptedProbeRunner(StubRunner):
    """A probe runner whose calls each consume the next scripted
    (stdout, stderr, returncode) — for the per-seat-server cases, where the
    first and second probes must answer differently. Running out of script
    raises, which fails the case loudly."""

    def __init__(self, results):
        super().__init__()
        self.results = list(results)

    def __call__(self, argv, **kwargs):
        self.calls.append(argv)
        self.call_kwargs.append(kwargs)
        stdout, stderr, returncode = self.results.pop(0)
        return subprocess.CompletedProcess(argv, returncode, stdout, stderr)


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

# N3: comments are stripped the way the shell strips them.
runner = StubRunner()
check("N3: a comment line mentioning the banned forms does not deny the command below",
      decide("# osascript write text\ngit status", runner) is None and not runner.calls,
      runner.calls)
runner = StubRunner()
check("N3: a trailing comment mentioning tmux send-keys stays a comment",
      decide("echo done # then tmux send-keys -t seat-a x", runner) is None
      and not runner.calls,
      runner.calls)
runner = StubRunner(stdout="1\n")
reason = decide("echo hi # docs mention <<EOF\ntmux send-keys -t seat-a x", runner)
check("N3: a <<EOF inside a comment opens no heredoc; the next line is still guarded",
      reason is not None and "attached client" in reason, reason)
check("N3: a quoted # is not a comment (probed as part of the word)",
      decide("tmux send-keys -t 'seat#3' x", StubRunner(stdout="0\n")) is None)

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
reason = decide("bash -lc 'tmux send-keys -t seat-a x'", StubRunner(stdout="1\n"))
check("N2: the -c riding in a flag cluster (bash -lc) is still an execution string",
      reason is not None and "attached client" in reason, reason)
reason = decide("sh -euc 'tmux send-keys -t seat-a x'", StubRunner(stdout="1\n"))
check("N2: a longer cluster (sh -euc) is still an execution string",
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
check("the attached denial sends a message for another agent-seat to SendMessage",
      reason is not None and "SendMessage tool" in reason and "#37" not in reason,
      reason)
check("the attached denial carries the show-the-user line for this machine",
      reason is not None and guard.show_the_user_line() in reason, reason)

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
check("the unverifiable denial carries the check command and the override",
      reason is not None
      and "Check the target with: python3 scripts/synthetic-keystroke-guard-hook.py "
          "--is-target-detached gatekeeper --ssh-host ned" in reason
      and "CLAUDE_VERIFIED_DETACHED=1" in reason and "session_attached" not in reason,
      reason)

check("the CLAUDE_VERIFIED_DETACHED=1 override skips the probe",
      decide("CLAUDE_VERIFIED_DETACHED=1 ssh ned 'tmux send-keys -t gatekeeper Enter'",
             StubRunner(stderr="unreachable", returncode=255)) is None)

reason = decide("tmux paste-buffer", StubRunner())
check("keystrokes with no -t target are denied",
      reason is not None and "no -t target" in reason, reason)
check("the no-target denial carries SendMessage and the show-the-user line",
      reason is not None and "SendMessage tool" in reason
      and guard.show_the_user_line() in reason and "#37" not in reason, reason)

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
      reason is not None and "unexpanded variable" in reason and not runner.calls,
      reason)
check("F8a: the unresolved-target denial offers no override, since no probe can check it",
      reason is not None and "CLAUDE_VERIFIED_DETACHED=1" not in reason, reason)
check("F8a: the unresolved-target denial shows the xargs placeholder literally",
      reason is not None and "If the target is xargs' or parallel's {}," in reason, reason)

runner = StubRunner(stderr="can't find pane: {}", returncode=1)
reason = decide("tmux ls -F '#{session_name}' | xargs -I{} tmux send-keys -t {} cmd",
                runner)
check("N1: an xargs {} placeholder target is unresolvable, not a can't-find allow",
      reason is not None and "replacement string" in reason and not runner.calls,
      (reason, runner.calls))

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

# --- per-seat tmux servers (2026-08-21): which server the probe dials ---
# Fleet seats each run their own tmux server (-L <seat>), so "no server
# running" on the default socket says nothing about the seat's own server —
# a probe that stopped there would read an attached per-seat session as
# safe to type into.

no_server_probe_answer = ("", "no server running on /private/tmp/tmux-501/default", 1)

# The two probe answers the PR #122 review measured on real tmux 3.7b that the
# first classifier misread (P2-1, P2-2): rc 0 with EMPTY stdout is tmux's
# CANFAIL answer for a live server that does not know the session — not a
# count of zero attached clients — and "error connecting" is the answer for
# an absent socket file, the steady state for a never-dialed socket path.
live_server_unknown_session_answer = ("", "", 0)
absent_socket_file_answer = (
    "", "error connecting to /private/tmp/tmux-501/default (No such file or directory)", 1)

runner = ScriptedProbeRunner([live_server_unknown_session_answer, ("1\n", "", 0)])
reason = decide("tmux send-keys -t seat-a x", runner)
check("P2-1: rc0+empty-stdout is unknown, not count 0 — per-seat fallback runs and denies",
      reason is not None and "attached client" in reason and len(runner.calls) == 2,
      (reason, runner.calls))

runner = ScriptedProbeRunner([live_server_unknown_session_answer, ("0\n", "", 0)])
check("P2-1: rc0+empty-stdout then per-seat-detached allows after both probes",
      decide("tmux send-keys -t seat-a x", runner) is None and len(runner.calls) == 2,
      runner.calls)

runner = ScriptedProbeRunner([absent_socket_file_answer, ("1\n", "", 0)])
reason = decide("tmux send-keys -t seat-a x", runner)
check("P2-2: absent socket file is unknown, not unverifiable — fallback runs and denies",
      reason is not None and "attached client" in reason and len(runner.calls) == 2,
      (reason, runner.calls))

runner = ScriptedProbeRunner([absent_socket_file_answer, ("0\n", "", 0)])
check("P2-2: absent socket file then per-seat-detached allows (no false deny)",
      decide("tmux send-keys -t seat-a x", runner) is None and len(runner.calls) == 2,
      runner.calls)

runner = ScriptedProbeRunner([("", "", 0)])
check("P2-1: with the command's own -L flag, rc0+empty-stdout stays a single-probe allow",
      decide("tmux -L seat-b send-keys -t seat-b x", runner) is None
      and len(runner.calls) == 1,
      runner.calls)

runner = ScriptedProbeRunner([no_server_probe_answer, ("1\n", "", 0)])
reason = decide("tmux send-keys -t seat-a x", runner)
check("per-seat: default-unknown then per-seat-attached denies",
      reason is not None and "attached client" in reason, reason)
check("per-seat: the first probe carries no socket flag (the command's own plain dial)",
      runner.calls[0] == ["tmux", "display-message", "-p", "-t", "seat-a",
                          "#{session_attached}"],
      runner.calls)
check("per-seat: the fallback probe dials the seat's own socket, exact argv",
      runner.calls[1] == ["tmux", "-L", "seat-a", "display-message", "-p",
                          "-t", "seat-a", "#{session_attached}"],
      runner.calls)

runner = ScriptedProbeRunner([no_server_probe_answer, ("0\n", "", 0)])
check("per-seat: default-unknown then per-seat-detached allows after both probes",
      decide("tmux send-keys -t seat-a x", runner) is None
      and len(runner.calls) == 2, runner.calls)

runner = ScriptedProbeRunner([no_server_probe_answer, no_server_probe_answer])
check("per-seat: a session no probed server knows is allowed (types nowhere)",
      decide("tmux send-keys -t seat-a x", runner) is None
      and len(runner.calls) == 2, runner.calls)

runner = StubRunner(stdout="1\n")
reason = decide("tmux -L seat-b send-keys -t seat-b x", runner)
check("per-seat: a command-carried -L rides the probe and an attached answer denies",
      reason is not None and "attached client" in reason
      and runner.calls[0][:3] == ["tmux", "-L", "seat-b"],
      (reason, runner.calls))

runner = ScriptedProbeRunner([no_server_probe_answer])
check("per-seat: a command-carried -L is probed exclusively — no second-socket shopping",
      decide("tmux -L seat-b send-keys -t seat-b x", runner) is None
      and len(runner.calls) == 1, runner.calls)

runner = StubRunner(stdout="1\n")
reason = decide("tmux -Lseat-b send-keys -t seat-b x", runner)
check("per-seat: the glued -Lseat-b form still rides the probe",
      reason is not None and runner.calls[0][:3] == ["tmux", "-L", "seat-b"],
      (reason, runner.calls))

runner = StubRunner(stdout="1\n")
reason = decide("tmux -S /tmp/custom.sock send-keys -t seat-b x", runner)
check("per-seat: a command-carried -S socket path rides the probe",
      reason is not None
      and runner.calls[0][:3] == ["tmux", "-S", "/tmp/custom.sock"],
      (reason, runner.calls))

runner = ScriptedProbeRunner([no_server_probe_answer, ("1\n", "", 0)])
reason = decide("tmux send-keys -t seat-a:1.0 x", runner)
check("per-seat: a window-qualified target derives the socket from its session part",
      reason is not None and runner.calls[1][:3] == ["tmux", "-L", "seat-a"]
      and "seat-a:1.0" in runner.calls[1],
      (reason, runner.calls))

runner = ScriptedProbeRunner([no_server_probe_answer, ("1\n", "", 0)])
reason = decide("ssh ned 'tmux send-keys -t gatekeeper x'", runner)
check("per-seat: the ssh-wrapped fallback probe carries -L to the box",
      reason is not None and "attached client" in reason
      and runner.calls[1][0] == "ssh" and "-L gatekeeper" in runner.calls[1][-1],
      (reason, runner.calls))

runner = StubRunner(stdout="1\n")
reason = decide("ssh ned 'tmux -L gatekeeper send-keys -t gatekeeper x'", runner)
check("per-seat: a command-carried -L inside the ssh remote command rides that probe",
      reason is not None and runner.calls[0][0] == "ssh"
      and "-L gatekeeper" in runner.calls[0][-1],
      (reason, runner.calls))

runner = ScriptedProbeRunner([
    ("", "ssh: connect to host ned: Operation timed out", 255)])
reason = decide("ssh ned 'tmux send-keys -t gatekeeper x'", runner)
check("per-seat: an unverifiable first probe denies without shopping to a second socket",
      reason is not None and "could not verify" in reason
      and len(runner.calls) == 1,
      (reason, runner.calls))

reason = decide("tmux send-keys -t seat-a x",
                StubRunner(stderr="server exited unexpectedly", returncode=2))
check("per-seat: the unverifiable denial's check command names the target alone",
      reason is not None and "could not verify" in reason
      and "--is-target-detached seat-a\n" in reason,
      reason)


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


# --- a command substitution inside double quotes is a command list ---
# The shell runs "$( ... )" exactly as it runs a bare $( ... ). Read as one
# data word, a guarded command inside it passed, and a heredoc opened inside
# it was never split out, so the first " in the heredoc's body ended the
# string and a backticked command after it was read as an invocation.

commit_message_quoting_a_backticked_command = (
    "git commit -m \"$(cat <<'EOF'\n"
    "Document the rule\n"
    "\n"
    "The brief says: \"never `tmux send-keys -t $SEAT Enter` into a seat.\" Stated now.\n"
    "EOF\n"
    ")\""
)
runner = StubRunner()
reason = decide(commit_message_quoting_a_backticked_command, runner)
check("a heredoc commit message inside \"$(cat <<'EOF' ...)\" is data, quotes and backticks included",
      reason is None and not runner.calls, (reason, runner.calls))

reason = decide('echo "$(tmux send-keys -t seat-a x)"', StubRunner(stdout="1\n"))
check("send-keys inside a double-quoted command substitution is denied like the bare form",
      reason is not None and "attached client" in reason, reason)

reason = decide('OUTPUT="$(tmux paste-buffer -t seat-a 2>&1)"', StubRunner(stdout="1\n"))
check("paste-buffer captured into a double-quoted assignment is denied",
      reason is not None and "attached client" in reason, reason)

quoted_substitution_feeding_osascript_a_heredoc = (
    "RESULT=\"$(osascript <<'EOF'\n"
    'tell application "iTerm" to tell current session of front window to write text "ls"\n'
    "EOF\n"
    ")\""
)
reason = decide(quoted_substitution_feeding_osascript_a_heredoc, StubRunner())
check("osascript consuming a heredoc inside a double-quoted substitution is denied",
      reason is not None and "write text" in reason, reason)

runner = StubRunner(stdout="1\n")
reason = decide("git commit -m \"$(cat <<'EOF'\nA 27\" monitor fits\nEOF\n)\"\n"
                "tmux send-keys -t seat-a x", runner)
check("a lone \" in the heredoc message does not hide the command after the commit",
      reason is not None and "attached client" in reason, reason)

runner = StubRunner(stdout="1\n")
reason = decide('echo "$(tmux send-keys -t seat-a x', runner)
check("an unterminated \"$( is read as commands to the end of the text",
      reason is not None and "attached client" in reason, reason)

words = guard.tokenize_simple_commands('echo "at $(date +%H) today" done')
check("the substitution's commands come first and the word keeps its text unexpanded",
      words == [["date", "+%H"], ["echo", "at $(date +%H) today", "done"]], words)

words = guard.tokenize_simple_commands('cd "$(dirname "$(git rev-parse --git-dir)")" && ls')
check("a substitution nested in another, both double-quoted, is read innermost first",
      words == [["git", "rev-parse", "--git-dir"],
                ["dirname", "$(git rev-parse --git-dir)"],
                ["cd", '$(dirname "$(git rev-parse --git-dir)")'], ["ls"]], words)

words = guard.tokenize_simple_commands(
    'echo "$(printf \')\'; printf "%s)" x; (cd /tmp; ls); tmux send-keys -t seat-a x) end"')
check("a ) in quotes or closing a subshell does not close the substitution",
      words[:5] == [["printf", ")"], ["printf", "%s)", "x"], ["cd", "/tmp"], ["ls"],
                    ["tmux", "send-keys", "-t", "seat-a", "x"]]
      and len(words) == 6 and words[5][0] == "echo" and words[5][1].endswith(" end"),
      words)

# Controls: forms the fix must leave as they were.
runner = StubRunner(stdout="1\n")
check("an escaped \\$( in double quotes is not a substitution (stays data, no probes)",
      decide('echo "\\$(tmux send-keys -t seat-a x)"', runner) is None
      and not runner.calls, runner.calls)

runner = StubRunner()
reason = decide('tmux send-keys -t "$(cat seat-name)" x', runner)
check("a substitution as the target is still an unresolved target, not probed",
      reason is not None and "unexpanded variable" in reason and not runner.calls,
      (reason, runner.calls))

runner = StubRunner(stdout="1\n")
reason = decide('echo "$((1<<20))"\ntmux send-keys -t seat-a x', runner)
check("double-quoted arithmetic 1<<20 opens no heredoc; the next line is still guarded",
      reason is not None and "attached client" in reason, reason)

shell_view, heredocs = guard.split_out_heredocs(commit_message_quoting_a_backticked_command)
check("the heredoc inside the double-quoted substitution is split out, body and all",
      shell_view == "git commit -m \"$(cat <<'EOF'\n)\""
      and [body.splitlines()[0] for _line, body in heredocs] == ["Document the rule"],
      (shell_view, heredocs))

# --- a quoted substitution must never hide a command the shell runs ---
# In each command below the shell runs the tmux command. The reader that read
# a double-quoted string as one word listed that command, by reading on past
# the string's closing quote. Reading the substitution as commands must not
# lose it: these are the shapes where the first version of that reading did.

for case_name, command in [
    ("a ( inside ${...} does not hold the substitution open: the command after it is read",
     'echo "$(a ${x%(*})"; tmux send-keys -t seat-a x'),
    ("a $'...' string holding \\' ends at its own quote: the command after it is read",
     "NOTE=\"$(a $'it\\'s')\"; tmux send-keys -t seat-a x"),
    ("a heredoc in quoted arithmetic with a lone ' in its body: the command after it is read",
     "N=\"$(( $(cat <<'EOF'\nit's 1\nEOF\n) + 1 ))\"; tmux send-keys -t seat-a x"),
    # The shell rejects this one. It stands for every reading of a
    # substitution that loses its place and never finds the closing ).
    ("a substitution the reader cannot close: the command after the string is still read",
     'echo "$(a \'unclosed)"; tmux send-keys -t seat-a x'),
]:
    reason = decide(command, StubRunner(stdout="1\n"))
    check(case_name, reason is not None and "attached client" in reason, reason)

words = guard.tokenize_simple_commands('echo "$(a ${x%(*}; b ${y:-$(c)})" && d')
check("inside ${...} a parenthesis is a word character, and a $( there is still read",
      words == [["a", "${x%(*}"], ["b", "${y:-$"], ["c"], ["}"],
                ["echo", "$(a ${x%(*}; b ${y:-$(c)})"], ["d"]], words)

words = guard.tokenize_simple_commands("a $'it\\'s' b; echo $'x'; c 'it\\'s'")
check("$'...' ends at its first unescaped quote, and a plain '...' at its first quote",
      words[0] == ["a", "$it\\'s", "b"] and words[1] == ["echo", "$x"]
      and words[2][0] == "c", words)

# The bare form, $( ... ) outside quotes, read the $'...' string the same
# wrong way before this change, so the command after it passed there too.
reason = decide("NOTE=$(a $'it\\'s'); tmux send-keys -t seat-a x", StubRunner(stdout="1\n"))
check("the same $'...' string in a bare substitution no longer hides the command after it",
      reason is not None and "attached client" in reason, reason)

# A heredoc whose delimiter is not quoted is not plain data: the shell expands
# its body, and runs every $( ... ) and backticked command in it, before the
# consumer sees it. Those commands are read; the rest of the body is data.
unquoted_heredoc_message_running_a_backticked_command = (
    'git commit -m "$(cat <<EOF\n'
    'say "never `tmux send-keys -t seat-a x` here."\n'
    "EOF\n"
    ')"'
)
reason = decide(unquoted_heredoc_message_running_a_backticked_command, StubRunner(stdout="1\n"))
check("a backticked command in an unquoted-delimiter heredoc inside \"$( ... )\" is read",
      reason is not None and "attached client" in reason, reason)

for case_name, command in [
    ("a backticked command in an unquoted-delimiter heredoc at the top level is read",
     "cat > notes.md <<EOF\nnever `tmux send-keys -t seat-a x` here\nEOF"),
    ("a $( ... ) in an unquoted-delimiter heredoc at the top level is read",
     "cat > notes.md <<-EOF\n\tseat: $(tmux send-keys -t seat-a x)\n\tEOF"),
]:
    reason = decide(command, StubRunner(stdout="1\n"))
    check(case_name, reason is not None and "attached client" in reason, reason)

runner = StubRunner(stdout="1\n")
check("escaped \\` and \\$( in an unquoted-delimiter heredoc stay data (no probes)",
      decide("cat > notes.md <<EOF\nnever \\`tmux send-keys -t seat-a x\\` "
             "or \\$(tmux send-keys -t seat-b y) here\nEOF", runner) is None
      and not runner.calls, runner.calls)

shell_view, heredocs = guard.split_out_heredocs(
    "cat <<EOF\nnever `tmux send-keys -t seat-a x` or $(date +%H) here\nEOF\nls")
mark = guard.EXPANDED_BODY_COMMANDS_MARK
check("an unquoted-delimiter heredoc leaves its substitutions in the shell view, marked, at its <<",
      shell_view == (f"cat {mark}{'tmux send-keys -t seat-a x'.encode().hex()}{mark}"
                     f"{mark}{'date +%H'.encode().hex()}{mark}<<EOF\nls")
      and heredocs == [("cat <<EOF",
                        "never `tmux send-keys -t seat-a x` or $(date +%H) here")],
      (shell_view, heredocs))
# A guard that scans the shell view's text itself, as the leading-dash guard
# marks unquoted glob characters, must not see a body's quotes or globs: a
# lone ' there would hide every glob after the heredoc.
shell_view_with_quotes, _heredocs = guard.split_out_heredocs(
    "cat <<EOF\nuse the `don't \"*\" #` form\nEOF\ngrep phrase *.txt")
check("a marked command list holds no quote, glob character or # in the shell view",
      shell_view_with_quotes.endswith("<<EOF\ngrep phrase *.txt")
      and not any(c in shell_view_with_quotes[:-len("<<EOF\ngrep phrase *.txt")]
                  for c in "'\"`*#"),
      shell_view_with_quotes)
words = guard.tokenize_simple_commands(shell_view)
check("each marked command list is read as a substitution, ahead of the heredoc's command",
      words == [["tmux", "send-keys", "-t", "seat-a", "x"], ["date", "+%H"],
                ["cat", "<<EOF"], ["ls"]]
      and [type(w).__name__ for w in words] == ["SubstitutionCommand", "SubstitutionCommand",
                                                 "list", "list"],
      words)

# The heredoc scan keeps its place past the same two forms: a heredoc opened
# on the line after either is still split out, and its body is data.
for case_name, first_line in [
    ("the heredoc scan reads past ${x%(*}: a heredoc on the next line is split out",
     'X="$(a ${x%(*})"'),
    ("the heredoc scan reads past $'it\\'s': a heredoc on the next line is split out",
     "X=\"$(a $'it\\'s')\""),
]:
    runner = StubRunner(stdout="1\n")
    check(case_name,
          decide(first_line + "\ncat <<'EOF'\nnever `tmux send-keys -t seat-a x`\nEOF",
                 runner) is None and not runner.calls, runner.calls)

# Controls for the heredoc scan inside a quoted substitution: each passes
# before this change too, and each fails if the scan closes the substitution
# at the first ), opens one at an escaped \$(, or does not return to the
# string when the substitution closes.
runner = StubRunner(stdout="1\n")
check("a heredoc opened after a subshell inside the quoted substitution is split out",
      decide("X=\"$( (a); cat <<'EOF'\nnever `tmux send-keys -t seat-a x`\nEOF\n)\"",
             runner) is None and not runner.calls, runner.calls)

reason = decide("echo \"run \\$(cat <<'EOF' yourself\"\ntmux send-keys -t seat-a x",
                StubRunner(stdout="1\n"))
check("an escaped \\$( opens no substitution for the heredoc scan: << after it is data",
      reason is not None and "attached client" in reason, reason)

reason = decide('echo "$(a) see <<EOF"\ntmux send-keys -t seat-a x\nEOF',
                StubRunner(stdout="1\n"))
check("after the substitution closes the scan is back in the string: << there is data",
      reason is not None and "attached client" in reason, reason)

# --- the second reading must not hide a command the shell runs either ---
# In each command below bash 3.2 and bash 5.3 run the tmux command, and the
# reader that read a double-quoted string as one word listed it. These are
# the shapes where the reading of quoted substitutions and expanded heredoc
# bodies, as first fixed, lost it.
for case_name, command in [
    ("a lone ' in a backticked command in an unquoted body does not hide the command after it",
     "cat > notes.md <<EOF\nuse the `don't` form\nEOF\ntmux send-keys -t seat-a x"),
    ("a lone ' in a $( ... ) in an unquoted body does not hide the command after it",
     "cat > notes.md <<EOF\nuse $(a it's) form\nEOF\ntmux send-keys -t seat-a x"),
    ("a lone \" in a backticked command in an unquoted body does not hide the command after it",
     'cat > notes.md <<EOF\nuse `a "b` form\nEOF\ntmux send-keys -t seat-a x'),
    ("a lone \" in a $( ... ) in an unquoted body does not hide the command after it",
     'cat > notes.md <<EOF\nuse $(a "x) form\nEOF\ntmux send-keys -t seat-a x'),
    ("a <<\\EOF heredoc inside \"$( ... )\" ends at EOF: the command after the string is read",
     'X="$(cat <<\\EOF\nplain\nEOF\n)"; tmux send-keys -t seat-a x'),
    ("a <<E\"O\"F heredoc inside \"$( ... )\" ends at EOF: the command after the string is read",
     'X="$(cat <<E"O"F\nplain\nEOF\n)"; tmux send-keys -t seat-a x'),
    ("a <<\\EOF heredoc at the top level ends at EOF: the command after it is read",
     "cat <<\\EOF\nplain\nEOF\ntmux send-keys -t seat-a x"),
    ("$$ before a single-quoted string ending in \\ does not open $'...': the command after is read",
     "a $$'a\\'; tmux send-keys -t seat-a x"),
    ("$$$' still opens $'...' after the process id: the command after it is read",
     "a $$$'a\\''; tmux send-keys -t seat-a x"),
    ("a subshell inside a $( ... ) inside ${ ... } is read as commands",
     "echo ${y:-$(a && (tmux send-keys -t seat-a x))}"),
    ("a subshell after a pipe inside a $( ... ) inside ${ ... } is read as commands",
     "echo ${y:-$(a | (tmux send-keys -t seat-a x))}"),
    ("a subshell opening a $( ... ) inside ${ ... } is read as commands",
     "echo ${y:-$( (tmux send-keys -t seat-a x) )}"),
    ("a ; inside ${ ... } still ends nothing but the pattern: the command after it is read",
     "echo ${x:-a;}; tmux send-keys -t seat-a x"),
]:
    reason = decide(command, StubRunner(stdout="1\n"))
    check(case_name, reason is not None and "attached client" in reason, reason)

# The heredoc scan keeps its place past the same forms: a heredoc opened on
# the line after either is still split out, and its body is data.
for case_name, first_line in [
    ("the heredoc scan reads $$'a\\' as the process id and a plain string",
     "a $$'a\\'"),
    ("the heredoc scan reads $$'a\\' inside a quoted substitution the same way",
     "X=\"$(a $$'a\\')\""),
    ("the heredoc scan reads a subshell inside ${y:-$( ... )} as a subshell",
     'X="$(a ${y:-$(b && (c))})"'),
]:
    runner = StubRunner(stdout="1\n")
    check(case_name,
          decide(first_line + "\ncat <<'EOF'\nnever `tmux send-keys -t seat-a x`\nEOF",
                 runner) is None and not runner.calls, runner.calls)

# Forms where bash runs no tmux command, and the reader must not refuse one.
for case_name, command in [
    ("a body behind <<\\EOF is not expanded: its backticked command is data",
     "cat <<\\EOF\nsay `tmux send-keys -t seat-a x` here\nEOF\nc"),
    ("a body behind <<E\"O\"F is not expanded: its backticked command is data",
     'cat <<E"O"F\nsay `tmux send-keys -t seat-a x` here\nEOF\nc'),
    ("a lone backtick in an unquoted body runs nothing: the prose after it is data",
     "cat > notes.md <<EOF\nthe ` character; never tmux send-keys -t seat-a x\nEOF"),
    ("a $( in an unquoted body that never closes runs nothing",
     "cat > notes.md <<EOF\nthen $(tmux send-keys -t seat-a x\nEOF"),
    ("$$( in an unquoted body is the process id and a parenthesis, not a substitution",
     "cat <<EOF\npid $$(tmux send-keys -t seat-a x)\nEOF"),
    # bash rejects this one whole. A substitution that loses its place keeps
    # the commands it found, and the rest of its string is data: a later $(
    # in the same string is not read again.
    ("after a substitution loses its place, a later $( in the same string is data",
     "echo \"$(a 'x) $(tmux send-keys -t seat-a x)\""),
]:
    runner = StubRunner(stdout="1\n")
    check(case_name, decide(command, runner) is None and not runner.calls, runner.calls)

reason = decide("cat > notes.md <<EOF\n$(tmux send-keys -t seat-a x) then $(date\nEOF",
                StubRunner(stdout="1\n"))
check("a substitution before one that never closes still runs and is read",
      reason is not None and "attached client" in reason, reason)

# Nesting far past any real command reads the deep part as data, the way the
# reader did before it read substitutions at all, instead of exhausting
# Python's recursion and crashing the guard, which lets the command through.
deeply_nested = "tmux send-keys -t seat-a x"
for _level in range(1500):
    deeply_nested = 'echo "$(' + deeply_nested + ')"'
try:
    reason = decide(deeply_nested, StubRunner(stdout="1\n"))
    crashed = None
except RecursionError as error:
    reason, crashed = None, error
check("1,500 nested quoted substitutions do not crash the guard, which still denies",
      crashed is None and reason is not None and "attached client" in reason,
      (crashed, reason))

# --- the third reading: forms where bash runs the tmux command ---
# Each was refused before quoted substitutions were read, and the second
# reading passed it.
for case_name, command in [
    ("a process substitution <( ... ) inside ${ ... } is read as commands",
     "cat ${output:-<(tmux send-keys -t seat-a x)}"),
    ("a process substitution >( ... ) inside ${ ... } is read as commands",
     "tee ${output:->(tmux send-keys -t seat-a x)} < notes.md"),
    ("a heredoc inside \"$( ... )\" ending EOF)\" ends there: the command after the string is read",
     "git commit -m \"$(cat <<'EOF'\nmessage\nEOF)\"\ntmux send-keys -t seat-a x"),
    ("an empty-delimiter heredoc inside \"$( ... )\" ends at its ): the command after is read",
     "git commit -m \"$(cat <<''\nmessage\n)\"\ntmux send-keys -t seat-a x"),
    ("a case pattern's ) inside \"$( ... )\" ends the pattern, not the substitution",
     "X=\"$(b \"$(case x in x) tmux send-keys -t seat-a x;; esac)\")\""),
    ("a case pattern's ) inside a bare \"$( ... )\" ends the pattern, not the substitution",
     "X=\"$(case x in x) tmux send-keys -t seat-a x;; esac)\""),
    ("a heredoc opened in a $( ... ) inside $(( ... )) is a heredoc, not a shift",
     "X=1 a \"$(( $(cat <<EOF | cat\na b # $(echo \"$(tmux send-keys -t seat-a x)\") $(a it's)\n"
     "EOF\nc \"$(( $(c) + 1 ))\"\n) + 1 ))\""),
    ("a backticked command inside double quotes is read as commands",
     "echo $'it\\'s' \"'`tmux send-keys -t seat-a x`\""),
    ("a backticked command in a string after a quoted substitution is read as commands",
     "X=\"$(a ${y:-$(b && (c))}) <<'EOF'\n`tmux send-keys -t seat-a x`\nEOF\n\""),
    ("three quoted substitutions deep, the innermost command is read",
     'echo "$(echo "$(echo "$(tmux send-keys -t seat-a x)")")"'),
    ("a NUL in the command is dropped, as the shell drops it: the command after it is read",
     "a \x00 b; case x in x) c;; esac; tmux send-keys -t seat-a x"),
]:
    reason = decide(command, StubRunner(stdout="1\n"))
    check(case_name, reason is not None and "attached client" in reason, reason)

# Forms where bash runs no tmux command: no refusal, no probe.
for case_name, command in [
    ("$$( inside double quotes is the process id and a parenthesis, not a substitution",
     'echo "$$(tmux send-keys -t seat-a x)"'),
    ("$$( mid-string inside double quotes is not a substitution either",
     'echo "a $$(tmux send-keys -t seat-a x) b"; c'),
    ("a heredoc after ${y:-$( (b) )} inside \"$( ... )\" is split out: its body is data",
     "X=\"$(a ${y:-$( (b)\n)}; cat <<'EOF'\n`tmux send-keys -t seat-a x`\nEOF\n)\""),
    ("an escaped backtick inside double quotes is data",
     'echo "\\`tmux send-keys -t seat-a x\\`"'),
    ("text between two NULs the command holds is not read as a marked command list",
     "a \x00" + "tmux send-keys -t seat-a x".encode().hex() + "\x00 c"),
    ("a quoted-delimiter heredoc inside a substitution in an unquoted body is data",
     "cat <<EOF\n$(cat <<'X'\n$(tmux send-keys -t seat-a x)\nX\n)\nEOF\nc"),
    ("a single-quoted $( inside a backticked command inside double quotes is data",
     "echo \"`printf '%s' '$(tmux send-keys -t seat-a x)'`\""),
    ("a ${x:- pattern going on to the next line keeps the heredoc scan in place",
     "X=\"$(echo ${x:-\n(*})\"\ncat <<'EOF'\n`tmux send-keys -t seat-a x`\nEOF"),
]:
    runner = StubRunner(stdout="1\n")
    check(case_name, decide(command, runner) is None and not runner.calls, runner.calls)

words = guard.tokenize_simple_commands('X="$(case $v in (a|b) c;; *) d;;& e) f;& esac)" && g')
check("inside a quoted substitution a case's patterns and branches are read as commands",
      words[:-2] == [["case", "$v", "in"], ["a"], ["b"], ["c"], ["*"], ["d"], ["e"],
                     ["f"], ["esac"]]
      and words[-2][0].startswith("X=$(case") and words[-1] == ["g"], words)


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


# Each denial gives one instruction to a line.
for name, text in (("ATTACHED_REASON", guard.ATTACHED_REASON),
                   ("UNVERIFIED_REASON", guard.UNVERIFIED_REASON),
                   ("NO_TARGET_REASON", guard.NO_TARGET_REASON),
                   ("UNRESOLVED_TARGET_REASON", guard.UNRESOLVED_TARGET_REASON),
                   ("SYNTHETIC_TYPING_REASON", guard.SYNTHETIC_TYPING_REASON)):
    check(f"{name} cites no issue and names no date",
          "nedschorus#" not in text and "#37" not in text and "2026" not in text, text)

check("the AppleScript denial tells an agent typing into another application to stop",
      "If you meant to type into another application, stop and tell the user what you wanted typed."
      in guard.SYNTHETIC_TYPING_REASON, guard.SYNTHETIC_TYPING_REASON)

# The show-the-user line is chosen by the platform the guard runs on.
check("on the Mac, the show-the-user line names the window opener",
      guard.show_the_user_line("darwin") ==
      "If the purpose is to show the user something, open a window with "
      "scripts/open-iterm-window-running-command <command...>",
      guard.show_the_user_line("darwin"))
check("elsewhere, the show-the-user line says the opener runs only on the Mac",
      guard.show_the_user_line("linux") ==
      "If the purpose is to show the user something, tell the user the command to run; "
      "the window opener runs only on the Mac.",
      guard.show_the_user_line("linux"))


# --- the check mode, --is-target-detached ---

def run_check(arguments, runner):
    out = io.StringIO()
    status = guard.run_check_mode(arguments, runner=runner, clock=lambda: 0.0, out=out)
    return status, out.getvalue().strip()


status, printed = run_check(["seat-a"], StubRunner(stdout="0\n"))
check("check mode: a detached session prints detached and exits 0",
      (status, printed) == (0, "detached"), (status, printed))
status, printed = run_check(["seat-a"], StubRunner(stdout="2\n"))
check("check mode: an attached session prints attached and exits 1",
      (status, printed) == (1, "attached"), (status, printed))
status, printed = run_check(["gatekeeper", "--ssh-host", "ned"],
                            StubRunner(stderr="ssh: connect to host ned: Operation timed out",
                                       returncode=255))
check("check mode: a failed probe prints could not verify with the error and exits 2",
      status == 2 and printed.startswith("could not verify: ")
      and "Operation timed out" in printed, (status, printed))
status, printed = run_check(["seat-a"], StubRunner(stdout="\n"))
check("check mode: an empty answer is not read as 0 attached clients",
      status == 2 and printed.startswith("could not verify: "), (status, printed))
status, printed = run_check(["seat-a"], ScriptedProbeRunner([
    ("", "no server running on /tmp/tmux-501/default", 1),
    ("", "error connecting to /tmp/tmux-501/seat-a", 1)]))
check("check mode: no server knowing the session prints could not verify, not detached",
      status == 2 and printed.startswith("could not verify: "), (status, printed))

runner = ScriptedProbeRunner([("", "no server running on /tmp/tmux-501/default", 1),
                              ("1\n", "", 0)])
status, printed = run_check(["seat-a"], runner)
check("check mode: it probes the seat's own server when the default has none",
      (status, printed) == (1, "attached") and len(runner.calls) == 2
      and runner.calls[1][:3] == ["tmux", "-L", "seat-a"], (status, printed, runner.calls))

runner = StubRunner(stdout="0\n")
status, printed = run_check(["gatekeeper", "--ssh-host", "ned", "--ssh-option", "-p", "2222",
                             "--tmux-server-flag", "-L", "gatekeeper"], runner)
check("check mode: the ssh host, carried option and server flag reach the probe",
      status == 0 and runner.calls and runner.calls[0][0] == "ssh"
      and "-p" in runner.calls[0] and "2222" in runner.calls[0] and "ned" in runner.calls[0]
      and "-L gatekeeper" in runner.calls[0][-1], runner.calls)
check("check mode: each probe may take longer than the hook's own",
      runner.call_kwargs and runner.call_kwargs[0]["timeout"] > guard.PER_PROBE_TIMEOUT_SECONDS,
      runner.call_kwargs)

status, printed = run_check(["seat-a", "--bogus"], StubRunner())
check("check mode: an unrecognised argument prints could not verify and exits 2",
      status == 2 and printed.startswith("could not verify: "), (status, printed))

command = guard.check_command("gatekeeper", ["-L", "gatekeeper"], ("ned", ("-p", "2222")))
target, server_flags, ssh_context = guard.parse_check_mode_arguments(
    __import__("shlex").split(command)[3:])
check("the check command the denial prints parses back to the same probe",
      (target, server_flags, ssh_context) == ("gatekeeper", ["-L", "gatekeeper"], ("ned", ("-p", "2222"))),
      (command, target, server_flags, ssh_context))

reason = decide("ssh a \"ssh b 'tmux send-keys -t s x'\"", StubRunner(stdout="0\n"))
check("a nested-ssh target is denied without a check command that cannot check it",
      reason is not None and "more than one ssh hop" in reason
      and "Check the target with" not in reason and guard.NESTED_SSH_HOST not in reason
      and "CLAUDE_VERIFIED_DETACHED" not in reason, reason)

completed = subprocess.run([sys.executable, str(HOOK_SCRIPT), "--is-target-detached"],
                           capture_output=True, text=True, check=False,
                           stdin=subprocess.DEVNULL, timeout=60)
check("check mode end to end: no target prints could not verify and exits 2",
      completed.returncode == 2 and completed.stdout.startswith("could not verify: "),
      (completed.returncode, completed.stdout, completed.stderr))


print()
if failures:
    print(f"{len(failures)} case(s) failed")
    sys.exit(1)
print(f"all cases passed")
