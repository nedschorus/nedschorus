#!/usr/bin/env python3
"""Tests for resupervise-seat.py.

The script's whole value is that it REFUSES correctly: it kills a tmux session
and ends a running agent, so every path that reaches the kill must first prove
the seat's work is written down and waiting. These cases pin the refusals, since
a refusal that silently became a proceed is the failure that costs a session's
work.

Refusal cases run against a scratch handoff directory. The proceed path is
exercised with --dry-run and with a stub launcher, never by killing a real seat:
the suite runs on a machine whose own agents are live, so any case that could
touch a real tmux session is expressed against a name no seat uses.

Run: python3 scripts/resupervise-seat-test.py
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RESUPERVISE_SCRIPT = Path(__file__).with_name("resupervise-seat.py")

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def run_resupervise(workspace: Path, name: str, *flags):
    """Run the script against a scratch handoff directory and agents root."""
    return subprocess.run(
        [sys.executable, str(RESUPERVISE_SCRIPT), name,
         "--handoff-dir", str(workspace), "--agents-root", str(workspace / "agents"), *flags],
        capture_output=True, text=True, check=False,
    )


def write_handoff(workspace: Path, name: str, counter: int, dont_restart: bool = False):
    lines = [
        f"# handoff for {name}",
        "written-at: 2026-08-19T00:00:00+00:00",
        f"restart-counter: {counter}",
        "next-step: Continue the walk.",
    ]
    if dont_restart:
        lines.append("dont-restart: the user asked to be consulted")
    (workspace / f"{name}-handoff.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_state(workspace: Path, name: str, state: dict):
    (workspace / f"{name}-supervisor-state.json").write_text(
        json.dumps(state), encoding="utf-8"
    )


def run_no_handoff_cases(workspace: Path):
    """With nothing written down, the seat must be left strictly alone.

    This is the case that protects a working agent: no handoff means its work
    exists only in the running session, and killing that session destroys it.
    """
    result = run_resupervise(workspace, "nohandoff", "--dry-run")
    check("with no handoff at all, the script refuses",
          result.returncode == 1, result.stdout + result.stderr)
    check("the no-handoff refusal names the handoff-first procedure",
          "hand off first" in result.stderr, result.stderr)

    (workspace / "prose-handoff.md").write_text(
        "# handoff for prose\nthis file has no restart-counter line at all\n", encoding="utf-8"
    )
    result = run_resupervise(workspace, "prose", "--dry-run")
    check("a handoff with no restart-counter refuses",
          result.returncode == 1, result.stdout + result.stderr)
    check("the unreadable-handoff refusal says the supervisor would not ignite",
          "not ignite" in result.stderr, result.stderr)


def run_already_consumed_case(workspace: Path):
    """A handoff a supervisor already acted on is not a waiting handoff.

    Proceeding here would kill a session that had recycled normally -- the
    handoff on disk is the PREVIOUS cycle's, and the agent running now never
    asked to be retired.
    """
    write_handoff(workspace, "consumed", counter=4)
    write_state(workspace, "consumed", {"consumed_counter": 4, "session_id": "s"})
    result = run_resupervise(workspace, "consumed", "--dry-run")
    check("an already-consumed handoff refuses",
          result.returncode == 1, result.stdout + result.stderr)
    check("the consumed refusal names both counters",
          "restart-counter 4" in result.stderr and "recorded 4" in result.stderr,
          result.stderr)

    # Strictly newer is the boundary the supervisor's own boot-ignition uses.
    write_handoff(workspace, "consumed", counter=5)
    result = run_resupervise(workspace, "consumed", "--dry-run")
    check("a counter newer than the consumed one proceeds",
          result.returncode == 0, result.stdout + result.stderr)


def run_live_supervisor_case(workspace: Path):
    """A seat that already has a watcher is not the state this script repairs."""
    supervisor_module = load_supervisor()
    write_handoff(workspace, "watched", counter=1)
    supervisor_module.stamp_heartbeat(
        workspace / "watched-supervisor-state.json", {"session_id": "s"}
    )
    result = run_resupervise(workspace, "watched", "--dry-run")
    check("a seat with a live supervisor refuses",
          result.returncode == 1, result.stdout + result.stderr)
    check("the live-supervisor refusal says there is nothing to recover",
          "Nothing to recover" in result.stderr, result.stderr)


def load_supervisor():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "handoff_supervisor", RESUPERVISE_SCRIPT.with_name("handoff-supervisor.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_stale_heartbeat_case(workspace: Path):
    """A stale heartbeat is the real trigger: a supervisor that died mid-run.

    This is the 2026-08-18 shape -- state file present from a supervisor that
    is gone, agent still running -- and it must proceed, not refuse.
    """
    write_handoff(workspace, "stale", counter=2)
    write_state(workspace, "stale", {
        "consumed_counter": 1,
        "session_id": "s",
        "last_poll_at": "2026-08-18T00:00:00+00:00",
    })
    result = run_resupervise(workspace, "stale", "--dry-run")
    check("a stale heartbeat with a waiting handoff proceeds",
          result.returncode == 0, result.stdout + result.stderr)
    check("the proceed path reports the stale heartbeat as its reason",
          "no supervisor is watching" in result.stdout, result.stdout)
    check("the dry run changes nothing and says so",
          "DRY RUN" in result.stdout, result.stdout)


def run_dont_restart_case(workspace: Path):
    """dont-restart is the agent asking to be consulted, not a refusal.

    The supervisor honors it on its own terminal, so this script proceeds and
    warns rather than deciding on the agent's behalf.
    """
    write_handoff(workspace, "consult", counter=1, dont_restart=True)
    result = run_resupervise(workspace, "consult", "--dry-run")
    check("a dont-restart handoff still proceeds",
          result.returncode == 0, result.stdout + result.stderr)
    check("the dont-restart note reaches the operator",
          "dont-restart" in result.stdout, result.stdout)


def run_missing_launcher_case(workspace: Path):
    """Without a launcher there is no successor, so nothing may be killed.

    Checked BEFORE the kill: a script that cleared the seat and then discovered
    it could not launch would leave the operator worse off than it found them.
    """
    isolated = workspace / "isolated"
    isolated.mkdir()
    copied = isolated / "resupervise-seat.py"
    copied.write_text(RESUPERVISE_SCRIPT.read_text(encoding="utf-8"), encoding="utf-8")
    for sibling in ("handoff-supervisor.py",):
        (isolated / sibling).write_text(
            RESUPERVISE_SCRIPT.with_name(sibling).read_text(encoding="utf-8"), encoding="utf-8"
        )
    write_handoff(workspace, "nolauncher", counter=1)
    result = subprocess.run(
        [sys.executable, str(copied), "nolauncher",
         "--handoff-dir", str(workspace), "--agents-root", str(workspace / "agents")],
        capture_output=True, text=True, check=False,
    )
    check("a missing launcher refuses before anything is killed",
          result.returncode == 1, result.stdout + result.stderr)
    check("the missing-launcher refusal names the path it looked at",
          "launch-claude-mac" in result.stderr, result.stderr)


def run_prepare_only_case(workspace: Path):
    """--prepare-only is how a box seat's checks run on the box.

    It must not require a launcher: the launcher for a box seat is Mac-side,
    and demanding one on the box would refuse every box recovery.
    """
    isolated = workspace / "isolated"
    copied = isolated / "resupervise-seat.py"
    write_handoff(workspace, "boxseat", counter=1)
    result = subprocess.run(
        [sys.executable, str(copied), "boxseat", "--prepare-only",
         "--handoff-dir", str(workspace), "--agents-root", str(workspace / "agents")],
        capture_output=True, text=True, check=False,
    )
    check("--prepare-only succeeds with no launcher present",
          result.returncode == 0, result.stdout + result.stderr)
    check("--prepare-only says the seat is clear and stops",
          "launch it from the machine" in result.stdout, result.stdout)


def run_end_to_end_case(workspace: Path):
    """The proceed path really clears the seat and launches, and says so.

    Run against a stub launcher and a tmux session named for this suite, never
    a real seat. The output assertion is a regression pin: os.execv discards
    python's unflushed buffer, so before the explicit flush every diagnostic
    line above the launch vanished whenever stdout was not a terminal --
    exactly the piped and logged runs where the record matters most
    (measured 2026-08-19).

    The session is created on the DEFAULT tmux server, which since the
    per-seat-server change (2026-08-21) doubles as the transition case: a
    seat launched before that change lives there, and the kill must fall back
    to the default socket to find it.
    """
    if shutil.which("tmux") is None:
        print("SKIP  end-to-end: tmux is not installed")
        return

    isolated = workspace / "isolated"
    copied = isolated / "resupervise-seat.py"
    launcher_record = workspace / "launcher-ran.txt"
    stub_launcher = isolated / "launch-claude-mac"
    stub_launcher.write_text(
        f'#!/bin/sh\necho "ran $1" >> {launcher_record}\n', encoding="utf-8"
    )
    stub_launcher.chmod(0o755)

    session = "resupervise-seat-test-seat"
    write_handoff(workspace, session, counter=9)
    write_state(workspace, session, {
        "consumed_counter": 8, "session_id": "s",
        "last_poll_at": "2026-08-18T00:00:00+00:00",
    })
    created = subprocess.run(
        ["tmux", "new-session", "-d", "-s", session, "-c", str(workspace), "sleep 120"],
        capture_output=True, text=True, check=False,
    )
    if created.returncode != 0:
        print(f"SKIP  end-to-end: could not create a tmux session ({created.stderr.strip()})")
        return

    try:
        result = subprocess.run(
            [sys.executable, str(copied), session,
             "--handoff-dir", str(workspace), "--agents-root", str(workspace / "agents")],
            capture_output=True, text=True, check=False,
        )
        check("the proceed path runs the launcher",
              launcher_record.is_file() and session in launcher_record.read_text(),
              result.stdout + result.stderr)
        still_there = subprocess.run(
            ["tmux", "has-session", "-t", f"={session}"],
            capture_output=True, text=True, check=False,
        )
        check("the proceed path clears the stale tmux session",
              still_there.returncode != 0, "session survived")
        check("the record survives the exec into the launcher",
              "killed the stale tmux session" in result.stdout
              and "an unconsumed handoff is waiting" in result.stdout,
              result.stdout)
    finally:
        subprocess.run(["tmux", "kill-session", "-t", f"={session}"],
                       capture_output=True, check=False)


def run_per_seat_server_end_to_end_case(workspace: Path):
    """A seat living on its OWN tmux server is found and cleared there.

    Per-seat tmux servers (2026-08-21): the launchers put each seat's session
    on a server of its own, socket `tmux -L <name>`. The case above seats the
    stale session on the default server (the transition shape); this one
    seats it on the per-seat socket -- the steady-state shape -- and the kill
    must name that socket in its record.
    """
    if shutil.which("tmux") is None:
        print("SKIP  per-seat end-to-end: tmux is not installed")
        return

    isolated = workspace / "isolated"
    copied = isolated / "resupervise-seat.py"
    launcher_record = workspace / "launcher-ran-per-seat.txt"
    stub_launcher = isolated / "launch-claude-mac"
    stub_launcher.write_text(
        f'#!/bin/sh\necho "ran $1" >> {launcher_record}\n', encoding="utf-8"
    )
    stub_launcher.chmod(0o755)

    session = "resupervise-seat-test-own-server"
    write_handoff(workspace, session, counter=9)
    write_state(workspace, session, {
        "consumed_counter": 8, "session_id": "s",
        "last_poll_at": "2026-08-18T00:00:00+00:00",
    })
    created = subprocess.run(
        ["tmux", "-L", session, "new-session", "-d", "-s", session,
         "-c", str(workspace), "sleep 120"],
        capture_output=True, text=True, check=False,
    )
    if created.returncode != 0:
        print(f"SKIP  per-seat end-to-end: could not create a per-seat tmux session "
              f"({created.stderr.strip()})")
        return

    try:
        result = subprocess.run(
            [sys.executable, str(copied), session,
             "--handoff-dir", str(workspace), "--agents-root", str(workspace / "agents")],
            capture_output=True, text=True, check=False,
        )
        still_there = subprocess.run(
            ["tmux", "-L", session, "has-session", "-t", f"={session}"],
            capture_output=True, text=True, check=False,
        )
        check("a seat on its own tmux server is cleared there",
              still_there.returncode != 0, result.stdout + result.stderr)
        check("the kill record names the per-seat server socket",
              f"(server socket {session})" in result.stdout, result.stdout)
    finally:
        subprocess.run(["tmux", "-L", session, "kill-server"],
                       capture_output=True, check=False)


def run_missing_tmux_case(workspace: Path):
    """With tmux absent the script must refuse, never traceback.

    subprocess raises FileNotFoundError for a missing binary rather than
    returning a failure code, so an unguarded call crashes -- and it would crash
    under --dry-run and --prepare-only too, which promise to change nothing. Run
    with a PATH holding only the python interpreter's directory, so tmux really
    is unreachable.
    """
    isolated = workspace / "isolated"
    stub_path = workspace / "empty-path"
    stub_path.mkdir(exist_ok=True)
    write_handoff(workspace, "notmux", counter=1)
    environment = dict(os.environ)
    environment["PATH"] = str(stub_path)
    result = subprocess.run(
        [sys.executable, str(isolated / "resupervise-seat.py"), "notmux", "--prepare-only",
         "--handoff-dir", str(workspace), "--agents-root", str(workspace / "agents")],
        capture_output=True, text=True, check=False, env=environment,
    )
    check("a machine without tmux does not traceback",
          "Traceback" not in result.stderr, result.stderr)
    check("a machine without tmux still exits cleanly",
          result.returncode in (0, 1), f"exit {result.returncode}")


def run_agent_box_case(workspace: Path):
    """--agent-box must reach the launcher, not just the ssh checks.

    The launcher reads NEDSCHORUS_AGENT_BOX and otherwise defaults to its own
    alias, so a flag honored by the checks and dropped at the launch would clear
    one host and seat the successor on another. Asserted by reading the source:
    the launch is an exec, which cannot be observed from a subprocess run here.
    """
    source = (workspace / "isolated" / "resupervise-seat.py").read_text(encoding="utf-8")
    check("the box launch passes NEDSCHORUS_AGENT_BOX through",
          "NEDSCHORUS_AGENT_BOX" in source and "os.execve" in source,
          "the box launch does not carry --agent-box")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="resupervise-seat-test-") as scratch:
        workspace = Path(scratch)
        run_no_handoff_cases(workspace)
        run_already_consumed_case(workspace)
        run_live_supervisor_case(workspace)
        run_stale_heartbeat_case(workspace)
        run_dont_restart_case(workspace)
        run_missing_launcher_case(workspace)
        run_prepare_only_case(workspace)
        run_end_to_end_case(workspace)
        run_per_seat_server_end_to_end_case(workspace)
        run_missing_tmux_case(workspace)
        run_agent_box_case(workspace)

    print()
    if failures:
        print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
        return 1
    print("all cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
