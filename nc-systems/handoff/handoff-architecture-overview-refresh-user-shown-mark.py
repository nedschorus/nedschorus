#!/usr/bin/env python3
"""Record that the user has seen today's overview refresh, using a shared mark on ned-box.

Mark only after showing the diff: a seat closed beforehand must leave the next seat able to remind.
The reminder day starts at midnight in America/Los_Angeles, independently of the memory review's noon start."""

import argparse
import importlib.util
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

PROGRAM = "handoff-architecture-overview-refresh-user-shown-mark"
PROGRAM_PATH = f"nc-systems/handoff/{PROGRAM}.py"

_handoff_user_review_of_agent_memory_stores_mark_spec = importlib.util.spec_from_file_location(
    "handoff_user_review_of_agent_memory_stores_mark",
    Path(__file__).resolve().with_name("handoff-user-review-of-agent-memory-stores-mark.py"))
handoff_user_review_of_agent_memory_stores_mark = importlib.util.module_from_spec(_handoff_user_review_of_agent_memory_stores_mark_spec)
_handoff_user_review_of_agent_memory_stores_mark_spec.loader.exec_module(handoff_user_review_of_agent_memory_stores_mark)

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
    return (f"{handoff_user_review_of_agent_memory_stores_mark.NED_BOX_SSH_TARGET}:"
            f"{DAILY_OVERVIEW_REFRESH_REMINDER_MARKS_DIRECTORY}/{file_name}")


def pacific_date_of(moment: datetime) -> str:
    """Return the Pacific YYYY-MM-DD date of a timezone-aware moment."""
    return handoff_user_review_of_agent_memory_stores_mark.pacific_time_of(moment).date().isoformat()


def ssh_target_for_this_machine():
    """Return ned-box's ssh target from the Mac, or None on ned-box."""
    return (None if handoff_user_review_of_agent_memory_stores_mark.this_machine_is_ned_box()
            else handoff_user_review_of_agent_memory_stores_mark.NED_BOX_SSH_TARGET)


def read_daily_overview_refresh_reminder_marks(pacific_date: str, timeout: float) -> dict:
    """Return the date's marks as {file name: text}, raising on read failure."""
    _, marks = handoff_user_review_of_agent_memory_stores_mark.read_memory_store_and_review_marks(
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
    # A retry carries the day the user was shown the refresh, so a retry after that
    # Pacific day cannot mark a day on which the user saw nothing.
    parser.add_argument("--shown-on-pacific-date", type=date.fromisoformat, default=None,
                        help="the Pacific date, YYYY-MM-DD, the user was shown the "
                             "refresh; today's when left out")
    arguments = parser.parse_args(argv)
    marks_directory_citation = (f"{handoff_user_review_of_agent_memory_stores_mark.NED_BOX_SSH_TARGET}:"
                                f"{DAILY_OVERVIEW_REFRESH_REMINDER_MARKS_DIRECTORY}/")
    if not re.fullmatch(SYSTEM_NAME_PATTERN, arguments.system):
        print(f"{PROGRAM}: {arguments.system!r} was refused as a system's name, so no mark "
              f"was written in {marks_directory_citation}: a system's name is the name "
              f"of its directory under nc-systems/ without the nc-systems/ prefix, such as "
              f"handoff, starting with a letter or digit and holding only letters, digits, "
              f"'-' and '_' (only these characters are checked, not whether the directory "
              f"exists).\n"
              f"Run this again with the system's name that the handoff-supervisor's overview "
              f"refresh reminder gave, "
              f"such as: python3 {PROGRAM_PATH} handoff", file=sys.stderr)
        return 2
    now = now or datetime.now(timezone.utc)
    today = pacific_date_of(now)
    shown_on = (arguments.shown_on_pacific_date.isoformat()
                if arguments.shown_on_pacific_date is not None else today)
    if shown_on < today:
        print(f"{PROGRAM}: no mark was written for {arguments.system}, because "
              f"--shown-on-pacific-date {shown_on} is a Pacific date that has passed. A mark is the file that records that the user was shown the "
              f"{arguments.system} architecture overview refresh. A mark withholds the reminder "
              f"to show the user that refresh only on the Pacific date the mark is dated, so a "
              f"mark dated {shown_on} would withhold no reminder.\n"
              f"No mark is needed for {shown_on}. Whether a mark is needed for today depends "
              f"on whether you show the user the {arguments.system} refresh today, Pacific time:\n"
              f"If you have already shown the user the refresh today, run now, in a nedschorus "
              f"checkout on the Mac or on ned-box, this command, which has no date "
              f"flag and so writes a mark dated today: python3 {PROGRAM_PATH} {arguments.system}\n"
              f"If you show the user the refresh later today, run that same command right after "
              f"you show it.\n"
              f"If you do not show the user the refresh today, run nothing; the reminder will "
              f"come again.")
        return 0
    if shown_on > today:
        print(f"{PROGRAM}: no mark was written for {arguments.system}, because "
              f"--shown-on-pacific-date {shown_on} is after today's Pacific date, {today}.\n"
              f"If the user was shown the {arguments.system} architecture overview refresh "
              f"today, run, in a nedschorus checkout on the Mac or on ned-box: "
              f"python3 {PROGRAM_PATH} {arguments.system}\n"
              f"If the user was shown the refresh on an earlier day, run nothing: a mark "
              f"dated on a day that has passed does not withhold today's reminder.",
              file=sys.stderr)
        return 2
    file_name = daily_overview_refresh_reminder_mark_file_name(shown_on, arguments.system)
    content = now.astimezone(timezone.utc).strftime(REMINDER_MARK_TIME_FORMAT)
    try:
        handoff_user_review_of_agent_memory_stores_mark.write_daily_memory_review_mark(
            ssh_target_for_this_machine(), file_name, content,
            DAILY_OVERVIEW_REFRESH_REMINDER_MARK_SSH_TIMEOUT_SECONDS,
            marks_directory=DAILY_OVERVIEW_REFRESH_REMINDER_MARKS_DIRECTORY)
    except handoff_user_review_of_agent_memory_stores_mark.DailyMemoryReviewReadOrWriteFailed as error:
        print(f"{PROGRAM}: the mark for {arguments.system} could not be confirmed as "
              f"written to {daily_overview_refresh_reminder_mark_citation(file_name)}, so the "
              f"next agent-session the handoff-supervisor starts today may show the user the "
              f"same architecture overview refresh again: {error}\n"
              f"If you are a subagent, send this whole message to the agent that dispatched "
              f"you instead of acting on it; otherwise, do what the next lines say.\n"
              f"Tell the user: \"The record that you were shown the {arguments.system} "
              f"architecture overview refresh today may not have been written on ned-box, so "
              f"you may be shown it again today: {error}\"\n"
              f"When the user says the cause is fixed, run, in a nedschorus checkout on the "
              f"Mac or on ned-box, since either writes the mark on ned-box: "
              f"python3 {PROGRAM_PATH} {arguments.system} --shown-on-pacific-date {shown_on}",
              file=sys.stderr)
        return 1
    print(f"{PROGRAM}: recorded that the user was shown the {arguments.system} architecture "
          f"overview refresh on the Pacific date {shown_on}, in "
          f"{daily_overview_refresh_reminder_mark_citation(file_name)}; the handoff-supervisor "
          f"withholds the {arguments.system} refresh reminder for the rest of {shown_on}, "
          f"Pacific time, and gives it again on a later day while the refresh is still due.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
