#!/usr/bin/env python3
"""Record that today's memory review has started, or that it is done.

RULED. The user, 2026-09-30, item 3 of the walk
eight-deferrals-with-no-trigger-2026-09-29, his word "y", on his own words:
"Memory can be useful in the short term, but unless it's drained regularly it
becomes counter productive. I think reviewing memory daily is the right
approach, assuming all agents share the same memory file." and "COuld we put
something in the reincarnation process, that surfaces a review of both
computer's memory file starting at noon each day. Once it's reviewed, it
sleeps until the next noon?" The issue is GHI [Memory: agents write freely,
and each reincarnation drains the new entries in a walk with the
user](https://github.com/nedschorus/nedschorus/issues/39).

From noon in America/Los_Angeles, a Mac handoff-supervisor gives the seat it
launches one line asking for the review, unless today's review has started or
is done, or neither store changed since the last review was done. That line,
and why it is built the way it is, are memory_review_due_lines in
nc-systems/handoff/handoff-supervisor.py. This program writes the marks the
line reads, and holds what the two share: where the stores and the marks are,
how a store is read, which Pacific date it is, and the digest that says
whether the stores changed. The supervisor imports it by path. So does
nc-systems/handoff/daily-overview-refresh-reminder-mark.py, whose dated marks
are read and written through this program's reader and writer, given that
program's own marks directory and file-name pattern.

USAGE
  nc-systems/handoff/daily-memory-review-mark.py started
  nc-systems/handoff/daily-memory-review-mark.py done

THE MARKS are one file per mark in the log-store, named for the Pacific date
the mark was written on:

  nedlern@ned-box:/home/nedlern/nedschorus-logs/daily-memory-review-marks/<YYYY-MM-DD>-started.txt
  nedlern@ned-box:/home/nedlern/nedschorus-logs/daily-memory-review-marks/<YYYY-MM-DD>-done.txt

A started file holds the UTC time it was written. A done file holds the digest
of both stores at the moment the walk closed, so the next noon can tell
whether either store changed since. Writing a mark again on the same date
replaces it.

THE STORES. Each machine has one memory store, which every seat on it shares:
Claude Code keys the store to the repository root, so every worktree of this
repository on a machine writes into it. The two are MAC_MEMORY_STORE_DIRECTORY
and NED_BOX_MEMORY_STORE_DIRECTORY below. A store's files are the regular
files directly inside its directory, except those whose names begin with a
dot, such as the .DS_Store the Mac's Finder leaves behind: that file is not
memory, and it would change the digest with nothing reviewed. An entry is any
file of the store but its index, MEMORY.md.

THE DIGEST is sha256 over each store in turn, the Mac's first, and within it
each file in name order: the store's name, the file's name, its length and its
content. A file added, removed, renamed or edited in either store changes it.

ON EACH MACHINE. From the Mac, ned-box's store is read and the mark is written
over ssh. On ned-box the mark is written locally. `done` runs only on the Mac:
nothing gives ned-box a way back to the Mac
(docs/issues/39-memory-drain-at-reincarnation.md, "Walking a ned-box drain
from the Mac"), so on ned-box the Mac's store cannot be read, and a digest of
ned-box's store alone would never match the one the Mac's check computes.

Exit codes: 0 the mark was written, 1 it was not, 2 bad invocation.
"""

import argparse
import base64
import hashlib
import json
import shlex
import socket
import subprocess
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

PROGRAM = "daily-memory-review-mark"

# The zone the review's noon and its dates are read in, named rather than
# taken from the machine: the user reads on the Mac, in Pacific time, and
# ned-box's own zone is nobody's decision about when noon is.
PACIFIC_TIME_ZONE_NAME = "America/Los_Angeles"

NED_BOX_HOSTNAME = "ned-box"
NED_BOX_SSH_TARGET = "nedlern@ned-box"
# The options the log-store's other writers pass ssh
# (nc-systems/cold-read/cold-read-record-ship.py's SSH_COMMAND): never prompt,
# and give up on a connection that does not open in ten seconds.
NED_BOX_SSH_COMMAND = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10"]

MAC_MEMORY_STORE_DIRECTORY = "/Users/el/.claude/projects/-Users-el-Projects-nedschorus/memory"
NED_BOX_MEMORY_STORE_DIRECTORY = (
    "/home/nedlern/.claude/projects/-home-nedlern-Projects-nedschorus/memory")
# The same store as the Mac opens it, through the Samba share of ned-box's home
# (smb://nedlern@ned-box.local/nedhome) mounted at /Volumes/nedhome. The
# reviewing seat reads the entries there with its file tools, so an edit goes
# through the instruction-file guard, which does not see a change made over
# ssh. This program never reads the mount: ssh gives up after ten seconds,
# and a read from a hung mount has no time limit.
NED_BOX_MEMORY_STORE_MAC_MOUNT_DIRECTORY = (
    "/Volumes/nedhome/.claude/projects/-home-nedlern-Projects-nedschorus/memory")
MEMORY_STORE_INDEX_FILE_NAME = "MEMORY.md"

# On ned-box; see THE MARKS in the module docstring.
DAILY_MEMORY_REVIEW_MARKS_DIRECTORY = "/home/nedlern/nedschorus-logs/daily-memory-review-marks"
DAILY_MEMORY_REVIEW_MARK_KINDS = ("started", "done")

# How long each of this program's reads, and its write, gets before it is given
# up on. Read from the module inside main rather than bound as a default
# argument, so a case can lower it.
DAILY_MEMORY_REVIEW_MARK_SSH_TIMEOUT_SECONDS = 30

# Run by python3 with a store's directory and the marks' directory as its two
# arguments: over ssh on ned-box, or locally for the Mac's store. It only reads,
# and prints one JSON object: each store file's content in base64, and each
# mark's text. An empty or absent directory reads as holding nothing. One text
# for both machines, so the two stores are read by the same rule. A third
# argument, when given, is the pattern a mark's file name must match in place
# of this review's own: nc-systems/handoff/daily-overview-refresh-reminder-mark.py
# reads its dated marks through this same program, so there is one reader of a
# marks directory in the log-store.
MEMORY_STORE_AND_REVIEW_MARKS_READ_PROGRAM = r"""
import base64, json, os, re, sys
store_directory, marks_directory = sys.argv[1], sys.argv[2]
mark_file_name_pattern = (sys.argv[3] if len(sys.argv) > 3
                          else r"[0-9]{4}-[0-9]{2}-[0-9]{2}-(started|done)[.]txt")
store = {}
if store_directory and os.path.isdir(store_directory):
    for name in os.listdir(store_directory):
        path = os.path.join(store_directory, name)
        if not name.startswith(".") and os.path.isfile(path):
            with open(path, "rb") as handle:
                store[name] = base64.b64encode(handle.read()).decode("ascii")
marks = {}
if marks_directory and os.path.isdir(marks_directory):
    for name in os.listdir(marks_directory):
        if re.fullmatch(mark_file_name_pattern, name):
            with open(os.path.join(marks_directory, name), encoding="utf-8",
                      errors="replace") as handle:
                marks[name] = handle.read()
print(json.dumps({"store": store, "marks": marks}))
"""


class DailyMemoryReviewReadOrWriteFailed(Exception):
    """A store or the marks could not be read, or a mark could not be
    written; the message says which command failed and how."""


def this_machine_is_ned_box() -> bool:
    return socket.gethostname().split(".")[0] == NED_BOX_HOSTNAME


def pacific_time_of(moment: datetime) -> datetime:
    """moment, which must carry its zone, as the time in America/Los_Angeles."""
    return moment.astimezone(ZoneInfo(PACIFIC_TIME_ZONE_NAME))


def daily_memory_review_mark_file_name(pacific_date: str, mark: str) -> str:
    return f"{pacific_date}-{mark}.txt"


def ned_box_memory_store_citation() -> str:
    """ned-box's store in the scp form, which resolves from either machine."""
    return f"{NED_BOX_SSH_TARGET}:{NED_BOX_MEMORY_STORE_DIRECTORY}/"


def run_on_ned_box_or_here(command: str, ssh_target, timeout: float, stdin_text=None):
    """Run one shell command on ned-box over ssh, or here when ssh_target is
    None; return its stdout, and raise DailyMemoryReviewReadOrWriteFailed on a
    nonzero exit, a timeout, or a command that cannot be started."""
    argv = ([*NED_BOX_SSH_COMMAND, ssh_target, command] if ssh_target
            else ["/bin/sh", "-c", command])
    runner = f"ssh {ssh_target}" if ssh_target else "/bin/sh"
    try:
        completed = subprocess.run(argv, capture_output=True, text=True, check=False,
                                   timeout=timeout, input=stdin_text)
    except subprocess.TimeoutExpired:
        raise DailyMemoryReviewReadOrWriteFailed(f"{runner} timed out after {timeout} s")
    except OSError as error:
        raise DailyMemoryReviewReadOrWriteFailed(
            f"{runner} could not be started: {type(error).__name__}: {error}")
    if completed.returncode != 0:
        first_line = (completed.stderr.strip().splitlines() or ["no detail"])[0]
        raise DailyMemoryReviewReadOrWriteFailed(
            f"{runner} exited {completed.returncode}: {first_line}")
    return completed.stdout


def read_memory_store_and_review_marks(ssh_target, store_directory: str,
                                       marks_directory: str, timeout: float,
                                       mark_file_name_pattern=None):
    """(store, marks): the store's files as {name: bytes}, and the marks as
    {file name: text}, read on ned-box over ssh or, when ssh_target is None,
    here. Pass "" for a directory not wanted. mark_file_name_pattern, when
    given, is the regular expression a mark's whole file name must match in
    place of this review's started and done names; it is how another dated
    mark in the log-store is read. Raises DailyMemoryReviewReadOrWriteFailed
    when the read fails."""
    command = " ".join(shlex.quote(part) for part in (
        "python3", "-c", MEMORY_STORE_AND_REVIEW_MARKS_READ_PROGRAM,
        store_directory, marks_directory,
        *((mark_file_name_pattern,) if mark_file_name_pattern else ())))
    output = run_on_ned_box_or_here(command, ssh_target, timeout)
    try:
        answer = json.loads(output)
        store = {name: base64.b64decode(content) for name, content in answer["store"].items()}
        marks = dict(answer["marks"])
    except (ValueError, KeyError, TypeError, AttributeError) as error:
        where = f"ssh {ssh_target}" if ssh_target else "the local read"
        raise DailyMemoryReviewReadOrWriteFailed(
            f"{where} answered with output that does not parse: {type(error).__name__}: {error}")
    return store, marks


def memory_store_entry_count(store: dict) -> int:
    return sum(1 for name in store if name != MEMORY_STORE_INDEX_FILE_NAME)


def memory_stores_digest(mac_store: dict, ned_box_store: dict) -> str:
    """See THE DIGEST in the module docstring."""
    digest = hashlib.sha256()
    for store_name, store in (("mac", mac_store), ("ned-box", ned_box_store)):
        for file_name in sorted(store):
            content = store[file_name]
            digest.update(f"{store_name}\0{file_name}\0{len(content)}\0".encode("utf-8"))
            digest.update(content)
    return digest.hexdigest()


def latest_done_mark(marks: dict):
    """(Pacific date, recorded digest) of the latest done mark, or None when no
    review has been recorded as done."""
    done = sorted(name for name in marks if name.endswith("-done.txt"))
    if not done:
        return None
    return done[-1][:len("YYYY-MM-DD")], marks[done[-1]].strip()


def write_daily_memory_review_mark(ssh_target, file_name: str, content: str, timeout: float,
                                   marks_directory=None):
    """Write one mark into the marks directory, on ned-box over ssh or, when
    ssh_target is None, here. The content travels on stdin, so nothing in it
    is read by a shell. marks_directory, when given, is another marks
    directory in the log-store to write into in place of this review's own."""
    marks_directory = marks_directory or DAILY_MEMORY_REVIEW_MARKS_DIRECTORY
    directory = shlex.quote(marks_directory)
    target = shlex.quote(f"{marks_directory}/{file_name}")
    run_on_ned_box_or_here(f"mkdir -p {directory} && cat > {target}", ssh_target,
                           timeout, stdin_text=content + "\n")


def main(argv=None, now=None) -> int:
    parser = argparse.ArgumentParser(
        prog=PROGRAM,
        description="Record that today's memory review has started, or that it is done.")
    parser.add_argument("mark", choices=DAILY_MEMORY_REVIEW_MARK_KINDS)
    arguments = parser.parse_args(argv)
    now = now or datetime.now(timezone.utc)
    pacific_date = pacific_time_of(now).date().isoformat()
    timeout = DAILY_MEMORY_REVIEW_MARK_SSH_TIMEOUT_SECONDS
    ssh_target = None if this_machine_is_ned_box() else NED_BOX_SSH_TARGET
    if arguments.mark == "done":
        if ssh_target is None:
            print(f"{PROGRAM}: run `done` from a Mac seat when you are on ned-box.",
                  file=sys.stderr)
            return 1
        try:
            ned_box_store, _ = read_memory_store_and_review_marks(
                ssh_target, NED_BOX_MEMORY_STORE_DIRECTORY, "", timeout)
            mac_store, _ = read_memory_store_and_review_marks(
                None, MAC_MEMORY_STORE_DIRECTORY, "", timeout)
        except DailyMemoryReviewReadOrWriteFailed as error:
            print(f"{PROGRAM}: the done mark was not written because a memory store "
                  f"could not be read ({error}) — tell the user what it said, and run "
                  f"this again once the cause is fixed.", file=sys.stderr)
            return 1
        content = memory_stores_digest(mac_store, ned_box_store)
    else:
        content = now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    file_name = daily_memory_review_mark_file_name(pacific_date, arguments.mark)
    try:
        write_daily_memory_review_mark(ssh_target, file_name, content, timeout)
    except DailyMemoryReviewReadOrWriteFailed as error:
        print(f"{PROGRAM}: the {arguments.mark} mark was not written ({error}) — tell "
              f"the user what it said, and run this again once the cause is fixed.",
              file=sys.stderr)
        return 1
    print(f"{PROGRAM}: {arguments.mark} recorded for {pacific_date} in "
          f"{NED_BOX_SSH_TARGET}:{DAILY_MEMORY_REVIEW_MARKS_DIRECTORY}/{file_name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
