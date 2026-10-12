#!/usr/bin/env python3
"""Tests for nc-systems/general-tools/claude-code-tmux-kill-server-and-kill-session-missing-server-selection-refusal-hook.py.

The first case runs REAL tmux on a throwaway server, so the refusal is shown to
answer a real behavior: with $TMUX pointing at a server, `tmux kill-server`
kills that server even when TMUX_TMPDIR names another directory. If a later
tmux stopped doing that, the case would fail and say the guard's premise had
gone. It is skipped where tmux is not installed.

Run: python3 nc-systems/general-tools/tests/claude-code-tmux-kill-server-and-kill-session-missing-server-selection-refusal-hook-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HOOK_SCRIPT = (Path(__file__).resolve().parents[1]
               / "claude-code-tmux-kill-server-and-kill-session-missing-server-selection-refusal-hook.py")

_spec = importlib.util.spec_from_file_location("tmux_kill_guard", HOOK_SCRIPT)
guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guard)

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def run_main(command, tool_name="Bash"):
    """Drive main() as the harness does; return the refusal text or None."""
    payload = {"tool_name": tool_name, "cwd": "/tmp",
               "tool_input": {"command": command}}
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        code = guard.main(stdin=io.StringIO(json.dumps(payload)))
    text = stdout.getvalue().strip()
    if code != 0:
        return f"<exit {code}>"
    if not text:
        return None
    output = json.loads(text)["hookSpecificOutput"]
    assert output["permissionDecision"] == "deny", output
    return output["permissionDecisionReason"]


def premise_case():
    if shutil.which("tmux") is None:
        print("SKIP  premise: tmux is not installed here")
        return
    # A short directory: tmux socket paths have a length limit.
    scratch = Path(tempfile.mkdtemp(prefix="tkg-", dir="/tmp"))
    try:
        socket = scratch / "s"
        other = scratch / "other"
        other.mkdir()
        environment = {key: value for key, value in os.environ.items()
                       if key not in ("TMUX", "TMUX_PANE")}
        subprocess.run(["tmux", "-S", str(socket), "new-session", "-d", "-s", "probe"],
                       env=environment, check=True, timeout=20)
        server_environment = dict(environment, TMUX=f"{socket},0,0",
                                  TMUX_TMPDIR=str(other))
        subprocess.run(["tmux", "kill-server"], env=server_environment,
                       capture_output=True, timeout=20)
        alive = subprocess.run(["tmux", "-S", str(socket), "has-session", "-t", "probe"],
                               env=environment, capture_output=True, timeout=20)
        check("premise: a bare kill-server kills the server in $TMUX, whatever TMUX_TMPDIR says",
              alive.returncode != 0, "the server in $TMUX survived")
    finally:
        subprocess.run(["tmux", "-S", str(scratch / "s"), "kill-server"],
                       capture_output=True, timeout=20)
        shutil.rmtree(scratch, ignore_errors=True)


def refusal_cases():
    refused = {
        "bare kill-server": "tmux kill-server",
        "kill-session with a target": "tmux kill-session -t build-check",
        "TMUX_TMPDIR prefix does not name the server":
            "TMUX_TMPDIR=/tmp/claude-1000/F1-tmux tmux kill-server 2>/dev/null",
        "inside an && chain": "cd /tmp && tmux kill-server",
        "after a semicolon": "unset TMUX; tmux kill-session -t a",
        "env -u TMUX": "env -u TMUX tmux kill-server",
        "env with TMUX_TMPDIR": "env TMUX_TMPDIR=/tmp/a tmux kill-server",
        "abbreviated command name": "tmux kill-ses -t a",
        "second tmux command after \\;": "tmux new-session -d -s a \\; kill-server",
        "inside a command substitution": "echo $(tmux kill-server)",
        "after a timeout prefix": "timeout 5 tmux kill-server",
    }
    for name, command in refused.items():
        reason = run_main(command)
        check(f"refuses: {name}", reason is not None and reason.startswith("Refused on purpose"),
              f"{command!r} gave {reason!r}")


def allow_cases():
    allowed = {
        "-L names the server": "tmux -L private kill-server",
        "-S names the server": "tmux -S /tmp/s kill-server",
        "-S joined to its value": "tmux -S/tmp/s kill-session -t a",
        "-S after -f": "tmux -f /dev/null -S /tmp/s kill-server",
        "another tmux command": "tmux list-sessions",
        "kill-pane is not a server or session kill": "tmux kill-pane -t x",
        "quoted prose": 'echo "never run tmux kill-server bare"',
        "unquoted echo": "echo tmux kill-server",
        "prose in an argument": 'printf "%s" "note: tmux kill-server"',
        "the session command the refusal suggests":
            'tmux -S "${TMUX%%,*}" kill-session -t build-check',
    }
    for name, command in allowed.items():
        reason = run_main(command)
        check(f"allows: {name}", reason is None, f"{command!r} gave {reason!r}")
    check("allows: a tool other than Bash", run_main("tmux kill-server", tool_name="Read") is None)


def message_cases():
    with_tmpdir = run_main("TMUX_TMPDIR=/tmp/claude-1000/F1-tmux tmux kill-server 2>/dev/null")
    expected = f"tmux -S /tmp/claude-1000/F1-tmux/tmux-{os.getuid()}/default kill-server"
    check("with TMUX_TMPDIR: gives the exact command, without the redirection",
          with_tmpdir is not None and f"\n{expected}\n" in with_tmpdir, repr(with_tmpdir))
    session = run_main("tmux kill-session -t build-check")
    check("kill-session: names the target and the command on the agent-seat's server",
          session is not None
          and 'tmux -S "${TMUX%%,*}" kill-session -t build-check' in session
          and "display-message -p '#S'" in session, repr(session))
    suggested = 'tmux -S "${TMUX%%,*}" kill-session -t build-check'
    check("kill-session: the suggested command passes the guard", run_main(suggested) is None)
    bare = run_main("tmux kill-server")
    for line in ("If you started a tmux server of your own",
                 "If you started no tmux server of your own",
                 "From now on, name the server in every tmux command"):
        check(f"bare kill-server: carries the line {line!r}",
              bare is not None and line in bare, repr(bare))
    check("bare kill-server: its example command passes the guard",
          run_main("tmux -L my-server kill-server") is None)
    chained = run_main("TMUX_TMPDIR=/tmp/a tmux new -d \\; kill-server")
    check("a chained kill gets no computed command", chained == guard.REFUSAL_WITHOUT_COMMAND_MESSAGE,
          repr(chained))


def malformed_input_cases():
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        code = guard.main(stdin=io.StringIO("not json"))
    check("unreadable payload: allows silently", code == 0 and stdout.getvalue() == "")
    check("missing command: allows", run_main(None) is None)


premise_case()
refusal_cases()
allow_cases()
message_cases()
malformed_input_cases()
if failures:
    print(f"{len(failures)} case(s) failed")
    sys.exit(1)
print("all cases passed")
