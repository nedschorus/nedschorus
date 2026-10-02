#!/usr/bin/env python3
"""Put a supervisor back on a seat whose agent is running unsupervised.

An agent session reincarnates itself only when a supervisor is watching it: the
supervisor waits for the handoff file, kills the spent session, and starts the
successor on the same terminal. A session started any other way -- `claude` or
`claude --continue` typed by hand -- has no supervisor, so it can never reincarnate,
and one that began supervised can lose its supervisor while it keeps running
(observed 2026-08-18: two Mac seats ran unsupervised for about 25 hours).

Recovery used to be a hand procedure with no script behind it, so each one left
whatever state the operator improvised. The 2026-08-18 recovery left a stale
tmux window as the seat's ACTIVE window, and a healthy seat was read as dead for
a day. This script is that procedure, performed the same way every time.

WHAT IT DOES -- it retires the unsupervised session rather than adopting it:

  1. Refuse unless the seat's handoff file is genuinely waiting to be acted on
     (present, and carrying a restart-counter the supervisor has not consumed).
     The agent writes that file by running handoff-write-and-check-supervisor.py;
     ask it to hand off first, then run this.
  2. Refuse if a supervisor is already alive on the seat -- there is nothing to
     recover, and a second supervisor is exactly the two-watcher state the
     supervisor's own lock exists to prevent.
  3. Report what is running in the seat directory, read the same way
     clean-worktrees.py reads it (lsof), so the operator sees whether a live
     process is about to be retired and is told when that answer cannot be
     trusted.
  4. Kill the seat's stale tmux session, so the recovered seat lives in ONE
     window and no decoy is left behind. Checked on the seat's OWN tmux server
     (per-seat servers, `tmux -L <name>`, 2026-08-21) and on the default
     server, where seats launched before that change still live. That step is
     retire_seat_tmux_session below, which recover-crashed-seats.py runs too
     when an operator says to restart a seat behind a leftover idle shell.
  5. Run the seat's launcher. The supervisor boots, finds the unconsumed handoff,
     and ignites the successor from it (handoff-supervisor.py's boot-ignition
     path, live since 2026-08-14).

The successor is a fresh session carrying the retiring one's handoff and dialog
extract -- the ordinary reincarnation, not a continuation of the running process.
Step 4 ends the running session if it is still alive, which is the point: its
work is in the handoff. What it does cost is anything the agent did AFTER
writing that handoff, since the writer tells an unsupervised agent to keep
working; hand off again if that gap has grown. A wedged agent that cannot write
a handoff is out of scope: it needs live adoption, which the supervisor supports
through --adopt-session-id / --adopt-process-id and which no entry point reaches
(deliberately deferred, 2026-08-19).

WHERE EACH STEP RUNS. Steps 1-4 read and change state that lives on the seat's
OWN machine -- its handoff directory, its supervisor state file, its tmux
session. Step 5 runs the launcher, and launch-claude-ubuntu is a Mac-side
script: it composes a command and sends it over ssh, and the box cannot even
resolve its own ssh alias. So a box seat splits: --machine ubuntu runs steps 1-4
over ssh on the box (this same script, --prepare-only, in the box's checkout)
and then runs launch-claude-ubuntu here on the Mac. A Mac seat does all five
steps locally.

That split means --machine ubuntu needs this script present in the box's
checkout. The box checkout is pulled by hand today (nedschorus#45), so a box
that has not been pulled since this landed will refuse with a message saying so
rather than proceeding on a half-done recovery.

A box seat's directory is always ~/agents/<name> on the box, because
launch-claude-ubuntu reads no agents-root variable (user-ruled 2026-09-22, in
merge-lane-2's walk merge-lane-2-questions-concerns-and-suggestions-2026-09-22;
the launcher's NO AGENTS ROOT note has the why). So --machine ubuntu refuses
--agents-root, on either half: a root given here would steer the box-side
checks to one directory while the launcher seats the successor in another,
the split the 2026-08-22 ruling forbids ("overrides either work or are
blocked"). This script used to forward the value to both halves.

Usage:
  resupervise-seat.py <name> [--machine mac|ubuntu] [--dry-run]
                             [--handoff-dir <path>] [--agents-root <path>]
                             (--agents-root with --machine mac only)
  resupervise-seat.py <name> --prepare-only        (steps 1-4; run on the seat's
                                                    machine, then launch there)

Exit codes: 0 the seat was relaunched (or --dry-run / --prepare-only found it
ready), 1 refused because the seat is not in a recoverable state, 2 bad
invocation.
"""

import argparse
import importlib.util
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

_supervisor_spec = importlib.util.spec_from_file_location(
    "handoff_supervisor", Path(__file__).resolve().parent.parent
    / "nc-systems" / "handoff" / "handoff-supervisor.py"
)
supervisor = importlib.util.module_from_spec(_supervisor_spec)
_supervisor_spec.loader.exec_module(supervisor)

SCRIPT_DIRECTORY = Path(__file__).resolve().parent


def default_agents_root() -> Path:
    """Return the agents root using the Mac launcher's environment override."""
    # Checks and launcher must resolve the same root; the Ubuntu launcher always uses ~/agents.
    return Path(os.environ.get("NEDSCHORUS_AGENTS_ROOT") or "~/agents").expanduser()


def refuse(message: str) -> int:
    print(f"resupervise-seat: {message}", file=sys.stderr)
    return 1


def handoff_is_waiting(handoff_path: Path, state_path: Path):
    """Return (waiting, counter, note) for an unconsumed handoff."""
    # Require a counter the supervisor will consume before killing a session whose work needs recovery.
    if not handoff_path.is_file():
        return False, None, (
            f"no handoff at {handoff_path}. Ask the agent to hand off first (its handoff "
            "skill runs handoff-write-and-check-supervisor.py); nothing is killed until "
            "its work is written down."
        )

    fields = supervisor.parse_handoff_file(handoff_path)
    counter = supervisor.counter_from(fields)
    if counter is None:
        return False, None, (
            f"{handoff_path} carries no readable restart-counter, so the supervisor would "
            "not ignite from it. Leaving the seat alone."
        )

    state = supervisor.read_supervisor_state(state_path)
    consumed = state.get("consumed_counter")
    if consumed is not None and counter <= consumed:
        return False, counter, (
            f"the handoff at {handoff_path} (restart-counter {counter}) was already consumed "
            f"by a supervisor (it recorded {consumed}). Nothing is waiting; ask the agent to "
            "hand off again if it needs reincarnating."
        )

    if fields.get("dont-restart"):
        return True, counter, (
            "the handoff carries dont-restart: the supervisor will ask on the seat's terminal "
            "before starting a successor"
        )
    return True, counter, ""


def directory_occupancy_keep_reason(directory: Path):
    """Return a reason occupancy cannot be trusted, or None for a usable lsof answer."""
    if shutil.which("lsof") is None:
        return "lsof is not installed, so what is running in the seat cannot be checked"
    try:
        cwd_listing = subprocess.run(
            ["lsof", "-a", "-d", "cwd", "-F", "n"],
            capture_output=True, text=True, timeout=30, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "the occupancy check (lsof) could not be run"

    prefix = str(directory.resolve())
    reported_paths = 0
    for line in cwd_listing.stdout.splitlines():
        if line.startswith("n"):
            reported_paths += 1
            cwd = line[1:]
            if cwd == prefix or cwd.startswith(prefix + "/"):
                return None  # a live process is the session to retire
    if cwd_listing.returncode != 0:
        return (f"the occupancy check (lsof) failed with exit {cwd_listing.returncode}, "
                "so what is running in the seat cannot be trusted")
    if reported_paths == 0:
        return "the occupancy check (lsof) reported no working directories at all"
    return "no live process is rooted in the seat directory"


def run_tmux(*arguments_after_tmux, socket_name=None):
    """Run tmux, returning None if the command cannot run."""
    # Without socket_name, tmux uses $TMUX inside a session and the default socket outside one.
    if shutil.which("tmux") is None:
        return None
    socket_arguments = [] if socket_name is None else ["-L", socket_name]
    try:
        return subprocess.run(
            ["tmux", *socket_arguments, *arguments_after_tmux],
            capture_output=True, text=True, timeout=30, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def tmux_sockets_holding_seat_session(name: str) -> list:
    """Return socket names holding the seat session, in kill order."""
    # Check both seat and default servers: leaving either session alive creates a decoy seat.
    holding = []
    for socket_name in dict.fromkeys((name, "default")):
        completed = run_tmux("has-session", "-t", f"={name}", socket_name=socket_name)
        if completed is not None and completed.returncode == 0:
            holding.append(socket_name)
    return holding


def retire_seat_tmux_session(name: str):
    """Retire every session named for the seat; return (killed_sockets, failure_detail)."""
    killed_sockets = []
    for socket_name in tmux_sockets_holding_seat_session(name):
        killed = run_tmux("kill-session", "-t", f"={name}", socket_name=socket_name)
        if killed is None or killed.returncode != 0:
            detail = "tmux could not be run" if killed is None else (
                killed.stderr.strip() or "no detail")
            return killed_sockets, (f"could not kill the stale tmux session {name} "
                                    f"(server socket {socket_name}): {detail}")
        killed_sockets.append(socket_name)
    return killed_sockets, None


def launcher_for(machine: str) -> Path:
    return SCRIPT_DIRECTORY / f"launch-claude-{machine}"


BOX_SCRIPT_PATH = "$HOME/Projects/nedschorus/scripts/resupervise-seat.py"


def resupervise_box_seat(arguments) -> int:
    """Prepare the seat on ned-box, then run the launcher on the Mac."""
    # The Ubuntu launcher sends commands over ssh from the Mac; ned-box cannot resolve its own ssh alias.
    remote_arguments = ["--prepare-only", "--machine", "ubuntu"]
    # Preserve remote paths unexpanded; quote for the one remote-shell parse.
    if arguments.handoff_dir:
        remote_arguments += ["--handoff-dir", shlex.quote(arguments.handoff_dir)]
    if arguments.dry_run:
        remote_arguments.append("--dry-run")
    remote = subprocess.run(
        ["ssh", "-o", "ConnectTimeout=10", arguments.agent_box,
         f"test -f {BOX_SCRIPT_PATH} && python3 {BOX_SCRIPT_PATH} "
         f"{arguments.name} {' '.join(remote_arguments)}"],
        check=False,
    )
    if remote.returncode != 0:
        # A missing remote script means preparation never ran, not that the seat is healthy.
        missing = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=10", arguments.agent_box, f"test -f {BOX_SCRIPT_PATH}"],
            capture_output=True, text=True, check=False,
        )
        if missing.returncode != 0:
            return refuse(
                f"{BOX_SCRIPT_PATH} is not on {arguments.agent_box}. The box checkout is pulled "
                "by hand (nedschorus#45) -- pull it there, then re-run. Nothing was changed."
            )
        return refuse(
            f"the box-side checks refused (exit {remote.returncode}); nothing was launched. "
            "Their reason is printed above."
        )

    if arguments.dry_run:
        print(f"resupervise-seat: DRY RUN -- would now run launch-claude-ubuntu {arguments.name} "
              "from this Mac")
        return 0

    launcher = launcher_for("ubuntu")
    if not launcher.is_file():
        return refuse(f"no launcher beside this script at {launcher}")
    print(f"resupervise-seat: box side is clear; running {launcher.name} {arguments.name}")
    sys.stdout.flush()  # exec discards buffered output
    sys.stderr.flush()
    # Forward the checked host and handoff directory so launch targets the seat just prepared.
    environment = {**os.environ, "NEDSCHORUS_AGENT_BOX": arguments.agent_box}
    if arguments.handoff_dir:
        environment["LAUNCH_CLAUDE_SUPERVISOR_EXTRA_ARGUMENTS"] = (
            f"--handoff-dir {shlex.quote(arguments.handoff_dir)}")
    os.execve(str(launcher), [str(launcher), arguments.name], environment)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Put a supervisor back on an unsupervised seat, by retiring its session.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("name", help="the seat's name -- its tmux session, directory and handoff files")
    parser.add_argument(
        "--machine", default="mac", choices=("mac", "ubuntu"),
        help="which launcher seats the successor (default: mac)",
    )
    # Empty defaults distinguish explicit paths from machine-local defaults; never forward a Mac-expanded default.
    parser.add_argument("--handoff-dir", default="",
                        help="handoff directory on this machine only, not committed "
                             "(default ~/.claude/handoffs)")
    parser.add_argument("--agents-root", default="",
                        help="where seat directories live, for --machine mac only "
                             "(default $NEDSCHORUS_AGENTS_ROOT, else ~/agents); a box "
                             "seat is always ~/agents/<name> on the box")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="report whether the seat is recoverable and what would happen; change nothing",
    )
    parser.add_argument(
        "--prepare-only", action="store_true",
        help="do steps 1-4 (checks and clearing the stale tmux session) and stop without "
             "launching; how --machine ubuntu reaches the box, and usable by hand",
    )
    parser.add_argument(
        "--agent-box", default="ned",
        help="ssh alias of the Ubuntu agent box, as launch-claude-ubuntu uses it",
    )
    arguments = parser.parse_args(argv)

    if arguments.machine == "ubuntu" and arguments.agents_root:
        print("resupervise-seat: with --machine ubuntu, re-run without --agents-root: "
              "a box seat is always ~/agents/<name> on the box and cannot be moved "
              "from the Mac. Nothing was changed.", file=sys.stderr)
        return 2

    # Run checks where the seat's handoff, supervisor state, and tmux session live.
    if arguments.machine == "ubuntu" and not arguments.prepare_only:
        return resupervise_box_seat(arguments)

    handoff_directory = Path(arguments.handoff_dir or "~/.claude/handoffs").expanduser()
    handoff_path = supervisor.handoff_file_path(handoff_directory, arguments.name)
    state_path = supervisor.supervisor_state_path(handoff_directory, arguments.name)
    agents_root = (Path(arguments.agents_root).expanduser() if arguments.agents_root
                   else default_agents_root())
    seat_directory = agents_root / arguments.name

    # Refuse before killing anything when a supervisor already owns the seat.
    alive, explanation = supervisor.supervisor_liveness(state_path)
    if alive:
        # alive can be assumed when ps fails; preserve the explanation distinguishing that case.
        return refuse(
            f"{arguments.name} already has a supervisor watching it ({explanation}). "
            "Nothing to recover -- if it is watching, it reincarnates the seat "
            "on its own handoff."
        )

    waiting, counter, note = handoff_is_waiting(handoff_path, state_path)
    if not waiting:
        return refuse(note)
    if note:
        print(f"resupervise-seat: {note}")
    print(f"resupervise-seat: {explanation}")
    print(f"resupervise-seat: an unconsumed handoff is waiting at {handoff_path} "
          f"(restart-counter {counter})")

    occupancy_note = directory_occupancy_keep_reason(seat_directory)
    if occupancy_note is None:
        print(f"resupervise-seat: a live process is rooted in {seat_directory} -- "
              "the session being retired. Anything it did since writing the handoff "
              "ends with it.")
    else:
        # The session may already have exited, so absence alone is not fatal.
        print(f"resupervise-seat: {occupancy_note}")

    launcher = launcher_for(arguments.machine)
    if not arguments.prepare_only and not launcher.is_file():
        return refuse(
            f"no launcher beside this script at {launcher} -- run the copy inside a "
            "nedschorus checkout"
        )

    # Never kill the operator's own tmux session mid-recovery. Without $TMUX, display-message can select an unrelated session.
    # Omit -L so tmux resolves the surrounding server through $TMUX.
    if os.environ.get("TMUX"):
        current_session = run_tmux("display-message", "-p", "#{session_name}")
        if (current_session is not None and current_session.returncode == 0
                and current_session.stdout.strip() == arguments.name):
            return refuse(
                f"this command is running inside the {arguments.name} tmux session, and clearing "
                "that session would kill the terminal doing the clearing. Run it from another "
                "window, or from outside tmux."
            )

    if arguments.dry_run:
        stale_sockets = tmux_sockets_holding_seat_session(arguments.name)
        would_launch = ("stop there (--prepare-only)" if arguments.prepare_only
                        else f"run {launcher} {arguments.name}")
        print(f"resupervise-seat: DRY RUN -- would "
              f"{'kill the stale tmux session and ' if stale_sockets else ''}{would_launch}")
        return 0

    # tmux new-session -A attaches to an existing session instead of starting the supervisor; retire the old session first.
    killed_sockets, retire_failure = retire_seat_tmux_session(arguments.name)
    for socket_name in killed_sockets:
        print(f"resupervise-seat: killed the stale tmux session {arguments.name} "
              f"(server socket {socket_name})")
    if retire_failure is not None:
        return refuse(retire_failure)
    if not killed_sockets:
        print(f"resupervise-seat: no tmux session named {arguments.name} to clear "
              "on its own server or the default one")

    if arguments.prepare_only:
        print(f"resupervise-seat: the {arguments.name} seat is clear and its handoff is waiting; "
              "launch it from the machine its launcher runs on")
        return 0

    print(f"resupervise-seat: running {launcher.name} {arguments.name} -- the supervisor "
          "will ignite from the waiting handoff")
    # exec hands this terminal to the successor; a supervisor without a terminal cannot reincarnate.
    # Flush first because exec discards Python's buffered output.
    sys.stdout.flush()
    sys.stderr.flush()
    # Forward the directories checked above so launch cannot switch seats; quote for the launcher's one shell parse.
    environment = dict(os.environ)
    environment["NEDSCHORUS_AGENTS_ROOT"] = str(agents_root)
    environment["LAUNCH_CLAUDE_SUPERVISOR_EXTRA_ARGUMENTS"] = (
        f"--handoff-dir {shlex.quote(str(handoff_directory))}")
    os.execve(str(launcher), [str(launcher), arguments.name], environment)


if __name__ == "__main__":
    sys.exit(main())
