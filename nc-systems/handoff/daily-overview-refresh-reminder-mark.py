#!/usr/bin/env python3
"""Record that the user has been shown today's refresh of one system's overview.

RULED. The user, 2026-10-01, to the merge-lane-2 seat, on the point that
every reincarnating seat was given the same "overview refresh due" line while
one seat's drafted refresh waited for him. In his own words: "My concern is
that if only one seat reminds me, what if I close that seat? Does it matter
which seat reminds me? If not, then as long as I get reminded at least once a
day, that should work." Then his word "y" to the rule: "one reminder a day
for each overview that is behind, from whichever seat starts up first that
day; the other seats stay quiet until the next day." Recorded at
  https://github.com/nedschorus/nedschorus/pull/852#issuecomment-5939116857

A handoff-supervisor, on either machine, gives the seat it launches the
"overview refresh due" line for a system unless today's mark for that system
exists. That line, and how the mark decides it, are overview_refresh_due_lines
in nc-systems/handoff/handoff-supervisor.py. This program writes the mark the
line reads, and holds what the two share: where the marks are, what a mark is
called, and what a mark holds. The supervisor imports it by path.

USAGE
  nc-systems/handoff/daily-overview-refresh-reminder-mark.py <system>

<system> is the name of the system's directory under nc-systems/, such as
handoff. The seat runs this once the user has been shown the diff between the
overview and its draft, and not before: the mark means the user was reminded,
so a seat that is closed before it shows him the diff leaves no mark, and the
next seat to reincarnate that day is given the line.

THE MARKS are one file per system per day in the log-store, named for the
Pacific date the mark was written on and for the system:

  nedlern@ned-box:/home/nedlern/nedschorus-logs/daily-overview-refresh-reminder-marks/<YYYY-MM-DD>-<system>.txt

A mark holds the UTC time it was written. Writing a mark again on the same
date replaces it. A mark whose text is not such a time is not a mark: the
supervisor gives the line and says so, because the user is to be reminded at
least once a day.

THE DAY is the calendar date in America/Los_Angeles, the zone the daily memory
review reads its dates in, from midnight. The memory review looks only from
noon, which is the user's own "starting at noon each day" for that review; the
reminder has no such start, because the rule gives the line to whichever seat
starts up first that day.

ONE READER AND ONE WRITER. The marks are read and written through
nc-systems/handoff/daily-memory-review-mark.py's reader and writer, given this
program's marks directory and file-name pattern, so a dated mark in the
log-store is read and written one way. That program also decides which machine
this is, the Pacific time, and the ssh command.

ON EACH MACHINE. From the Mac the mark is read and written over ssh. On
ned-box it is read and written locally.

Exit codes: 0 the mark was written, 1 it was not, 2 bad invocation.
"""

import argparse
import importlib.util
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

PROGRAM = "daily-overview-refresh-reminder-mark"

# The reader and the writer of a dated mark in the log-store, the Pacific time
# and which machine this is; see ONE READER AND ONE WRITER in the module
# docstring. Loaded by path, as the supervisor loads it: its file name has
# hyphens. Loading it runs nothing.
_daily_memory_review_mark_spec = importlib.util.spec_from_file_location(
    "daily_memory_review_mark",
    Path(__file__).resolve().with_name("daily-memory-review-mark.py"))
daily_memory_review_mark = importlib.util.module_from_spec(_daily_memory_review_mark_spec)
_daily_memory_review_mark_spec.loader.exec_module(daily_memory_review_mark)

# On ned-box; see THE MARKS in the module docstring.
DAILY_OVERVIEW_REFRESH_REMINDER_MARKS_DIRECTORY = (
    "/home/nedlern/nedschorus-logs/daily-overview-refresh-reminder-marks")

# What a system's name may be for a mark to carry it: the name of a directory
# under nc-systems/, which is letters, digits, hyphens and underscores. A seat
# that passes the overview's path in place of the system's name is refused
# here, where it can be told what to pass; a mark under any other name would
# never be read.
SYSTEM_NAME_PATTERN = r"[A-Za-z0-9][A-Za-z0-9_-]*"

# What a mark holds: the UTC time it was written, in this form.
REMINDER_MARK_TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

# How long this program's one write gets before it is given up on. Read from
# the module inside main rather than bound as a default argument, so a case
# can lower it.
DAILY_OVERVIEW_REFRESH_REMINDER_MARK_SSH_TIMEOUT_SECONDS = 30


def daily_overview_refresh_reminder_mark_file_name(pacific_date: str, system: str) -> str:
    return f"{pacific_date}-{system}.txt"


def daily_overview_refresh_reminder_mark_citation(file_name: str) -> str:
    """A mark in the scp form, which resolves from either machine."""
    return (f"{daily_memory_review_mark.NED_BOX_SSH_TARGET}:"
            f"{DAILY_OVERVIEW_REFRESH_REMINDER_MARKS_DIRECTORY}/{file_name}")


def pacific_date_of(moment: datetime) -> str:
    """The calendar date of moment, which must carry its zone, in
    America/Los_Angeles, as YYYY-MM-DD; see THE DAY in the module docstring."""
    return daily_memory_review_mark.pacific_time_of(moment).date().isoformat()


def ssh_target_for_this_machine():
    """ned-box's ssh target from the Mac, None on ned-box itself."""
    return (None if daily_memory_review_mark.this_machine_is_ned_box()
            else daily_memory_review_mark.NED_BOX_SSH_TARGET)


def read_daily_overview_refresh_reminder_marks(pacific_date: str, timeout: float) -> dict:
    """The marks of pacific_date as {file name: text}, read on ned-box over
    ssh or, on ned-box, here. Only that date's marks are read, so the read
    does not grow with the days. Raises
    daily_memory_review_mark.DailyMemoryReviewReadOrWriteFailed when the read
    fails."""
    _, marks = daily_memory_review_mark.read_memory_store_and_review_marks(
        ssh_target_for_this_machine(), "", DAILY_OVERVIEW_REFRESH_REMINDER_MARKS_DIRECTORY,
        timeout,
        mark_file_name_pattern=f"{re.escape(pacific_date)}-{SYSTEM_NAME_PATTERN}[.]txt")
    return marks


def reminder_mark_text_is_a_time(text: str) -> bool:
    """Whether a mark's text is the UTC time a mark holds. A file cut short as
    it was written, or one written by hand, is not."""
    try:
        datetime.strptime(text.strip(), REMINDER_MARK_TIME_FORMAT)
    except ValueError:
        return False
    return True


def main(argv=None, now=None) -> int:
    parser = argparse.ArgumentParser(
        prog=PROGRAM,
        description="Record that the user has been shown today's refresh of one "
                    "system's overview.")
    parser.add_argument("system", help="the system's directory name under nc-systems/")
    arguments = parser.parse_args(argv)
    if not re.fullmatch(SYSTEM_NAME_PATTERN, arguments.system):
        print(f"{PROGRAM}: pass the name of the system's directory under nc-systems/, "
              f"such as handoff, in place of {arguments.system!r}.", file=sys.stderr)
        return 2
    now = now or datetime.now(timezone.utc)
    file_name = daily_overview_refresh_reminder_mark_file_name(
        pacific_date_of(now), arguments.system)
    content = now.astimezone(timezone.utc).strftime(REMINDER_MARK_TIME_FORMAT)
    try:
        daily_memory_review_mark.write_daily_memory_review_mark(
            ssh_target_for_this_machine(), file_name, content,
            DAILY_OVERVIEW_REFRESH_REMINDER_MARK_SSH_TIMEOUT_SECONDS,
            marks_directory=DAILY_OVERVIEW_REFRESH_REMINDER_MARKS_DIRECTORY)
    except daily_memory_review_mark.DailyMemoryReviewReadOrWriteFailed as error:
        print(f"{PROGRAM}: the mark for {arguments.system} was not written ({error}) — "
              f"tell the user what it said, and run this again once the cause is fixed.",
              file=sys.stderr)
        return 1
    print(f"{PROGRAM}: the reminder for {arguments.system} is recorded for "
          f"{file_name[:len('YYYY-MM-DD')]} in "
          f"{daily_overview_refresh_reminder_mark_citation(file_name)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
