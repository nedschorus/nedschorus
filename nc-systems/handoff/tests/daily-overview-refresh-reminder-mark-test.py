#!/usr/bin/env python3
"""Tests for daily-overview-refresh-reminder-mark.py.

Run: python3 nc-systems/handoff/tests/daily-overview-refresh-reminder-mark-test.py

No case reaches ned-box. The marks directory is a fixture directory, set
through the program's constant; ned-box is played by an ssh first on PATH that
records the host of each call and runs the command it was handed here; the
machine's name is set per case; and the moment is passed in.

Prints one line per case and exits non-zero if any case fails.
"""

import contextlib
import importlib.util
import io
import os
import socket
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

SYSTEM_DIRECTORY = Path(__file__).resolve().parent.parent
SCRIPT_PATH = SYSTEM_DIRECTORY / "daily-overview-refresh-reminder-mark.py"

_spec = importlib.util.spec_from_file_location(
    "daily_overview_refresh_reminder_mark", SCRIPT_PATH)
mark = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mark)

failures = []

# 20:30 on 2026-09-30 in America/Los_Angeles (PDT, UTC-7), which is already
# 2026-10-01 in UTC and 12:30 on 2026-10-01 in Tokyo.
PACIFIC_EVENING_THAT_IS_TOMORROW_IN_UTC = datetime(2026, 10, 1, 3, 30, tzinfo=timezone.utc)

SSH_THAT_RUNS_THE_COMMAND_HERE = 'exec /bin/sh -c "$1"'


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


@contextlib.contextmanager
def local_time_zone(name: str):
    saved = os.environ.get("TZ")
    os.environ["TZ"] = name
    time.tzset()
    try:
        yield
    finally:
        if saved is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = saved
        time.tzset()


class Fixture:
    def __init__(self, root: Path):
        self.root = root
        self.marks = root / "daily-overview-refresh-reminder-marks"
        self.fake_ssh_count = 0
        root.mkdir()

    @contextlib.contextmanager
    def in_place(self, ssh_body=SSH_THAT_RUNS_THE_COMMAND_HERE,
                 hostname="a-mac-that-is-not-ned-box", ssh_timeout=None):
        """Yields the file the fake ssh records its calls' hosts in."""
        self.fake_ssh_count += 1
        directory = self.root / f"fake-ssh-{self.fake_ssh_count}"
        directory.mkdir()
        calls = directory / "calls"
        fake_ssh = directory / "ssh"
        fake_ssh.write_text(
            '#!/bin/sh\nwhile [ "$1" = "-o" ]; do shift 2; done\n'
            'printf "%s\\n" "$1" >> "' + str(calls) + '"\nshift\n' + ssh_body + "\n",
            encoding="utf-8")
        fake_ssh.chmod(0o755)
        saved = {name: getattr(mark, name) for name in (
            "DAILY_OVERVIEW_REFRESH_REMINDER_MARKS_DIRECTORY",
            "DAILY_OVERVIEW_REFRESH_REMINDER_MARK_SSH_TIMEOUT_SECONDS")}
        mark.DAILY_OVERVIEW_REFRESH_REMINDER_MARKS_DIRECTORY = str(self.marks)
        if ssh_timeout is not None:
            mark.DAILY_OVERVIEW_REFRESH_REMINDER_MARK_SSH_TIMEOUT_SECONDS = ssh_timeout
        saved_gethostname = socket.gethostname
        socket.gethostname = lambda: hostname
        original_path = os.environ.get("PATH", "")
        os.environ["PATH"] = f"{directory}{os.pathsep}{original_path}"
        try:
            yield calls
        finally:
            os.environ["PATH"] = original_path
            socket.gethostname = saved_gethostname
            for name, value in saved.items():
                setattr(mark, name, value)

    def run(self, argv, now=PACIFIC_EVENING_THAT_IS_TOMORROW_IN_UTC, **in_place_options):
        """main's exit code, stdout, stderr, and the hosts the fake ssh was
        called for."""
        stdout, stderr = io.StringIO(), io.StringIO()
        with self.in_place(**in_place_options) as calls, \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = mark.main(argv, now=now)
        recorded = calls.read_text(encoding="utf-8").splitlines() if calls.exists() else []
        return code, stdout.getvalue(), stderr.getvalue(), recorded

    def read(self, pacific_date, **in_place_options):
        """read_daily_overview_refresh_reminder_marks's result for pacific_date,
        and the hosts the fake ssh was called for."""
        with self.in_place(**in_place_options) as calls:
            marks = mark.read_daily_overview_refresh_reminder_marks(pacific_date, 5)
        recorded = calls.read_text(encoding="utf-8").splitlines() if calls.exists() else []
        return marks, recorded

    def mark_files(self):
        return sorted(path.name for path in self.marks.iterdir()) if self.marks.is_dir() else []


def run_mark_cases(workspace: Path):
    fixture = Fixture(workspace / "marks-from-the-mac")

    # Under Tokyo's zone the machine's own date is 2026-10-01; the mark is
    # dated by the Pacific one.
    with local_time_zone("Asia/Tokyo"):
        code, stdout, stderr, calls = fixture.run(["handoff"])
    written = fixture.marks / "2026-09-30-handoff.txt"
    check("from the Mac, the mark for a system is written over ssh to nedlern@ned-box",
          code == 0 and written.is_file() and calls == ["nedlern@ned-box"],
          f"{code} {fixture.mark_files()} {calls!r}\n{stderr}")
    check("the mark is named for the Pacific date, whatever the machine's zone, and for "
          "the system",
          fixture.mark_files() == ["2026-09-30-handoff.txt"], repr(fixture.mark_files()))
    check("the mark holds the UTC time it was written",
          written.is_file() and written.read_text(encoding="utf-8") == "2026-10-01T03:30:00Z\n",
          repr(written.read_text(encoding="utf-8") if written.is_file() else None))
    check("the program prints where the mark was written",
          stdout == "daily-overview-refresh-reminder-mark: the reminder for handoff is "
          f"recorded for 2026-09-30 in nedlern@ned-box:{fixture.marks}/"
          "2026-09-30-handoff.txt\n", stdout)

    code, stdout, stderr, calls = fixture.run(["cold-read"])
    check("a second system's mark is a second file, and the first is left as it is",
          code == 0 and fixture.mark_files() == ["2026-09-30-cold-read.txt",
                                                 "2026-09-30-handoff.txt"],
          f"{code} {fixture.mark_files()}\n{stderr}")

    code, stdout, stderr, calls = fixture.run(
        ["handoff"], ssh_body="echo 'ssh: connect to host ned-box port 22: No route to host' >&2\n"
                              "echo 'second line' >&2\nexit 255")
    check("when ned-box cannot be reached, the exit is 1 and nothing is printed to stdout",
          code == 1 and stdout == "", f"{code} {stdout!r}")
    check("when ned-box cannot be reached, stderr carries ssh's first line and what to do",
          stderr == "daily-overview-refresh-reminder-mark: the mark for handoff could not be "
          "confirmed as written, so the next agent-seat to reincarnate today may show the "
          "user the same overview refresh again: ssh nedlern@ned-box exited 255: ssh: "
          "connect to host ned-box port 22: No route to host\n"
          "Tell the user what the error above says.\n"
          "When the user says the cause is fixed, run: "
          "nc-systems/handoff/daily-overview-refresh-reminder-mark.py handoff "
          "--shown-on-pacific-date 2026-09-30\n", stderr)

    code, stdout, stderr, calls = fixture.run(["handoff"], ssh_body="exec sleep 30",
                                              ssh_timeout=1)
    check("when ssh times out, the mark is not written and stderr says so",
          code == 1 and "ssh nedlern@ned-box timed out after 1 s" in stderr,
          f"{code}\n{stderr}")

    on_ned_box = Fixture(workspace / "marks-on-ned-box")
    code, stdout, stderr, calls = on_ned_box.run(["handoff"], hostname="ned-box")
    check("on ned-box, the mark is written locally with no ssh",
          code == 0 and on_ned_box.mark_files() == ["2026-09-30-handoff.txt"] and calls == [],
          f"{code} {on_ned_box.mark_files()} {calls!r}\n{stderr}")

    refused = Fixture(workspace / "marks-refused")
    code, stdout, stderr, calls = refused.run(
        ["docs/nedschorus-wiki/nedschorus-handoff-architecture-overview.md"])
    check("an overview's path in place of the system's name is refused, exit 2, with "
          "nothing written and no ssh",
          code == 2 and refused.mark_files() == [] and calls == [] and stdout == "",
          f"{code} {refused.mark_files()} {calls!r} {stdout!r}")
    check("the refusal says nothing was written, and what to pass",
          stderr == "daily-overview-refresh-reminder-mark: no daily-overview-refresh-reminder-"
          "mark was written, because 'docs/nedschorus-wiki/nedschorus-handoff-architecture-"
          "overview.md' is not a system's name.\n"
          "Run this again with the name of the system's directory under nc-systems/, such "
          "as handoff.\n", stderr)

    dated = Fixture(workspace / "marks-dated")
    code, stdout, stderr, calls = dated.run(["handoff", "--shown-on-pacific-date", "2026-09-30"])
    check("a retry dated today's Pacific date writes today's mark",
          code == 0 and dated.mark_files() == ["2026-09-30-handoff.txt"],
          f"{code} {dated.mark_files()}\n{stderr}")
    code, stdout, stderr, calls = dated.run(
        ["handoff", "--shown-on-pacific-date", "2026-09-29"])
    check("a retry for a day that has passed writes nothing, exits 0 and says why",
          code == 0 and dated.mark_files() == ["2026-09-30-handoff.txt"] and calls == []
          and stdout == "daily-overview-refresh-reminder-mark: no mark was written, because "
          "2026-09-29 has passed; the next agent-seat to show the refresh writes the new "
          "day's mark.\n", f"{code} {dated.mark_files()} {calls!r} {stdout!r}")
    code, stdout, stderr, calls = dated.run(
        ["handoff", "--shown-on-pacific-date", "2026-10-01"])
    check("a date after today's Pacific date is refused, exit 2, with nothing written",
          code == 2 and dated.mark_files() == ["2026-09-30-handoff.txt"] and calls == []
          and stderr == "daily-overview-refresh-reminder-mark: no mark was written, because "
          "2026-10-01 is after today's Pacific date.\n"
          "Run this again without --shown-on-pacific-date, or with the date the user was "
          "shown the refresh.\n", f"{code} {calls!r} {stderr!r}")
    malformed = subprocess.run([sys.executable, str(SCRIPT_PATH), "handoff",
                                "--shown-on-pacific-date", "yesterday"],
                               capture_output=True, text=True, check=False)
    check("a date that is not YYYY-MM-DD is a bad invocation, exit 2",
          malformed.returncode == 2, f"{malformed.returncode} {malformed.stderr}")

    no_system = subprocess.run([sys.executable, str(SCRIPT_PATH)],
                               capture_output=True, text=True, check=False)
    check("no system at all is a bad invocation, exit 2",
          no_system.returncode == 2, f"{no_system.returncode} {no_system.stderr}")


def run_read_cases(workspace: Path):
    fixture = Fixture(workspace / "marks-read")
    marks, calls = fixture.read("2026-09-30")
    check("an absent marks directory reads as holding no mark",
          marks == {} and calls == ["nedlern@ned-box"], f"{marks!r} {calls!r}")

    fixture.run(["handoff"])
    fixture.run(["cold-read"])
    (fixture.marks / "2026-09-29-handoff.txt").write_text("2026-09-29T20:00:00Z\n",
                                                           encoding="utf-8")
    (fixture.marks / "2026-10-01-handoff.txt").write_text("2026-10-01T20:00:00Z\n",
                                                           encoding="utf-8")
    (fixture.marks / "notes.txt").write_text("not a mark\n", encoding="utf-8")
    (fixture.marks / "2026-09-30-handoff.txt.partial").write_text("x\n", encoding="utf-8")
    marks, calls = fixture.read("2026-09-30")
    check("the marks read are the named date's, one per system, with their text",
          marks == {"2026-09-30-handoff.txt": "2026-10-01T03:30:00Z\n",
                    "2026-09-30-cold-read.txt": "2026-10-01T03:30:00Z\n"}, repr(marks))
    check("from the Mac, the marks are read in one ssh call to nedlern@ned-box",
          calls == ["nedlern@ned-box"], repr(calls))

    marks, calls = fixture.read("2026-09-30", hostname="ned-box")
    check("on ned-box, the marks are read locally with no ssh",
          sorted(marks) == ["2026-09-30-cold-read.txt", "2026-09-30-handoff.txt"]
          and calls == [], f"{marks!r} {calls!r}")

    failed = None
    try:
        fixture.read("2026-09-30", ssh_body="echo 'ssh: connect to host ned-box port 22: "
                                            "No route to host' >&2\nexit 255")
    except Exception as error:
        failed = error
    check("when ned-box cannot be reached, the read raises with ssh's first line",
          type(failed).__name__ == "DailyMemoryReviewReadOrWriteFailed"
          and "ssh nedlern@ned-box exited 255: ssh: connect to host ned-box port 22: "
              "No route to host" in str(failed), repr(failed))

    check("a mark is named for its Pacific date and its system",
          mark.daily_overview_refresh_reminder_mark_file_name("2026-09-30", "cold-read")
          == "2026-09-30-cold-read.txt")
    check("the day of a moment is its date in America/Los_Angeles",
          mark.pacific_date_of(PACIFIC_EVENING_THAT_IS_TOMORROW_IN_UTC) == "2026-09-30"
          and mark.pacific_date_of(datetime(2026, 10, 1, 7, 0, tzinfo=timezone.utc))
          == "2026-10-01",
          mark.pacific_date_of(PACIFIC_EVENING_THAT_IS_TOMORROW_IN_UTC))
    check("a mark's text is a time when it is the UTC time a mark holds",
          mark.reminder_mark_text_is_a_time("2026-10-01T03:30:00Z\n")
          and not mark.reminder_mark_text_is_a_time("")
          and not mark.reminder_mark_text_is_a_time("shown to the user\n")
          and not mark.reminder_mark_text_is_a_time("2026-10-01"))


with tempfile.TemporaryDirectory() as temporary_directory:
    run_mark_cases(Path(temporary_directory))
    run_read_cases(Path(temporary_directory))

if failures:
    print(f"\n{len(failures)} case(s) failed")
    sys.exit(1)
print("\nall cases passed")
