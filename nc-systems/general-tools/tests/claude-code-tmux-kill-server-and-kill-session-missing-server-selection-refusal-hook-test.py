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
        "heredoc ended early by a body line EOF, then a bare kill":
            "cat > probes.txt <<'EOF'\necho a\ncat <<EOF\nEOF\ntmux kill-server\nEOF\n",
        "heredoc ended early, then env -u TMUX kill":
            "cat > probes.txt <<'EOF'\ncat <<EOF\ntmux kill-server\nEOF\nenv -u TMUX tmux kill-server\nEOF\n",
        "after do, as a real agent typed it": 'for s in a b; do tmux kill-session -t "$s"; done',
        "after then": "if true; then TMUX_TMPDIR=/tmp/a tmux kill-server; fi",
        "after else": "if false; then :; else tmux kill-server; fi",
        "after !": "! tmux kill-server",
        "inside { }": "{ tmux kill-server; }",
        "inside ( )": "( tmux kill-server )",
        "after time": "time tmux kill-server",
        "after sudo": "sudo tmux kill-server",
        "after xargs": "printf '%s\\n' a | xargs tmux kill-session -t",
        "after env -C and its value": "env -C /tmp tmux kill-server",
        "a full path to tmux": "/usr/bin/tmux kill-server",
        "a value flag skipped before the command": "tmux -f /dev/null kill-server",
        "a value joined to -f": "tmux -f/tmp/x.conf kill-server",
        # tmux rejects -c together with a command (it prints its usage and
        # exits 1), so this command kills nothing; the case checks only that
        # -c's joined value is read as a value, and the refusal is harmless.
        "-c's joined value read as a value (tmux itself rejects this command)":
            "tmux -c/bin/sh kill-server",
        "a value joined to -T": "tmux -TRGB kill-server",
        "-- before the command": "tmux -- kill-server",
        "a grouped flag whose last letter takes a value": "tmux -2f /dev/null kill-server",
        "a redirection before the command": "tmux 2>/dev/null kill-server",
        "a redirection written apart, before the command": "tmux 2> /dev/null kill-server",
        "a later command after a word ending in ;": "tmux new -d -s a x\\; kill-server",
        "a later command after a quoted word ending in ;": "tmux new -d 'sleep 1;' kill-server",
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
        "-L inside a group of flags": "tmux -vL x kill-server",
        "-L joined in a group": "tmux -vLx kill-server",
        "-L after a redirection": "tmux 2>/dev/null -L x kill-server",
        "-S after env -u TMUX": "env -u TMUX tmux -S /tmp/s kill-server",
        "a session whose name starts with kill": "tmux -L x new -d -s kill-session-demo",
        "kill-server as the value of -f": "tmux -f kill-server list-sessions",
        "another tmux command": "tmux list-sessions",
        "tmux with flags and no command": "tmux -2u",
        "kill-pane is not a server or session kill": "tmux kill-pane -t x",
        "kill-server inside a heredoc body that ends at its own delimiter":
            "cat > probes.txt <<'EOF'\ntmux kill-server\nEOF\n",
        "quoted prose": 'echo "never run tmux kill-server bare"',
        "unquoted echo": "echo tmux kill-server",
        "prose in an argument": 'printf "%s" "note: tmux kill-server"',
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
    check("kill-session with no TMUX_TMPDIR: no command aimed at the agent-seat's own server",
          session == guard.REFUSAL_WITHOUT_COMMAND_MESSAGE and "TMUX%%" not in session,
          repr(session))
    all_but = run_main("tmux kill-session -a -t keep")
    check("kill-session -a: no suggested command, since -a kills every other session there",
          all_but == guard.REFUSAL_WITHOUT_COMMAND_MESSAGE, repr(all_but))
    kept_clear = run_main("TMUX_TMPDIR=/tmp/a tmux kill-session -C -t keep")
    check("kill-session with TMUX_TMPDIR: the exact command keeps -C",
          kept_clear is not None and f"\ntmux -S /tmp/a/tmux-{os.getuid()}/default kill-session -C -t keep\n" in kept_clear,
          repr(kept_clear))
    kept_all = run_main("TMUX_TMPDIR=/tmp/a tmux kill-session -a -t keep")
    check("kill-session -a with TMUX_TMPDIR: the exact command names the private server and keeps -a",
          kept_all is not None and f"\ntmux -S /tmp/a/tmux-{os.getuid()}/default kill-session -a -t keep\n" in kept_all,
          repr(kept_all))
    expanding = run_main('TMUX_TMPDIR=/tmp/a tmux kill-session -t "$session"')
    check("kill-session with a $variable target: no command that quotes it literally",
          expanding == guard.REFUSAL_WITHOUT_COMMAND_MESSAGE and "'$session'" not in expanding,
          repr(expanding))
    odd_word = run_main("TMUX_TMPDIR=/tmp/a tmux kill-session -t keep -a '$x'")
    check("kill-session with an expanding word besides the target: no suggested command",
          odd_word == guard.REFUSAL_WITHOUT_COMMAND_MESSAGE, repr(odd_word))
    through_env = run_main("env TMUX_TMPDIR=/tmp/a tmux kill-server")
    check("TMUX_TMPDIR set through env: gives the exact command",
          through_env is not None and f"\ntmux -S /tmp/a/tmux-{os.getuid()}/default kill-server\n" in through_env,
          repr(through_env))
    apart = run_main("TMUX_TMPDIR=/tmp/a tmux kill-server 2> /dev/null")
    check("a redirection written apart from its target is left out of the exact command",
          apart is not None and f"\ntmux -S /tmp/a/tmux-{os.getuid()}/default kill-server\n" in apart
          and "/dev/null" not in apart, repr(apart))
    dollar = run_main("TMUX_TMPDIR=$HOME/x tmux kill-server")
    check("TMUX_TMPDIR holding $: no exact command",
          dollar == guard.REFUSAL_WITHOUT_COMMAND_MESSAGE, repr(dollar))
    backtick = run_main("TMUX_TMPDIR=`pwd`/x tmux kill-server")
    check("TMUX_TMPDIR holding a backtick: no exact command",
          backtick == guard.REFUSAL_WITHOUT_COMMAND_MESSAGE, repr(backtick))
    unknown_user = run_main("TMUX_TMPDIR=~no-such-user-tkg/x tmux kill-server")
    check("TMUX_TMPDIR with a ~user the hook cannot expand: no exact command",
          unknown_user == guard.REFUSAL_WITHOUT_COMMAND_MESSAGE, repr(unknown_user))
    tilde = run_main("TMUX_TMPDIR=~/x tmux kill-server")
    expanded = os.path.expanduser("~/x")
    check("TMUX_TMPDIR starting with ~: the exact command holds the expanded path, not a quoted ~",
          tilde is not None and f"\ntmux -S {expanded}/tmux-{os.getuid()}/default kill-server\n" in tilde
          and "'~" not in tilde, repr(tilde))
    bare = run_main("tmux kill-server")
    for line in ("If you started a tmux server of your own",
                 "If you started a session with a tmux command that named no server",
                 "If you started no tmux server or session of your own",
                 "From now on, name the server in every tmux command"):
        check(f"bare kill-server: carries the line {line!r}",
              bare is not None and line in bare, repr(bare))
    check("bare kill-server: its example command passes the guard",
          run_main("tmux -L my-server kill-server") is None)
    check("the refusal gives a kill-session example too, and it passes the guard",
          "tmux -L my-server kill-session -t my-session" in guard.REFUSAL_WITHOUT_COMMAND_MESSAGE
          and run_main("tmux -L my-server kill-session -t my-session") is None,
          repr(guard.REFUSAL_WITHOUT_COMMAND_MESSAGE))
    check("with TMUX_TMPDIR, the line before a kill-session command does not call it a server kill",
          kept_clear is not None and "To kill the private server" not in kept_clear, repr(kept_clear))
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
