#!/usr/bin/env python3
"""Skip agent-binary updates when another launcher or supervisor is updating.

macOS has no flock binary; all callers must share Python's flock lock.
Keep the timeout inside the lock holder so timeout handling cannot orphan an unlocked update."""

import argparse
import errno
import fcntl
import os
import subprocess
import sys
from pathlib import Path

AGENT_BINARY_UPDATE_LOCK_PATH = "~/.local/state/claude/agent-binary-update.lock"


def agent_binary_update_lock_path() -> Path:
    """Return the lock path using the current HOME."""
    # Keep the file outside Claude's locks/ directory, whose pid-lock handling may reap files.
    # Never unlink a flock file: another process could hold the old inode while a newcomer locks a new one.
    return Path(os.path.expanduser(AGENT_BINARY_UPDATE_LOCK_PATH))


def run_agent_binary_update_under_lock(command, timeout_seconds, program_name,
                                       lock_path=None) -> int:
    """Return the update status, or 0 when disabled or another update holds the lock."""
    if not timeout_seconds:
        return 0
    lock_path = Path(lock_path) if lock_path else agent_binary_update_lock_path()
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_file = open(lock_path, "a")
    except OSError as error:
        print(f"{program_name}: the update lock {lock_path} could not be opened "
              f"({error}); skipping the update and launching on the installed version",
              file=sys.stderr)
        return 1
    with lock_file:
        try:
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            if error.errno in (errno.EWOULDBLOCK, errno.EAGAIN, errno.EACCES):
                print("Another claude update is running; this launch uses the claude already installed.",
                      file=sys.stderr)
                return 0
            print(f"{program_name}: the update lock {lock_path} could not be "
                  f"taken ({error}); skipping the update and launching on "
                  f"the installed version", file=sys.stderr)
            return 1
        # The child must not inherit the lock: descendants left running would otherwise keep the lock held.
        try:
            return subprocess.run(command, timeout=timeout_seconds).returncode
        except subprocess.TimeoutExpired:
            print(f"{program_name}: the update was still running after "
                  f"{timeout_seconds}s and was stopped; launching on the installed version",
                  file=sys.stderr)
            return 124
        except OSError as error:
            print(f"{program_name}: the update could not be run ({error}); "
                  f"launching on the installed version", file=sys.stderr)
            return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="agent-binary-update-under-lock",
        description="Run an agent-binary update while holding this machine's "
                    "update lock; skip immediately if another update holds the lock.")
    parser.add_argument("--program-name", required=True,
                        help="the prefix for failure messages")
    parser.add_argument("--timeout-seconds", type=int, required=True,
                        help="the update execution timeout; 0 skips the update")
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
