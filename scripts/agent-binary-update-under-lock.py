#!/usr/bin/env python3
"""Run one `claude update` at a time on this machine, under a shared lock.

    python3 scripts/agent-binary-update-under-lock.py \\
        --program-name launch-claude-mac --timeout-seconds 120 -- claude update

WHY THE UPDATES ARE SERIALIZED (user-approved 2026-09-22, superwalk item 2).
Three places in the fleet run `claude update`: both launchers
(scripts/launch-claude-mac, scripts/launch-claude-ubuntu) and
handoff-supervisor.py's update_agent_binary, before every session it
launches. The double update, launcher then supervisor, is deliberate (PR "A
handoff restart updates the agent binary, as a launcher launch does",
https://github.com/nedschorus/nedschorus/pull/645). At a login restart,
restart-live-seats-at-login / recover-crashed-seats.py brings seats back one
at a time but moves on about 6 s after each supervisor's lock appears
(SEAT_SETTLE_SECONDS), and each supervisor's first launch then runs `claude
update`, a download of about 217 MB. So two updates on one machine can
overlap, and nothing serialized them. Whether `claude update` tolerates a
concurrent run is unknown; the plausible harm is a half-written binary or
symlink that breaks the next launch. Every caller now goes through this one
file, so every update on a machine waits for the one before it.

WHY fcntl.flock IN PYTHON, AND ONE HELPER FOR ALL THREE CALLERS. The
supervisor and the launchers must take the SAME kind of lock, or they do not
exclude each other: a flock and a mkdir-lock never see each other. macOS
ships no `flock` binary and its bash is 3.2, so the launchers reach the lock
through this file, run with the python3 both of them already require, and
the supervisor imports the same function. A flock is released by the kernel
when its holder dies, however it dies, so there is no stale lock to detect
and no pid-liveness check to get wrong on two operating systems -- the part
a mkdir-lock would need and could get wrong.

WHY THIS FILE ALSO OWNS THE TIMEOUT. The launchers used to wrap `claude
update` in `perl -e 'alarm ...'` (Mac) and GNU `timeout` (box). Kept outside
this helper, either would kill the Python parent and orphan a still-running
`claude update` whose lock had just been released -- perl's exec avoided that
only because perl became claude. So the helper runs the command itself, with
subprocess.run's timeout, exactly as the supervisor always did.

ONE BUDGET COVERS THE WAIT AND THE RUN. --timeout-seconds bounds the whole
step: time spent waiting for another update comes out of the time the
command may run. A launch is therefore delayed no longer than it was before
the lock existed. The update that waited behind another is almost always a
no-op once it gets the lock, because the machine is already current.

WHY THE LOCK FILE LIVES WHERE IT DOES. ~/.local/state/claude/ is the native
installer's own state directory on both machines (measured 2026-09-22). Its
locks/ subdirectory is Claude Code's, holding JSON pid-locks named
<version>.lock, so this file sits beside that directory, never inside it,
where Claude Code's own lock handling could read or reap it. The lock file
is never unlinked: removing a flock'd file while another process waits on it
would let a third process lock a new file of the same name.

WHAT IT REPORTS. Exactly the cases the caller cannot see for itself: it had
to wait, it gave up waiting, it killed the command at the limit, or the
command could not be started. A command that runs to completion prints its
own diagnosis, and a paraphrase here would add nothing (the 2026-08-31
Homebrew refusal exited 0, recorded in scripts/launch-claude-mac). Every
handled path exits 0 and a completed command's own status passes through, so
an update never blocks a launch.

A timeout of 0 skips the update entirely and takes no lock -- the
supervisor's --agent-update-timeout-seconds 0, which the test suites use.
"""

import argparse
import errno
import fcntl
import os
import subprocess
import sys
import time
from pathlib import Path

AGENT_BINARY_UPDATE_LOCK_PATH = "~/.local/state/claude/agent-binary-update.lock"

LOCK_POLL_INTERVAL_SECONDS = 0.25


def agent_binary_update_lock_path() -> Path:
    """The lock file, resolved against $HOME at call time, so a sandboxed
    HOME in a test suite holds its own lock rather than the machine's."""
    return Path(os.path.expanduser(AGENT_BINARY_UPDATE_LOCK_PATH))


def run_agent_binary_update_under_lock(command, timeout_seconds, program_name,
                                       lock_path=None) -> int:
    """Run command while holding the machine's agent-binary update lock.

    Returns the command's own exit status when it ran to completion, else 0.
    Never raises for a lock or a command problem: the caller launches a
    session next whatever happens here.
    """
    if not timeout_seconds:
        return 0
    deadline = time.monotonic() + timeout_seconds
    lock_path = Path(lock_path) if lock_path else agent_binary_update_lock_path()
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_file = open(lock_path, "a")
    except OSError as error:
        print(f"{program_name}: the update lock {lock_path} could not be opened "
              f"({error}); skipping the update and launching on the installed version",
              file=sys.stderr)
        return 0
    with lock_file:
        said_waiting = False
        while True:
            try:
                fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError as error:
                if error.errno not in (errno.EWOULDBLOCK, errno.EAGAIN, errno.EACCES):
                    print(f"{program_name}: the update lock {lock_path} could not be "
                          f"taken ({error}); skipping the update and launching on "
                          f"the installed version", file=sys.stderr)
                    return 0
            if time.monotonic() >= deadline:
                print(f"{program_name}: another update on this machine was still "
                      f"running after {timeout_seconds}s; skipping this update and "
                      f"launching on the installed version", file=sys.stderr)
                return 0
            if not said_waiting:
                print(f"{program_name}: waiting for another update on this machine "
                      f"to finish", file=sys.stderr)
                said_waiting = True
            time.sleep(LOCK_POLL_INTERVAL_SECONDS)
        # The lock is held from here until lock_file closes. The command does
        # not inherit it (subprocess closes descriptors by default), so a
        # process the update leaves behind cannot keep the lock.
        remaining_seconds = max(deadline - time.monotonic(), 0.001)
        try:
            return subprocess.run(command, timeout=remaining_seconds).returncode
        except subprocess.TimeoutExpired:
            print(f"{program_name}: the update was still running after "
                  f"{timeout_seconds}s and was stopped; launching on the installed version",
                  file=sys.stderr)
            return 0
        except OSError as error:
            print(f"{program_name}: the update could not be run ({error}); "
                  f"launching on the installed version", file=sys.stderr)
            return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="agent-binary-update-under-lock",
        description="Run an agent-binary update while holding this machine's "
                    "update lock, within one time budget for waiting and running.")
    parser.add_argument("--program-name", required=True,
                        help="the prefix for every line this prints")
    parser.add_argument("--timeout-seconds", type=int, required=True,
                        help="the budget for waiting and running together; 0 skips the update")
    parser.add_argument("command", nargs=argparse.REMAINDER,
                        help="-- then the update command, e.g. -- claude update")
    arguments = parser.parse_args()
    command = arguments.command
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        parser.error("give the update command after --")
    return run_agent_binary_update_under_lock(
        command, arguments.timeout_seconds, arguments.program_name)


if __name__ == "__main__":
    sys.exit(main())
