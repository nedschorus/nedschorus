#!/usr/bin/env python3
"""Tests for daily-memory-review-mark.py.

Run: python3 nc-systems/handoff/tests/daily-memory-review-mark-test.py

No case reaches ned-box. The stores and the marks directory are fixture
directories, set through the program's constants; ned-box is played by an ssh
first on PATH that records the host of each call and runs the command it was
handed here; the machine's name is set per case; and the moment is passed in.

Prints one line per case and exits non-zero if any case fails.
"""

import contextlib
import hashlib
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
SCRIPT_PATH = SYSTEM_DIRECTORY / "daily-memory-review-mark.py"

_spec = importlib.util.spec_from_file_location("daily_memory_review_mark", SCRIPT_PATH)
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
        self.mac_store = root / "mac-memory-store"
        self.ned_box_store = root / "ned-box-memory-store"
        self.marks = root / "daily-memory-review-marks"
        self.fake_ssh_count = 0
        root.mkdir()
        for store in (self.mac_store, self.ned_box_store):
            store.mkdir()
            (store / "MEMORY.md").write_text("- [An entry](an-entry.md)\n", encoding="utf-8")
        (self.mac_store / "mac-entry.md").write_text("mac\n", encoding="utf-8")
        (self.ned_box_store / "ned-box-entry.md").write_text("box\n", encoding="utf-8")

    def run(self, argv, now=PACIFIC_EVENING_THAT_IS_TOMORROW_IN_UTC,
            ssh_body=SSH_THAT_RUNS_THE_COMMAND_HERE, hostname="a-mac-that-is-not-ned-box",
            ssh_timeout=None):
        """main's exit code, stdout, stderr, and the hosts the fake ssh was
        called for."""
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
            "MAC_MEMORY_STORE_DIRECTORY", "NED_BOX_MEMORY_STORE_DIRECTORY",
            "DAILY_MEMORY_REVIEW_MARKS_DIRECTORY", "DAILY_MEMORY_REVIEW_MARK_SSH_TIMEOUT_SECONDS")}
        mark.MAC_MEMORY_STORE_DIRECTORY = str(self.mac_store)
        mark.NED_BOX_MEMORY_STORE_DIRECTORY = str(self.ned_box_store)
        mark.DAILY_MEMORY_REVIEW_MARKS_DIRECTORY = str(self.marks)
        if ssh_timeout is not None:
            mark.DAILY_MEMORY_REVIEW_MARK_SSH_TIMEOUT_SECONDS = ssh_timeout
        saved_gethostname = socket.gethostname
        socket.gethostname = lambda: hostname
        original_path = os.environ.get("PATH", "")
        os.environ["PATH"] = f"{directory}{os.pathsep}{original_path}"
        stdout, stderr = io.StringIO(), io.StringIO()
        try:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                code = mark.main(argv, now=now)
        finally:
            os.environ["PATH"] = original_path
            socket.gethostname = saved_gethostname
            for name, value in saved.items():
                setattr(mark, name, value)
        recorded = calls.read_text(encoding="utf-8").splitlines() if calls.exists() else []
        return code, stdout.getvalue(), stderr.getvalue(), recorded

    def mark_files(self):
        return sorted(path.name for path in self.marks.iterdir()) if self.marks.is_dir() else []


def run_mark_cases(workspace: Path):
    fixture = Fixture(workspace / "marks-from-the-mac")

    # Under Tokyo's zone the machine's own date is 2026-10-01; the mark is
    # dated by the Pacific one.
    with local_time_zone("Asia/Tokyo"):
        code, stdout, stderr, calls = fixture.run(["started"])
    started = fixture.marks / "2026-09-30-started.txt"
    check("started, from the Mac, writes today's started mark over ssh to nedlern@ned-box",
          code == 0 and started.is_file() and calls == ["nedlern@ned-box"],
          f"{code} {fixture.mark_files()} {calls!r}\n{stderr}")
    check("the mark is dated by the Pacific date, whatever the machine's zone",
          fixture.mark_files() == ["2026-09-30-started.txt"], repr(fixture.mark_files()))
    check("the started mark holds the UTC time it was written",
          started.is_file() and started.read_text(encoding="utf-8") == "2026-10-01T03:30:00Z\n",
          repr(started.read_text(encoding="utf-8") if started.is_file() else None))
    check("started prints where the mark was written",
          stdout == "daily-memory-review-mark: started recorded for 2026-09-30 in "
          f"nedlern@ned-box:{fixture.marks}/2026-09-30-started.txt\n", stdout)

    code, stdout, stderr, calls = fixture.run(["done"])
    done = fixture.marks / "2026-09-30-done.txt"
    expected_digest = mark.memory_stores_digest(
        {"MEMORY.md": b"- [An entry](an-entry.md)\n", "mac-entry.md": b"mac\n"},
        {"MEMORY.md": b"- [An entry](an-entry.md)\n", "ned-box-entry.md": b"box\n"})
    check("done, from the Mac, reads ned-box's store and writes the mark, both over ssh",
          code == 0 and calls == ["nedlern@ned-box", "nedlern@ned-box"],
          f"{code} {calls!r}\n{stderr}")
    check("the done mark holds the digest of both stores as they are",
          done.is_file() and done.read_text(encoding="utf-8") == expected_digest + "\n",
          repr(done.read_text(encoding="utf-8") if done.is_file() else None))

    code, stdout, stderr, calls = fixture.run(
        ["started"], ssh_body="echo 'ssh: connect to host ned-box port 22: No route to host' >&2\n"
                              "echo 'second line' >&2\nexit 255")
    check("when ned-box cannot be reached, the mark is not written and the exit is 1",
          code == 1 and fixture.mark_files() == ["2026-09-30-done.txt", "2026-09-30-started.txt"]
          and stdout == "", f"{code} {fixture.mark_files()} {stdout!r}")
    check("when ned-box cannot be reached, stderr carries ssh's first line and what to do",
          stderr == "daily-memory-review-mark: the started mark was not written (ssh "
          "nedlern@ned-box exited 255: ssh: connect to host ned-box port 22: No route to "
          "host) — tell the user what it said, and run this again once the cause is fixed.\n",
          stderr)

    code, stdout, stderr, calls = fixture.run(["done"], ssh_body="exec sleep 30", ssh_timeout=1)
    check("when ssh times out, done is not written and stderr says so",
          code == 1 and "ssh nedlern@ned-box timed out after 1 s" in stderr,
          f"{code}\n{stderr}")

    on_ned_box = Fixture(workspace / "marks-on-ned-box")
    code, stdout, stderr, calls = on_ned_box.run(["started"], hostname="ned-box")
    check("started, on ned-box, writes the mark locally with no ssh",
          code == 0 and on_ned_box.mark_files() == ["2026-09-30-started.txt"] and calls == [],
          f"{code} {on_ned_box.mark_files()} {calls!r}\n{stderr}")
    code, stdout, stderr, calls = on_ned_box.run(["done"], hostname="ned-box")
    check("done, on ned-box, writes nothing and says to run it from a Mac seat",
          code == 1 and on_ned_box.mark_files() == ["2026-09-30-started.txt"] and calls == []
          and stderr == "daily-memory-review-mark: run `done` from a Mac seat when you "
          "are on ned-box.\n", f"{code} {on_ned_box.mark_files()} {calls!r}\n{stderr}")

    invalid = subprocess.run([sys.executable, str(SCRIPT_PATH), "finished"],
                             capture_output=True, text=True, check=False)
    check("a mark other than started or done is a bad invocation, exit 2",
          invalid.returncode == 2, f"{invalid.returncode} {invalid.stderr}")


def run_store_and_digest_cases(workspace: Path):
    fixture = Fixture(workspace / "stores")
    (fixture.mac_store / ".DS_Store").write_bytes(b"\x00finder")
    (fixture.mac_store / "a-directory").mkdir()
    store, marks = mark.read_memory_store_and_review_marks(None, str(fixture.mac_store), "", 5)
    check("a store's files are its regular files, but those whose names begin with a dot",
          store == {"MEMORY.md": b"- [An entry](an-entry.md)\n", "mac-entry.md": b"mac\n"}
          and marks == {}, repr((store, marks)))
    absent, _ = mark.read_memory_store_and_review_marks(None, str(workspace / "absent"), "", 5)
    check("an absent store reads as empty", absent == {}, repr(absent))
    check("an entry is any file of the store but MEMORY.md",
          mark.memory_store_entry_count(store) == 1, repr(store))

    fixture.marks.mkdir()
    (fixture.marks / "2026-09-28-done.txt").write_text("digest-of-the-28th\n", encoding="utf-8")
    (fixture.marks / "2026-09-29-done.txt").write_text("digest-of-the-29th\n", encoding="utf-8")
    (fixture.marks / "2026-09-30-started.txt").write_text("2026-09-30T19:05:00Z\n",
                                                            encoding="utf-8")
    (fixture.marks / "notes.txt").write_text("not a mark\n", encoding="utf-8")
    _, marks = mark.read_memory_store_and_review_marks(None, "", str(fixture.marks), 5)
    check("the marks read are the started and done files, by name",
          sorted(marks) == ["2026-09-28-done.txt", "2026-09-29-done.txt",
                            "2026-09-30-started.txt"], repr(marks))
    check("the latest done mark is the one with the latest date",
          mark.latest_done_mark(marks) == ("2026-09-29", "digest-of-the-29th"),
          repr(mark.latest_done_mark(marks)))
    check("with no done mark there is no latest one",
          mark.latest_done_mark({"2026-09-30-started.txt": "x"}) is None)

    mac = {"MEMORY.md": b"index\n", "entry.md": b"one\n"}
    ned_box = {"MEMORY.md": b"index\n"}
    base = mark.memory_stores_digest(mac, ned_box)
    check("the digest is sha256 over each store's name and each file's name, length and "
          "content, the Mac's store first",
          base == hashlib.sha256(
              b"mac\0MEMORY.md\x006\0index\n" b"mac\0entry.md\x004\0one\n"
              b"ned-box\0MEMORY.md\x006\0index\n").hexdigest(), base)
    check("the digest changes when an entry's content changes",
          mark.memory_stores_digest({**mac, "entry.md": b"two\n"}, ned_box) != base)
    check("the digest changes when an entry is added",
          mark.memory_stores_digest(mac, {**ned_box, "new.md": b""}) != base)
    check("the digest changes when an entry is renamed",
          mark.memory_stores_digest({"MEMORY.md": b"index\n", "renamed.md": b"one\n"},
                                    ned_box) != base)
    check("the digest changes when an entry moves to the other store",
          mark.memory_stores_digest({"MEMORY.md": b"index\n"},
                                    {"MEMORY.md": b"index\n", "entry.md": b"one\n"}) != base)

    check("ned-box's store as the Mac mounts it is the same store under /Volumes/nedhome, "
          "the Mac's mount of ned-box's home",
          getattr(mark, "NED_BOX_MEMORY_STORE_MAC_MOUNT_DIRECTORY", None)
          == "/Volumes/nedhome" + mark.NED_BOX_MEMORY_STORE_DIRECTORY[len("/home/nedlern"):]
          and mark.NED_BOX_MEMORY_STORE_DIRECTORY.startswith("/home/nedlern/"),
          repr(getattr(mark, "NED_BOX_MEMORY_STORE_MAC_MOUNT_DIRECTORY", None)))


with tempfile.TemporaryDirectory() as temporary_directory:
    run_mark_cases(Path(temporary_directory))
    run_store_and_digest_cases(Path(temporary_directory))

if failures:
    print(f"\n{len(failures)} case(s) failed")
    sys.exit(1)
print("\nall cases passed")
