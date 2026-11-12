#!/usr/bin/env python3
"""Tests for nc-systems/cold-read/cold-read-cell-credential-files-outside-denied-directories-daily-check-user-alert-write.py.

Each case builds a scratch home directory and runs the program with HOME set to it, so the real home
directory and the real user-alerts directory are never read or written.

Run: python3 nc-systems/cold-read/tests/cold-read-cell-credential-files-outside-denied-directories-daily-check-user-alert-write-test.py
Prints one line per case and exits non-zero if any case fails.
"""
import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

PROGRAM = (Path(__file__).resolve().parents[1]
           / "cold-read-cell-credential-files-outside-denied-directories-daily-check-user-alert-write.py")
_specification = importlib.util.spec_from_file_location("credential_files_daily_check", PROGRAM)
program = importlib.util.module_from_spec(_specification)
_specification.loader.exec_module(program)

FAILURES = []


def check(name, condition, detail=""):
    print(("PASS  " if condition else "FAIL  ") + name)
    if not condition:
        print(f"      {detail!r}")
        FAILURES.append(name)


def make_file(home, relative):
    path = home / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("secret\n", encoding="utf-8")
    return path


def run(home):
    environment = dict(os.environ, HOME=str(home))
    return subprocess.run([sys.executable, str(PROGRAM)], env=environment, capture_output=True, text=True)


def pending_alerts(home):
    pending = home / ".local" / "state" / "nedschorus" / "user-alerts" / "pending"
    return [json.loads(path.read_text(encoding="utf-8")) for path in sorted(pending.glob("*.json"))]


@contextlib.contextmanager
def scratch_home():
    with tempfile.TemporaryDirectory() as directory:
        yield Path(directory).resolve()


@contextlib.contextmanager
def home_environment(home):
    saved = os.environ.get("HOME")
    os.environ["HOME"] = str(home)
    try:
        yield
    finally:
        os.environ["HOME"] = saved


with scratch_home() as home:
    reported = [make_file(home, "project/.env"), make_file(home, "a/b/github.token"),
                make_file(home, ".ssh-old/.env")]
    for relative in (".ssh/id.token", ".config/gh/hosts.token", ".config/nedschorus/x.token",
                     ".steam/steam.token", "nedsmessenger/.env", "nedsmessenger/secrets/a.token",
                     "nedschorus-logs/seats/test/.env", "project/.env.local", "project/token",
                     "other/.env/inside"):
        make_file(home, relative)
    result = run(home)
    alerts = pending_alerts(home)
    check("a *.token or .env file outside every listed folder and the log-store is named in one user-alert, "
          "and nothing inside a listed folder, inside the log-store, or merely like the patterns is",
          result.returncode == 0 and len(alerts) == 1
          and alerts[0]["title"] == program.FOUND_TITLE and alerts[0]["action"] == program.FOUND_ACTION
          and alerts[0]["alert_text"].splitlines()[1:] == [str(path) for path in sorted(reported)],
          (result, alerts))

with scratch_home() as home:
    make_file(home, ".ssh/id.token")
    result = run(home)
    check("with no credential file outside the listed folders, no user-alert is written and the exit is 0",
          result.returncode == 0 and pending_alerts(home) == [] and "No credential file" in result.stdout,
          result)

if os.geteuid() != 0:
    with scratch_home() as home:
        make_file(home, "locked/.env")
        (home / "locked").chmod(0)
        try:
            result = run(home)
        finally:
            (home / "locked").chmod(0o755)
        check("a folder this user cannot read is skipped without failing, since the reviewers cannot read it either",
              result.returncode == 0 and pending_alerts(home) == [], result)

with scratch_home() as home:
    make_file(home, "project/.env")
    make_file(home, ".local/state/nedschorus/user-alerts")
    result = run(home)
    check("when the user-alert naming the files cannot be written, the error is printed and the exit is 1",
          result.returncode == 1 and "could not be written" in result.stderr
          and str(home / "project" / ".env") in result.stdout, result)

check("a folder that vanished during the walk, like an unreadable one, is skipped",
      program._raise_unless_unreadable_or_gone(PermissionError()) is None
      and program._raise_unless_unreadable_or_gone(FileNotFoundError()) is None)
try:
    program._raise_unless_unreadable_or_gone(OSError(5, "Input/output error"))
    raised = False
except OSError:
    raised = True
check("an input/output error during the walk is raised", raised)


def walk_that_fails(home):
    raise OSError(5, "Input/output error")


real_search = program.credential_files_outside_denied_directories
program.credential_files_outside_denied_directories = walk_that_fails
try:
    with scratch_home() as home, home_environment(home):
        errors = io.StringIO()
        with contextlib.redirect_stderr(errors):
            exit_code = program.main()
        alerts = pending_alerts(home)
        check("when the walk fails, a user-alert says so and the exit is 1",
              exit_code == 1 and len(alerts) == 1 and alerts[0]["title"] == program.FAILED_TITLE
              and "Input/output error" in alerts[0]["alert_text"], (exit_code, alerts, errors.getvalue()))

    real_write = program.user_alerts.user_alert_write_to_pending

    def write_that_fails(title, alert_text, action):
        raise OSError(28, "No space left on device")

    program.user_alerts.user_alert_write_to_pending = write_that_fails
    try:
        with scratch_home() as home, home_environment(home):
            errors = io.StringIO()
            with contextlib.redirect_stderr(errors):
                exit_code = program.main()
            check("when the walk fails and the user-alert saying so cannot be written, both errors are printed "
                  "and the exit is 1",
                  exit_code == 1 and "Input/output error" in errors.getvalue()
                  and "No space left on device" in errors.getvalue(), (exit_code, errors.getvalue()))
    finally:
        program.user_alerts.user_alert_write_to_pending = real_write
finally:
    program.credential_files_outside_denied_directories = real_search

if FAILURES:
    print(f"\n{len(FAILURES)} case(s) FAILED:")
    for name in FAILURES:
        print(f"  - {name}")
    sys.exit(1)
print("\nall cases passed")
