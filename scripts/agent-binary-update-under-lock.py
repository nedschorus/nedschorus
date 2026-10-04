#!/usr/bin/env python3
"""Serialize agent-binary updates across launchers and supervisors.

macOS has no flock binary; all callers must share Python's flock lock.
Keep the timeout inside the lock holder so timeout handling cannot orphan an unlocked update."""

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
    """Return the lock path using the current HOME."""
    # Keep the file outside Claude's locks/ directory, whose pid-lock handling may reap files.
    # Never unlink a flock file: waiters could hold the old inode while a newcomer locks a new one.
    return Path(os.path.expanduser(AGENT_BINARY_UPDATE_LOCK_PATH))


def run_agent_binary_update_under_lock(command, timeout_seconds, program_name,
                                       lock_path=None) -> int:
    """Return the command's exit status, or 0 on lock or execution problems."""
    # Waiting and execution share one timeout budget so lock contention cannot extend launch delay.
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
        # The child must not inherit the lock: descendants left running would otherwise keep the lock held.
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
