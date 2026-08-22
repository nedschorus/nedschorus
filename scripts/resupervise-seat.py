#!/usr/bin/env python3
"""Put a supervisor back on a seat whose agent is running unsupervised.

An agent session recycles itself only when a supervisor is watching it: the
supervisor waits for the handoff file, kills the spent session, and starts the
successor on the same terminal. A session started any other way -- `claude` or
`claude --continue` typed by hand -- has no supervisor, so it can never recycle,
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
     window and no decoy is left behind.
  5. Run the seat's launcher. The supervisor boots, finds the unconsumed handoff,
     and ignites the successor from it (handoff-supervisor.py's boot-ignition
     path, live since 2026-08-14).

The successor is a fresh session carrying the retiring one's handoff and dialog
extract -- the ordinary recycle, not a continuation of the running process.
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

Usage:
  resupervise-seat.py <name> [--machine mac|ubuntu] [--dry-run]
                             [--handoff-dir <path>] [--agents-root <path>]
  resupervise-seat.py <name> --prepare-only        (steps 1-4; run on the seat's
                                                    machine, then launch there)

Exit codes: 0 the seat was relaunched (or --dry-run / --prepare-only found it
ready), 1 refused because the seat is not in a recoverable state, 2 bad
invocation.
"""

import argparse
import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

_supervisor_spec = importlib.util.spec_from_file_location(
    "handoff_supervisor", Path(__file__).with_name("handoff-supervisor.py")
)
supervisor = importlib.util.module_from_spec(_supervisor_spec)
_supervisor_spec.loader.exec_module(supervisor)

SCRIPT_DIRECTORY = Path(__file__).resolve().parent
AGENTS_ROOT_DEFAULT = Path.home() / "agents"


def refuse(message: str) -> int:
    print(f"resupervise-seat: {message}", file=sys.stderr)
    return 1


def handoff_is_waiting(handoff_path: Path, state_path: Path):
    """Return (True, counter, note) when an unconsumed handoff is waiting.

    Waiting means the supervisor's boot-ignition will act on this file: it
    exists, it carries a readable restart-counter, and that counter is newer
    than the one the last supervisor recorded as consumed. Killing the seat on
    anything less would destroy a running session whose work has not been
    handed off -- the one outcome this script must never produce.
    """
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
            "hand off again if it needs recycling."
        )

    if fields.get("dont-restart"):
        return True, counter, (
            "the handoff carries dont-restart: the supervisor will ask on the seat's terminal "
            "before starting a successor"
        )
    return True, counter, ""


def directory_occupancy_keep_reason(directory: Path):
    """Why this seat directory must be left alone, or None when provably vacant.

    Same contract as clean-worktrees.py's vacancy check, and for the same
    reason: vacancy is proven, never assumed. An unusable lsof answer -- missing,
    unrunnable, nonzero exit, or a listing naming no working directories at all
    -- keeps the seat. A path match keeps regardless of how the run exited, since
    a partial listing that names this directory is still positive evidence.

    Here the stakes are inverted from the reaper's: a match means the SESSION we
    intend to retire is alive, which is the normal case. This check exists to
    report what is running, and to refuse when the answer cannot be trusted.
    """
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
                return None  # a live process is rooted there: the session to retire
    if cwd_listing.returncode != 0:
        return (f"the occupancy check (lsof) failed with exit {cwd_listing.returncode}, "
                "so what is running in the seat cannot be trusted")
    if reported_paths == 0:
        return "the occupancy check (lsof) reported no working directories at all"
    return "no live process is rooted in the seat directory"


def run_tmux(*arguments_after_tmux):
    """Run one tmux command, or return None when tmux cannot be run at all.

    Every tmux call here goes through this. subprocess raises FileNotFoundError
    for a missing binary rather than returning a failure code, so an unguarded
    call crashes on a machine without tmux -- including under --dry-run and
    --prepare-only, which promise to change nothing and must not traceback.
    The lsof check above already had this guard; tmux never got the sibling
    treatment.
    """
    if shutil.which("tmux") is None:
        return None
    try:
        return subprocess.run(
            ["tmux", *arguments_after_tmux],
            capture_output=True, text=True, timeout=30, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def tmux_session_exists(name: str) -> bool:
    completed = run_tmux("has-session", "-t", f"={name}")
    return completed is not None and completed.returncode == 0


def launcher_for(machine: str) -> Path:
    return SCRIPT_DIRECTORY / f"launch-claude-{machine}"


BOX_SCRIPT_PATH = "$HOME/Projects/nedschorus/scripts/resupervise-seat.py"


def resupervise_box_seat(arguments) -> int:
    """Run the checks and the stale-session kill ON THE BOX, then launch here.

    The launcher for a box seat is a Mac-side script -- it composes a command
    and sends it over ssh, and the box cannot resolve its own ssh alias -- so
    the two halves genuinely run on different machines. The box half is this
    same script with --prepare-only, which is why its refusals reach the
    operator unchanged: nothing is re-judged on this side.
    """
    remote_arguments = ["--prepare-only", "--machine", "ubuntu"]
    if arguments.dry_run:
        remote_arguments.append("--dry-run")
    remote = subprocess.run(
        ["ssh", "-o", "ConnectTimeout=10", arguments.agent_box,
         f"test -f {BOX_SCRIPT_PATH} && python3 {BOX_SCRIPT_PATH} "
         f"{arguments.name} {' '.join(remote_arguments)}"],
        check=False,
    )
    if remote.returncode != 0:
        # A missing script on the box is the one failure worth naming, because
        # the box checkout is pulled by hand (nedschorus#45) and an operator
        # would otherwise read "refused" as "the seat is fine".
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
    sys.stdout.flush()  # exec discards the buffer; see the note on the mac path
    sys.stderr.flush()
    # Carry --agent-box into the launcher, which reads it as NEDSCHORUS_AGENT_BOX
    # and otherwise defaults to its own alias. Without this the flag steers both
    # ssh checks above and is then ignored at the decisive step: a non-default
    # box would be cleared, and the successor launched on the default one.
    os.execve(
        str(launcher),
        [str(launcher), arguments.name],
        {**os.environ, "NEDSCHORUS_AGENT_BOX": arguments.agent_box},
    )


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
    parser.add_argument("--handoff-dir", default="~/.claude/handoffs",
                        help="machine-local handoff directory")
    parser.add_argument("--agents-root", default=str(AGENTS_ROOT_DEFAULT),
                        help="where seat directories live (default: ~/agents)")
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

    # A box seat's handoff file, supervisor state and tmux session all live on
    # the box. Reading Mac state and killing a Mac tmux session for a box seat
    # would check the wrong machine and destroy the wrong window, so the checks
    # go where the state is: this same script, --prepare-only, over ssh.
    if arguments.machine == "ubuntu" and not arguments.prepare_only:
        return resupervise_box_seat(arguments)

    handoff_directory = Path(arguments.handoff_dir).expanduser()
    handoff_path = handoff_directory / f"{arguments.name}-handoff.md"
    state_path = handoff_directory / f"{arguments.name}-supervisor-state.json"
    seat_directory = Path(arguments.agents_root).expanduser() / arguments.name

    # A live supervisor means the seat is not in the state this script repairs.
    # Its own lock would refuse the second copy anyway; refusing here says why,
    # before anything is killed.
    alive, explanation = supervisor.supervisor_liveness(state_path)
    if alive:
        return refuse(
            f"{arguments.name} already has a supervisor watching it ({explanation}). "
            "Nothing to recover -- it will recycle on its own handoff."
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
        # Not fatal on its own: the session may already have exited, which is
        # the easiest case of all. Report it so the operator sees what state
        # the seat was actually in.
        print(f"resupervise-seat: {occupancy_note}")

    launcher = launcher_for(arguments.machine)
    if not arguments.prepare_only and not launcher.is_file():
        return refuse(
            f"no launcher beside this script at {launcher} -- run the copy inside a "
            "nedschorus checkout"
        )

    # Killing the tmux session this script is running inside would take the
    # operator's own terminal down mid-procedure and seat no successor. It
    # happens whenever recovery is attempted from a shell in the very seat
    # being recovered -- which is exactly where an operator lands after a
    # supervisor exits, since the launcher leaves a shell in the seat.
    current_session = run_tmux("display-message", "-p", "#{session_name}")
    if (current_session is not None and current_session.returncode == 0
            and current_session.stdout.strip() == arguments.name):
        return refuse(
            f"this command is running inside the {arguments.name} tmux session, and clearing "
            "that session would kill the terminal doing the clearing. Run it from another "
            "window, or from outside tmux."
        )

    stale_session = tmux_session_exists(arguments.name)
    if arguments.dry_run:
        would_launch = ("stop there (--prepare-only)" if arguments.prepare_only
                        else f"run {launcher} {arguments.name}")
        print(f"resupervise-seat: DRY RUN -- would "
              f"{'kill the stale tmux session and ' if stale_session else ''}{would_launch}")
        return 0

    # The stale session must go before the launcher runs: `tmux new-session -A`
    # ATTACHES to an existing name rather than starting the supervisor, so
    # leaving it would drop the operator into the dead seat's shell and seat no
    # successor at all. Killing it is also what keeps the recovered seat to one
    # window -- the decoy of 2026-08-18 was a second window left behind.
    if stale_session:
        killed = run_tmux("kill-session", "-t", f"={arguments.name}")
        if killed is None or killed.returncode != 0:
            detail = "tmux could not be run" if killed is None else (
                killed.stderr.strip() or "no detail")
            return refuse(
                f"could not kill the stale tmux session {arguments.name}: {detail}"
            )
        print(f"resupervise-seat: killed the stale tmux session {arguments.name}")
    else:
        print(f"resupervise-seat: no tmux session named {arguments.name} to clear")

    if arguments.prepare_only:
        print(f"resupervise-seat: the {arguments.name} seat is clear and its handoff is waiting; "
              "launch it from the machine its launcher runs on")
        return 0

    print(f"resupervise-seat: running {launcher.name} {arguments.name} -- the supervisor "
          "will ignite from the waiting handoff")
    # exec, not a child: this terminal becomes the successor's seat, and a
    # supervisor with no terminal refuses to recycle at all
    # (handoff-supervisor.py, ruled 2026-08-14). Replacing this process hands
    # the terminal over cleanly and leaves no python waiting behind the seat.
    # Flush first: exec discards whatever python still holds in its buffer, and
    # stdout is block-buffered whenever it is not a terminal -- so a piped or
    # logged run silently lost every line above, which is the whole record of
    # what was killed and why (measured 2026-08-19).
    sys.stdout.flush()
    sys.stderr.flush()
    os.execv(str(launcher), [str(launcher), arguments.name])


if __name__ == "__main__":
    sys.exit(main())
