#!/usr/bin/env python3
"""Record that the user has seen today's overview refresh, using a shared mark on ned-box.

Mark only after showing the diff: a seat closed beforehand must leave the next seat able to remind.
The reminder day starts at midnight in America/Los_Angeles, independently of the memory review's noon start."""

import argparse
import importlib.util
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

PROGRAM = "daily-overview-refresh-reminder-mark"

_daily_memory_review_mark_spec = importlib.util.spec_from_file_location(
    "daily_memory_review_mark",
    Path(__file__).resolve().with_name("daily-memory-review-mark.py"))
daily_memory_review_mark = importlib.util.module_from_spec(_daily_memory_review_mark_spec)
_daily_memory_review_mark_spec.loader.exec_module(daily_memory_review_mark)

DAILY_OVERVIEW_REFRESH_REMINDER_MARKS_DIRECTORY = (
    "/home/nedlern/nedschorus-logs/daily-overview-refresh-reminder-marks")

# Refuse paths: a mark under anything but the system directory name would never be read.
SYSTEM_NAME_PATTERN = r"[A-Za-z0-9][A-Za-z0-9_-]*"

REMINDER_MARK_TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

# Read the timeout inside main so tests can override it.
DAILY_OVERVIEW_REFRESH_REMINDER_MARK_SSH_TIMEOUT_SECONDS = 30


def daily_overview_refresh_reminder_mark_file_name(pacific_date: str, system: str) -> str:
    return f"{pacific_date}-{system}.txt"


def daily_overview_refresh_reminder_mark_citation(file_name: str) -> str:
    """Return the mark citation in scp form, usable from either machine."""
    return (f"{daily_memory_review_mark.NED_BOX_SSH_TARGET}:"
            f"{DAILY_OVERVIEW_REFRESH_REMINDER_MARKS_DIRECTORY}/{file_name}")


def pacific_date_of(moment: datetime) -> str:
    """Return the Pacific YYYY-MM-DD date of a timezone-aware moment."""
    return daily_memory_review_mark.pacific_time_of(moment).date().isoformat()


def ssh_target_for_this_machine():
    """Return ned-box's ssh target from the Mac, or None on ned-box."""
    return (None if daily_memory_review_mark.this_machine_is_ned_box()
            else daily_memory_review_mark.NED_BOX_SSH_TARGET)


def read_daily_overview_refresh_reminder_marks(pacific_date: str, timeout: float) -> dict:
    """Return the date's marks as {file name: text}, raising on read failure."""
    _, marks = daily_memory_review_mark.read_memory_store_and_review_marks(
        ssh_target_for_this_machine(), "", DAILY_OVERVIEW_REFRESH_REMINDER_MARKS_DIRECTORY,
        timeout,
        mark_file_name_pattern=f"{re.escape(pacific_date)}-{SYSTEM_NAME_PATTERN}[.]txt")
    return marks


def reminder_mark_text_is_a_time(text: str) -> bool:
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
              f"tell the user this message, and run this command again once the cause is fixed.",
              file=sys.stderr)
        return 1
    print(f"{PROGRAM}: the reminder for {arguments.system} is recorded for "
          f"{file_name[:len('YYYY-MM-DD')]} in "
          f"{daily_overview_refresh_reminder_mark_citation(file_name)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
