#!/usr/bin/env python3
"""Tests for nc-systems/nc-shared-database/nc-shared-database-nightly-backup-with-integrity-check.py.

The cases back up a database made by the service's own schema under a
temporary directory: a copy kept as one file, 14 copies kept, a copy that
fails its integrity check, which is injected because SQLite's backup does not
make one, with the check command its message prints run as printed, an event
stored between the backup and the read of the copy's highest sequence number,
and a database that does not exist. HOME points into the temporary directory,
so the user-alert the failed integrity check writes never reaches the user's real
user-alerts directory.

Run: python3 nc-systems/nc-shared-database/tests/nc-shared-database-nightly-backup-with-integrity-check-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import importlib.util
import io
import json
import os
import sqlite3
import subprocess
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

DIRECTORY = Path(__file__).resolve().parents[1]


def load(name, file_name):
    spec = importlib.util.spec_from_file_location(name, DIRECTORY / file_name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


service = load("nc_shared_database_service", "nc-shared-database-service.py")
backup = load("nc_shared_database_nightly_backup_with_integrity_check",
              "nc-shared-database-nightly-backup-with-integrity-check.py")

failures = 0


def check(name, condition, detail=None):
    global failures
    if condition:
        print(f"PASS  {name}")
    else:
        failures += 1
        print(f"FAIL  {name}: {detail!r}")


def pending_user_alerts():
    return [json.loads(path.read_text(encoding="utf-8"))
            for path in sorted((backup.user_alerts.user_alerts_directory() / "pending").glob("*.json"))]


def run(database, backup_directory):
    printed, errors = io.StringIO(), io.StringIO()
    with redirect_stdout(printed), redirect_stderr(errors):
        code = backup.main(["--database", str(database),
                            "--backup-directory", str(backup_directory)])
    return code, printed.getvalue(), errors.getvalue()


with tempfile.TemporaryDirectory() as scratch:
    scratch = Path(scratch)
    os.environ["HOME"] = str(scratch / "home")
    database = scratch / "nc-shared-database.sqlite3"
    service.create_nc_shared_database_if_absent(database)
    live = sqlite3.connect(str(database), isolation_level=None)
    backups = scratch / "backups"

    code, printed, errors = run(database, backups)
    check("a database with no event yet is backed up, with no highest sequence number, "
          "and no user-alert is written",
          code == 0 and "highest sequence number None" in printed and pending_user_alerts() == [],
          (code, printed, errors))

    for number in range(1, 8):
        live.execute("INSERT INTO event (event_id, machine, operation, received_at, body) "
                     "VALUES (?, 'mac', 'agent-seat-paused', 'now', '{}')", (f"e{number}",))
    live.execute("DELETE FROM event WHERE sequence = 7")
    for first_copy in backups.iterdir():
        first_copy.unlink()
    old_copies = [backups / f"nc-shared-database-20260101T0000{second:02d}Z.sqlite3"
                  for second in range(14)]
    for old_copy in old_copies:
        old_copy.write_bytes(b"old")
    code, printed, errors = run(database, backups)
    kept = sorted(backups.glob("nc-shared-database-*.sqlite3"))
    newest = kept[-1]
    copy = sqlite3.connect(str(newest))
    check("the copy is kept as one file, with every event",
          code == 0 and newest.name.startswith("nc-shared-database-2")
          and copy.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
          and copy.execute("SELECT count(*) FROM event").fetchone()[0] == 6
          and not list(backups.glob("*.partial")), (code, errors))
    copy.close()
    check("the 14 newest copies are kept and older ones deleted",
          len(kept) == 14 and not old_copies[0].exists() and old_copies[1].exists(),
          [path.name for path in kept])
    check("a kept copy is reported with its highest sequence number",
          str(newest) in printed and "highest sequence number 6" in printed, printed)

    live.execute("INSERT INTO event (event_id, machine, operation, received_at, body) "
                 "VALUES ('e8', 'mac', 'agent-seat-paused', 'now', '{}')")
    real_check = backup.integrity_check
    backup.integrity_check = lambda connection: ["*** in database main ***",
                                                 "Page 3 is never used"]
    code, printed, errors = run(database, backups)
    backup.integrity_check = real_check
    failed = list(backups.glob("*.failed-integrity-check"))
    check("a copy that fails its integrity check exits 1 and is not kept as a backup",
          code == 1 and len(failed) == 1
          and sorted(backups.glob("nc-shared-database-*.sqlite3")) == kept, (code, errors))
    check("after a failed check the older copies stay as they were", old_copies[1].exists())
    check("the failure names the failed copy, the database and what the check printed",
          str(failed[0]) in errors and str(database) in errors and "Page 3 is never used" in errors
          and "tell the user" in errors, errors)
    alerts = pending_user_alerts()
    check("a copy that fails its integrity check writes one user-alert carrying the failure "
          "as printed",
          len(alerts) == 1 and alerts[0]["title"] == backup.BACKUP_COPY_FAILED_INTEGRITY_CHECK_USER_ALERT_TITLE
          and alerts[0]["alert_text"] == errors.rstrip("\n")
          and alerts[0]["action"] == backup.BACKUP_COPY_FAILED_INTEGRITY_CHECK_USER_ALERT_ACTION_TEXT_SAYING_WHAT_AN_AGENT_CAN_DO, alerts)
    for alert_file in (backup.user_alerts.user_alerts_directory() / "pending").glob("*.json"):
        alert_file.unlink()
    commands = [line.strip() for line in errors.splitlines()
                if "PRAGMA integrity_check\"" in line]
    with tempfile.TemporaryDirectory() as fake_ssh_directory:
        # ssh runs its last argument in the remote user's shell; sh -c does the same here.
        fake_ssh = Path(fake_ssh_directory) / "ssh"
        fake_ssh.write_text('#!/bin/sh\nshift\nexec sh -c "$1"\n', encoding="utf-8")
        fake_ssh.chmod(0o755)
        environment = {**os.environ, "PATH": f"{fake_ssh_directory}:{os.environ['PATH']}"}
        outputs = [subprocess.run(command, shell=True, capture_output=True, text=True,
                                  env=environment).stdout.strip() for command in commands]
    check("the check command the failure prints works as printed, on ned-box and inside "
          "ssh nedlern@ned-box '...' from the Mac",
          len(commands) == 2 and commands[1].startswith("ssh nedlern@ned-box '")
          and outputs == ["[('ok',)]", "[('ok',)]"], (commands, outputs))
    check("the real integrity check passes a sound database",
          real_check(sqlite3.connect(str(database))) == ["ok"])

    for failed_copy in failed:
        failed_copy.unlink()
    highest_in_database_before = live.execute("SELECT max(sequence) FROM event").fetchone()[0]

    def store_an_event_then_check(connection):
        live.execute("INSERT INTO event (event_id, machine, operation, received_at, body) "
                     "VALUES ('after-the-backup', 'mac', 'agent-seat-paused', 'now', '{}')")
        return real_check(connection)

    backup.integrity_check = store_an_event_then_check
    code, printed, errors = run(database, backups)
    backup.integrity_check = real_check
    check("the highest sequence number reported is the copy's, not that of an event the "
          "database stored after the copy was made",
          code == 0 and f"highest sequence number {highest_in_database_before}" in printed
          and live.execute("SELECT max(sequence) FROM event").fetchone()[0]
          > highest_in_database_before, (code, printed, errors))

    missing = scratch / "missing.sqlite3"
    try:
        run(missing, backups)
        raised = None
    except sqlite3.OperationalError as error:
        raised = error
    check("a database that does not exist is an error, writes no user-alert, and no empty database is made",
          raised is not None and not missing.exists() and pending_user_alerts() == [], raised)

raise SystemExit(1 if failures else 0)
