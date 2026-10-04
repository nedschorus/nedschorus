#!/usr/bin/env python3
"""Record daily memory review marks and share store readers with reminder checks.

Use Pacific dates for the user’s noon. The done digest must cover both
machines, so done runs only on the Mac: ned-box has no route back to read
the Mac’s store.

Claude Code shares a repository’s memory store across worktrees. Ignore
hidden files such as .DS_Store so incidental metadata cannot trigger review."""

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

PACIFIC_TIME_ZONE_NAME = "America/Los_Angeles"

NED_BOX_HOSTNAME = "ned-box"
NED_BOX_SSH_TARGET = "nedlern@ned-box"
NED_BOX_SSH_COMMAND = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10"]

MAC_MEMORY_STORE_DIRECTORY = "/Users/el/.claude/projects/-Users-el-Projects-nedschorus/memory"
NED_BOX_MEMORY_STORE_DIRECTORY = (
    "/home/nedlern/.claude/projects/-home-nedlern-Projects-nedschorus/memory")
# Reviewers use the mount so file edits pass through the instruction-file guard.
# This reader uses ssh because a hung mount has no read timeout.
NED_BOX_MEMORY_STORE_MAC_MOUNT_DIRECTORY = (
    "/Volumes/nedhome/.claude/projects/-home-nedlern-Projects-nedschorus/memory")
MEMORY_STORE_INDEX_FILE_NAME = "MEMORY.md"

DAILY_MEMORY_REVIEW_MARKS_DIRECTORY = "/home/nedlern/nedschorus-logs/daily-memory-review-marks"
DAILY_MEMORY_REVIEW_MARK_KINDS = ("started", "done")

# Look up the timeout at call time so tests can lower it.
DAILY_MEMORY_REVIEW_MARK_SSH_TIMEOUT_SECONDS = 30

# Use the same reader locally and over ssh so both memory stores follow identical rules.
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
    """A store or mark operation failed; the message identifies the command and failure."""

    def __init__(self, message: str, ned_box_did_not_answer: bool = False):
        super().__init__(message)
        # ssh exits 255 for its own failures, such as no connection; any other
        # exit, or output that does not parse, came from ned-box, so ned-box answered.
        self.ned_box_did_not_answer = ned_box_did_not_answer


def this_machine_is_ned_box() -> bool:
    return socket.gethostname().split(".")[0] == NED_BOX_HOSTNAME


def pacific_time_of(moment: datetime) -> datetime:
    """Return a timezone-aware moment in America/Los_Angeles."""
    return moment.astimezone(ZoneInfo(PACIFIC_TIME_ZONE_NAME))


def daily_memory_review_mark_file_name(pacific_date: str, mark: str) -> str:
    return f"{pacific_date}-{mark}.txt"


def ned_box_memory_store_citation() -> str:
    """Return the store’s scp citation, usable from either machine."""
    return f"{NED_BOX_SSH_TARGET}:{NED_BOX_MEMORY_STORE_DIRECTORY}/"


def run_on_ned_box_or_here(command: str, ssh_target, timeout: float, stdin_text=None):
    """Return command stdout from ssh or local execution, raising on failure."""
    argv = ([*NED_BOX_SSH_COMMAND, ssh_target, command] if ssh_target
            else ["/bin/sh", "-c", command])
    runner = f"ssh {ssh_target}" if ssh_target else "/bin/sh"
    try:
        completed = subprocess.run(argv, capture_output=True, text=True, check=False,
                                   timeout=timeout, input=stdin_text)
    except subprocess.TimeoutExpired:
        raise DailyMemoryReviewReadOrWriteFailed(f"{runner} timed out after {timeout} s",
                                                 ned_box_did_not_answer=bool(ssh_target))
    except OSError as error:
        raise DailyMemoryReviewReadOrWriteFailed(
            f"{runner} could not be started: {type(error).__name__}: {error}")
    if completed.returncode != 0:
        first_line = (completed.stderr.strip().splitlines() or ["no detail"])[0]
        raise DailyMemoryReviewReadOrWriteFailed(
            f"{runner} exited {completed.returncode}: {first_line}",
            ned_box_did_not_answer=bool(ssh_target) and completed.returncode == 255)
    return completed.stdout


def read_memory_store_and_review_marks(ssh_target, store_directory: str,
                                       marks_directory: str, timeout: float,
                                       mark_file_name_pattern=None):
    """Return (store, marks) as {name: bytes} and {name: text}; empty directory arguments skip reads."""
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
    digest = hashlib.sha256()
    for store_name, store in (("mac", mac_store), ("ned-box", ned_box_store)):
        for file_name in sorted(store):
            content = store[file_name]
            digest.update(f"{store_name}\0{file_name}\0{len(content)}\0".encode("utf-8"))
            digest.update(content)
    return digest.hexdigest()


def latest_done_mark(marks: dict):
    """Return (Pacific_date, digest) for the latest done mark, or None."""
    done = sorted(name for name in marks if name.endswith("-done.txt"))
    if not done:
        return None
    return done[-1][:len("YYYY-MM-DD")], marks[done[-1]].strip()


def write_daily_memory_review_mark(ssh_target, file_name: str, content: str, timeout: float,
                                   marks_directory=None):
    # Send content on stdin so the shell cannot interpret it.
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
