#!/usr/bin/env python3
"""Wait until no process has a Claude Code background command's output file open for writing.

When Claude Code moves a Bash command to the background, it names the file the
command's output goes to. The command's shell and every process it starts hold
that file open for writing until they exit, so the command has ended once no
process does. A loop on `pgrep -f <pattern>` cannot tell this, because the
pattern also matches the command line of the shell running the loop.

Run: python3 <this file> <output file> [--time-limit-seconds N]

Exits 0 once no process holds the file open for writing. Exits 1 when the time
limit runs out while a process still does, which may be up to one poll
interval early, since a sleep that would reach the limit is not begun;
running the same command again keeps waiting. Exits 2, saying why, when the file does not exist, when no
writer is seen at the first look, when the time limit runs out during the
first look, or when the writers cannot be listed. No
writer at the first look is never read as "finished": the command may have
ended already, or its processes may be hidden from this program, as a process
in another process namespace is.

Writers are found through /proc/<pid>/fd and /proc/<pid>/fdinfo on Linux, and
through lsof on macOS. No look starts after the time limit, and each lsof
look is cut to the time that remains; a /proc look is not cut, as it takes
well under a second. A process that exits during a scan, or whose open files
this program may not read, is skipped, so a writer owned by another user is
not seen. A process that opens the file anew after every writer has exited is
not waited for. The program only reads: it sends no signal and changes no file.
"""

import argparse
import os
import re
import subprocess
import sys
import time
from pathlib import Path

# The Bash tool ends a command after 120 seconds unless its timeout is set, so the default
# ends the wait first, with this program's message rather than the tool's.
DEFAULT_TIME_LIMIT_SECONDS = 110
POLL_SECONDS = 5
LSOF_TIMEOUT_SECONDS = 30

EXIT_NO_WRITER_LEFT = 0
EXIT_TIME_LIMIT_REACHED = 1
EXIT_CANNOT_WAIT = 2

FDINFO_FLAGS_LINE = re.compile(r"^flags:\s*([0-7]+)\s*$", re.MULTILINE)
WRITE_ACCESS_MODES = (os.O_WRONLY, os.O_RDWR)
LSOF_WRITE_ACCESS_LETTERS = ("w", "u")


class WritersCannotBeListed(Exception):
    """The processes that hold a file open cannot be listed on this machine."""


class WritersLookTimeLimitReached(Exception):
    """The time limit ran out before the processes that hold a file open were listed."""


def linux_processes_writing_file(path, seconds_left=None, proc_root=Path("/proc")):
    """Return the process ids that hold path open for writing, read from /proc; seconds_left is unused."""
    try:
        entries = os.listdir(proc_root)
    except OSError as error:
        raise WritersCannotBeListed(f"{proc_root} cannot be read: {error}") from error
    writers = set()
    for entry in sorted(entries):
        if not entry.isdigit():
            continue
        process = Path(proc_root) / entry
        try:
            descriptors = os.listdir(process / "fd")
        except OSError:
            continue
        for descriptor in sorted(descriptors):
            try:
                if os.readlink(process / "fd" / descriptor) != path:
                    continue
                fdinfo = (process / "fdinfo" / descriptor).read_text()
            except OSError:
                continue
            flags = FDINFO_FLAGS_LINE.search(fdinfo)
            if flags is None:
                raise WritersCannotBeListed(
                    f"{process / 'fdinfo' / descriptor} has no flags line: {fdinfo!r}")
            if int(flags.group(1), 8) & os.O_ACCMODE in WRITE_ACCESS_MODES:
                writers.add(int(entry))
                break
    return writers


def macos_processes_writing_file(path, seconds_left=LSOF_TIMEOUT_SECONDS, runner=subprocess.run):
    """Return the process ids that hold path open for writing, read from lsof within seconds_left."""
    timeout = min(LSOF_TIMEOUT_SECONDS, seconds_left)
    try:
        completed = runner(["lsof", "-w", "-F", "pa", "--", path], capture_output=True, text=True,
                           timeout=timeout, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired as error:
        if seconds_left < LSOF_TIMEOUT_SECONDS:
            raise WritersLookTimeLimitReached(
                "lsof had not listed them when the time limit ran out") from error
        raise WritersCannotBeListed(f"lsof could not run: {error}") from error
    except (OSError, subprocess.SubprocessError) as error:
        raise WritersCannotBeListed(f"lsof could not run: {error}") from error
    # lsof exits 1, printing nothing, when no process has the file open.
    if completed.returncode not in (0, 1) or completed.stderr.strip():
        raise WritersCannotBeListed(
            f"lsof exited {completed.returncode}: {completed.stderr.strip()}")
    writers = set()
    process_id = None
    for line in completed.stdout.splitlines():
        if line.startswith("p"):
            process_id = int(line[1:])
        elif line.startswith("a") and any(letter in line[1:] for letter in LSOF_WRITE_ACCESS_LETTERS):
            writers.add(process_id)
    return writers


def processes_writing_file_lister(platform=sys.platform):
    return macos_processes_writing_file if platform == "darwin" else linux_processes_writing_file


def wait_until_no_process_writes(path, time_limit_seconds, list_writers,
                                 clock=time.monotonic, sleep=time.sleep):
    """Return (exit code, message) once no process writes path, or the wait cannot go on."""
    if not os.path.exists(path):
        return EXIT_CANNOT_WAIT, (
            f"Not waiting: {path} does not exist, so no background command writes to it.\n"
            f"If you typed the path, copy it again whole from the Bash tool's message that moved "
            f"the command to the background.")
    path = os.path.realpath(path)
    deadline = clock() + time_limit_seconds
    try:
        try:
            writers = list_writers(path, time_limit_seconds)
        except WritersLookTimeLimitReached as error:
            return EXIT_CANNOT_WAIT, (
                f"Not waiting: the processes writing to {path} could not be listed within "
                f"--time-limit-seconds {time_limit_seconds:g}: {error}\n"
                f"Run python3 {Path(__file__).resolve()} {path} instead, without "
                f"--time-limit-seconds: its default of {DEFAULT_TIME_LIMIT_SECONDS} seconds leaves "
                f"lsof the {LSOF_TIMEOUT_SECONDS} seconds one look may take.")
        if not writers:
            return EXIT_CANNOT_WAIT, (
                f"Not waiting: no process has {path} open for writing, so this program cannot tell "
                f"whether the background command has ended.\n"
                f"If Claude Code has told you the background command completed, it has ended: read "
                f"{path} for its output.\n"
                f"If Claude Code has not told you, the command's processes are hidden from this "
                f"program, for example in another process namespace: wait for Claude Code's "
                f"notice instead, and say in your report that this program could not see them.")
        while writers:
            # A sleep that would reach the time limit would leave no time for the look after it.
            if deadline - clock() <= POLL_SECONDS:
                return time_limit_reached(path, time_limit_seconds, writers)
            sleep(POLL_SECONDS)
            try:
                writers = list_writers(path, deadline - clock())
            except WritersLookTimeLimitReached:
                return time_limit_reached(path, time_limit_seconds, writers)
    except WritersCannotBeListed as error:
        return EXIT_CANNOT_WAIT, (
            f"Not waiting: the processes writing to {path} cannot be listed: {error}\n"
            f"Wait for Claude Code's notice that the background command completed instead.\n"
            f"Tell the user, or the agent that dispatched you, what this message says, so that "
            f"this program can be fixed.")
    return EXIT_NO_WRITER_LEFT, (
        f"Finished: no process has {path} open for writing any more, so the background command "
        f"has ended. Read {path} for its output.")


def time_limit_reached(path, time_limit_seconds, writers):
    return EXIT_TIME_LIMIT_REACHED, (
        f"Still running after {time_limit_seconds:g} seconds: process "
        f"{', '.join(map(str, sorted(writers)))} still has {path} open for writing.\n"
        f"To keep waiting, run the same command again.\n"
        f"If you give the Bash tool a timeout, make it longer than "
        f"--time-limit-seconds, so that this program ends the wait with this message.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("output_file", help="the file Claude Code named when it moved the command "
                                            "to the background")
    parser.add_argument("--time-limit-seconds", type=float, default=DEFAULT_TIME_LIMIT_SECONDS,
                        help=f"stop waiting after this many seconds (default "
                             f"{DEFAULT_TIME_LIMIT_SECONDS})")
    arguments = parser.parse_args(argv)
    code, message = wait_until_no_process_writes(
        arguments.output_file, arguments.time_limit_seconds, processes_writing_file_lister())
    print(message, file=sys.stdout if code == EXIT_NO_WRITER_LEFT else sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
