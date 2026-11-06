#!/usr/bin/env python3
"""Delete each agent-seat terminal capture whose last write is more than seven days old.

    python3 <this file> [--dry-run] [--captures-directory DIR ...]

The terminal captures are the files agent-seat-terminal-captures-common.py, beside this file,
says handoff-supervisor.py writes: <captures directory>/<agent-seat>/<UTC start>-<agent-seat>-terminal-capture.log.
Which captures directories a run deletes from, unless --captures-directory replaces the list:
- on ned-box, every machine's copy in the log-store,
  /home/nedlern/nedschorus-logs/agent-session-files-by-machine/*/agent-seat-terminal-captures,
  because the transcript mirror never deletes, so the Mac's copy there outlives the Mac's own;
- elsewhere, which is the Mac, this machine's own, ~/.claude/agent-seat-terminal-captures.

A file is deleted when its modification time is more than seven days ago. The start time in its
name is not used: a supervisor that has run for more than seven days is still writing its file,
and deleting it would lose the rest of that terminal capture. An agent-seat directory this run emptied is
removed. Anything else in a captures directory is left alone.

OUTPUT. `deleted <file>` for each file deleted, or `would delete <file>` with --dry-run, then one
summary line. A captures directory that does not exist is not a failure: nothing has been
captured there yet. A file or directory that cannot be deleted or read is a FAILED line naming it
and the error; the run goes on with the rest and exits 1. Exit 0 otherwise.

SCHEDULE. Once a day on each machine, installed by
nc-systems/general-tools/install-scheduled-jobs-on-this-machine.py from the table beside it,
scheduled-jobs-on-each-machine.json, where a change to the schedule is made: by cron on ned-box,
and by launchd on the Mac, so a run missed while the Mac sleeps happens at its next wake.

  ned-box: one cron line.

    45 5 * * * /usr/bin/python3 /home/nedlern/Projects/nedschorus/nc-systems/handoff/agent-seat-terminal-captures-older-than-seven-days-delete.py >> /home/nedlern/.claude/agent-seat-terminal-captures-older-than-seven-days-delete.log 2>&1

  Mac: the launchd job com.nedschorus.agent-seat-terminal-captures-older-than-seven-days-delete,
  at 05:45.
"""

import argparse
import importlib.util
import os
import sys
import time
from pathlib import Path

_captures_spec = importlib.util.spec_from_file_location(
    "agent_seat_terminal_captures_common",
    Path(__file__).resolve().with_name("agent-seat-terminal-captures-common.py"))
captures = importlib.util.module_from_spec(_captures_spec)
_captures_spec.loader.exec_module(captures)

PROGRAM = "agent-seat-terminal-captures-older-than-seven-days-delete"
SECONDS_PER_DAY = 86_400
# Messages follow docs/nedschorus-wiki/nedschorus-how-to-write-an-agent-facing-message-such-as-a-hook-refusal-or-script-error.md.
FAILED_PATH_KEPT_UNTIL_A_RUN_CAN_DELETE_IT_LINE = (
    "The path stays until a run can delete it; the run went on with the other captures. "
    "If the same path fails on the next day's run too, run `ls -ld` on the path and on its "
    "directory, on the machine whose log holds this line, where the path is; if either is not "
    "writable by that machine's own user, which runs this program, tell the user the path and what "
    "`ls -ld` showed. A subagent tells the agent that dispatched it instead.")


def agent_seat_terminal_captures_directories_this_machine_deletes_old_captures_from_find(hostname=None) -> list:
    if (captures.this_machine_is_the_log_store_host(hostname)
            and not os.environ.get(captures.AGENT_SEAT_TERMINAL_CAPTURES_DESTINATION_ENVIRONMENT_VARIABLE)):
        return sorted(captures.LOG_STORE_AGENT_SESSION_FILES_BY_MACHINE_DIRECTORY.glob(
            f"*/{captures.AGENT_SEAT_TERMINAL_CAPTURES_DIRECTORY_NAME}"))
    return [captures.agent_seat_terminal_captures_directory_on_this_machine_find(hostname)]


def delete_old_captures(directory: Path, oldest_kept_modification_time: float, dry_run: bool):
    """Return (deleted count, failure count) for one captures directory."""
    deleted = failed = 0
    if not directory.is_dir():
        return deleted, failed
    try:
        seat_directories = sorted(path for path in directory.iterdir() if path.is_dir())
    except OSError as error:
        print(f"FAILED: could not list {directory} ({error}). {FAILED_PATH_KEPT_UNTIL_A_RUN_CAN_DELETE_IT_LINE}")
        return 0, 1
    for seat_directory in seat_directories:
        try:
            files = sorted(path for path in seat_directory.iterdir() if path.is_file())
        except OSError as error:
            print(f"FAILED: could not list {seat_directory} ({error}). {FAILED_PATH_KEPT_UNTIL_A_RUN_CAN_DELETE_IT_LINE}")
            failed += 1
            continue
        for path in files:
            try:
                if path.stat().st_mtime >= oldest_kept_modification_time:
                    continue
                if dry_run:
                    print(f"would delete {path}")
                else:
                    path.unlink()
                    print(f"deleted {path}")
                deleted += 1
            except OSError as error:
                print(f"FAILED: could not delete {path} ({error}). {FAILED_PATH_KEPT_UNTIL_A_RUN_CAN_DELETE_IT_LINE}")
                failed += 1
        if not dry_run and deleted and not any(seat_directory.iterdir()):
            try:
                seat_directory.rmdir()
            except OSError as error:
                print(f"FAILED: could not remove the emptied directory {seat_directory} ({error}). "
                      f"{FAILED_PATH_KEPT_UNTIL_A_RUN_CAN_DELETE_IT_LINE}")
                failed += 1
    return deleted, failed


def main(argv=None, now=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="print what would be deleted; delete nothing")
    parser.add_argument("--captures-directory", action="append", type=Path,
                        help="a captures directory to delete from; repeat for several; "
                             "replaces this machine's own list")
    arguments = parser.parse_args(argv)
    directories = arguments.captures_directory or agent_seat_terminal_captures_directories_this_machine_deletes_old_captures_from_find()
    oldest_kept_modification_time = (time.time() if now is None else now) - (
        captures.AGENT_SEAT_TERMINAL_CAPTURES_KEPT_DAYS * SECONDS_PER_DAY)
    deleted = failed = 0
    for directory in directories:
        directory_deleted, directory_failed = delete_old_captures(
            directory, oldest_kept_modification_time, arguments.dry_run)
        deleted += directory_deleted
        failed += directory_failed
    print(f"{PROGRAM}: {'would delete' if arguments.dry_run else 'deleted'} {deleted} capture(s) "
          f"older than {captures.AGENT_SEAT_TERMINAL_CAPTURES_KEPT_DAYS} days from "
          f"{', '.join(str(directory) for directory in directories) or 'no captures directory'}"
          f"{f'; {failed} FAILED' if failed else ''}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
