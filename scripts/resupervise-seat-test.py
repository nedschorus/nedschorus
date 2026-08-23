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
import shlex
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


def run_override_propagation_case(workspace: Path):
    """--agents-root and --handoff-dir must reach the launch, not just the checks.

    The pattern of recover-crashed-seats.py's codex findings A/B (PR #131
    round 3), present here too: the flags steered steps 1-4 and were then
    dropped at the exec, so the launcher re-resolved the agents root and the
    supervisor re-resolved the handoff directory from their own defaults —
    the checks cleared one seat and the launch watched another (user-ruled
    2026-08-22: allowed overrides must work). The stub launcher records the
    environment the exec actually carried.
    """
    isolated = workspace / "isolated"
    record = workspace / "launcher-environment.txt"
    stub_launcher = isolated / "launch-claude-mac"
    stub_launcher.write_text(
        '#!/bin/sh\n'
        f'echo "root=$NEDSCHORUS_AGENTS_ROOT" >> {record}\n'
        f'echo "extra=$LAUNCH_CLAUDE_SUPERVISOR_EXTRA_ARGUMENTS" >> {record}\n',
        encoding="utf-8")
    stub_launcher.chmod(0o755)
    write_handoff(workspace, "override-carry", counter=3)
    result = subprocess.run(
        [sys.executable, str(isolated / "resupervise-seat.py"), "override-carry",
         "--handoff-dir", str(workspace), "--agents-root", str(workspace / "agents")],
        capture_output=True, text=True, check=False,
    )
    recorded = record.read_text(encoding="utf-8") if record.is_file() else ""
    recorded_values = dict(line.split("=", 1)
                           for line in recorded.splitlines() if "=" in line)
    check("the mac launch carries the assessed agents root through NEDSCHORUS_AGENTS_ROOT",
          recorded_values.get("root") == str(workspace / "agents"),
          (recorded, result.stdout, result.stderr))
    # Parsed the way the launch shell will (shlex.split), not by matching
    # hand-written quotes — the quoting is under test (PR #134 finding 1).
    check("the mac launch hands the supervisor the assessed handoff directory",
          shlex.split(recorded_values.get("extra", ""))
          == ["--handoff-dir", str(workspace)], recorded)


def run_box_forwarding_case(workspace: Path):
    """--machine ubuntu forwards the overrides to both of its halves.

    The box-side --prepare-only checks and the Mac-side ubuntu launcher each
    resolve the directories themselves, so a value given here and not
    forwarded would steer nothing past the argument parser. Values travel
    verbatim (they are box-local paths; the box expands its own ~) and only
    when the operator gave them — the machine's own defaults must not be
    replaced by a Mac-expanded path. Probed in-process with ssh and the exec
    both captured.
    """
    import argparse
    import importlib.util
    spec = importlib.util.spec_from_file_location("resupervise_under_test",
                                                  RESUPERVISE_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    class FakeCompleted:
        returncode = 0

    class FakeSubprocess:
        def __init__(self):
            self.calls = []

        def run(self, argv, **keywords):
            self.calls.append(argv)
            return FakeCompleted()

    execve_calls = []

    class FakeOs:
        environ = {key: value for key, value in os.environ.items()
                   if key not in ("NEDSCHORUS_AGENTS_ROOT",
                                  "LAUNCH_CLAUDE_SUPERVISOR_EXTRA_ARGUMENTS")}

        @staticmethod
        def execve(path, argv, env):
            execve_calls.append((path, argv, env))

    fake_subprocess = FakeSubprocess()
    module.subprocess = fake_subprocess  # rebinds the module-level name only
    module.os = FakeOs

    arguments = argparse.Namespace(
        name="box-carry", machine="ubuntu", dry_run=False, prepare_only=False,
        agent_box="testbox", handoff_dir="/box/handoffs", agents_root="/box/agents")
    module.resupervise_box_seat(arguments)
    remote_command = fake_subprocess.calls[0][-1]
    remote_tokens = shlex.split(remote_command)  # parsed as the box shell will
    check("the box-side checks are given the overrides, verbatim",
          "/box/handoffs" in remote_tokens and "/box/agents" in remote_tokens
          and "--handoff-dir" in remote_tokens and "--agents-root" in remote_tokens,
          remote_command)
    _, _, environment = execve_calls[0]
    check("the ubuntu launch carries the overrides in its environment",
          environment.get("NEDSCHORUS_AGENTS_ROOT") == "/box/agents"
          and shlex.split(environment.get("LAUNCH_CLAUDE_SUPERVISOR_EXTRA_ARGUMENTS", ""))
              == ["--handoff-dir", "/box/handoffs"]
          and environment.get("NEDSCHORUS_AGENT_BOX") == "testbox",
          {key: environment.get(key) for key in
           ("NEDSCHORUS_AGENTS_ROOT", "LAUNCH_CLAUDE_SUPERVISOR_EXTRA_ARGUMENTS",
            "NEDSCHORUS_AGENT_BOX")})

    # PR #134 review finding 1, the box halves: an apostrophe path must
    # survive the remote shell's parse and the launcher hook's parse.
    fake_subprocess.calls.clear()
    execve_calls.clear()
    arguments = argparse.Namespace(
        name="box-quote", machine="ubuntu", dry_run=False, prepare_only=False,
        agent_box="testbox", handoff_dir="/box/agent's handoffs",
        agents_root="/box/agent's root")
    module.resupervise_box_seat(arguments)
    remote_tokens = shlex.split(fake_subprocess.calls[0][-1])
    _, _, environment = execve_calls[0]
    check("apostrophe paths survive the box remote command's shell parse",
          "/box/agent's handoffs" in remote_tokens
          and "/box/agent's root" in remote_tokens,
          fake_subprocess.calls[0][-1])
    check("apostrophe paths survive the ubuntu launcher hook's shell parse",
          shlex.split(environment.get("LAUNCH_CLAUDE_SUPERVISOR_EXTRA_ARGUMENTS", ""))
          == ["--handoff-dir", "/box/agent's handoffs"]
          and environment.get("NEDSCHORUS_AGENTS_ROOT") == "/box/agent's root",
          environment.get("LAUNCH_CLAUDE_SUPERVISOR_EXTRA_ARGUMENTS"))

    fake_subprocess.calls.clear()
    execve_calls.clear()
    arguments = argparse.Namespace(
        name="box-plain", machine="ubuntu", dry_run=False, prepare_only=False,
        agent_box="testbox", handoff_dir="", agents_root="")
    module.resupervise_box_seat(arguments)
    remote_command = fake_subprocess.calls[0][-1]
    _, _, environment = execve_calls[0]
    check("with no overrides given, the box halves keep their own defaults",
          "--handoff-dir" not in remote_command
          and "--agents-root" not in remote_command
          and "NEDSCHORUS_AGENTS_ROOT" not in environment
          and "LAUNCH_CLAUDE_SUPERVISOR_EXTRA_ARGUMENTS" not in environment,
          (remote_command, environment.get("NEDSCHORUS_AGENTS_ROOT")))

    # default_agents_root reads the launchers' own variable (the same rule as
    # recover-crashed-seats.py's twin), so the no-flag checks and the launch
    # resolve one root.
    FakeOs.environ["NEDSCHORUS_AGENTS_ROOT"] = "/elsewhere/agents"
    check("default_agents_root honors NEDSCHORUS_AGENTS_ROOT",
          module.default_agents_root() == Path("/elsewhere/agents"),
          module.default_agents_root())


def run_apostrophe_propagation_case(workspace: Path):
    """PR #134 review finding 1, end to end on the mac path: an operator's
    --handoff-dir containing an apostrophe broke the hand-quoted hook value
    at the launch shell — AFTER the stale session was killed, so the seat
    stayed down while the record said the successor was starting. Through
    the real script and a stub launcher: the propagated value must parse
    back to the exact path."""
    apostrophe_handoffs = workspace / "agent's handoffs"
    apostrophe_handoffs.mkdir(exist_ok=True)
    (apostrophe_handoffs / "quoted-seat-handoff.md").write_text(
        "# handoff for quoted-seat\nrestart-counter: 2\nnext-step: go\n",
        encoding="utf-8")
    isolated = workspace / "isolated"
    record = workspace / "launcher-environment-apostrophe.txt"
    stub_launcher = isolated / "launch-claude-mac"
    stub_launcher.write_text(
        '#!/bin/sh\n'
        f'echo "extra=$LAUNCH_CLAUDE_SUPERVISOR_EXTRA_ARGUMENTS" >> "{record}"\n',
        encoding="utf-8")
    stub_launcher.chmod(0o755)
    result = subprocess.run(
        [sys.executable, str(isolated / "resupervise-seat.py"), "quoted-seat",
         "--handoff-dir", str(apostrophe_handoffs),
         "--agents-root", str(workspace / "agents")],
        capture_output=True, text=True, check=False,
    )
    recorded = record.read_text(encoding="utf-8") if record.is_file() else ""
    extra_value = recorded.partition("extra=")[2].strip()
    check("an apostrophe --handoff-dir reaches the supervisor intact (mac, end to end)",
          shlex.split(extra_value) == ["--handoff-dir", str(apostrophe_handoffs)],
          (recorded, result.stdout, result.stderr))


def run_ubuntu_launcher_hook_case():
    """The box path's --handoff-dir rides launch-claude-ubuntu's
    extra-arguments hook; without the hook the value stops at the launcher.
    Asserted at the source, like the agent-box case: the launcher's decisive
    step is an ssh to the box, unobservable here."""
    source = RESUPERVISE_SCRIPT.with_name("launch-claude-ubuntu").read_text(encoding="utf-8")
    check("launch-claude-ubuntu appends the extra-arguments hook, like its Mac twin",
          'SUPERVISOR_COMMAND="$SUPERVISOR_COMMAND $(escape_remote_double_quote_context '
          '"$LAUNCH_CLAUDE_SUPERVISOR_EXTRA_ARGUMENTS")"' in source,
          "hook missing from launch-claude-ubuntu — its behavior is proven in "
          "launch-claude-ubuntu-test.py; this pins only that the hook exists")


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
        run_override_propagation_case(workspace)
        run_apostrophe_propagation_case(workspace)
        run_box_forwarding_case(workspace)
        run_ubuntu_launcher_hook_case()

    print()
    if failures:
        print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
        return 1
    print("all cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
