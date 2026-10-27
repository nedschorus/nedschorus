#!/usr/bin/env python3
"""Tests for nc-systems/agent-seat-database/agent-seat-database-nightly-backup-with-integrity-check.py.

The cases back up a database made by the service's own schema under a
temporary directory: a copy kept as one file with the newest backup's mark
written into the database, 14 copies kept, a copy that fails its integrity
check, which is injected because SQLite's backup does not make one, and a
database that does not exist.

Run: python3 nc-systems/agent-seat-database/tests/agent-seat-database-nightly-backup-with-integrity-check-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import importlib.util
import io
import sqlite3
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

DIRECTORY = Path(__file__).resolve().parents[1]


def load(name, file_name):
    spec = importlib.util.spec_from_file_location(name, DIRECTORY / file_name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


service = load("agent_seat_database_service", "agent-seat-database-service.py")
backup = load("agent_seat_database_nightly_backup_with_integrity_check",
              "agent-seat-database-nightly-backup-with-integrity-check.py")

failures = 0


def check(name, condition, detail=None):
    global failures
    if condition:
        print(f"PASS  {name}")
    else:
        failures += 1
        print(f"FAIL  {name}: {detail!r}")


def run(database, backup_directory):
    printed, errors = io.StringIO(), io.StringIO()
    with redirect_stdout(printed), redirect_stderr(errors):
        code = backup.main(["--database", str(database),
                            "--backup-directory", str(backup_directory)])
    return code, printed.getvalue(), errors.getvalue()


def newest_backup_row(database):
    connection = sqlite3.connect(str(database))
    found = connection.execute("SELECT generation_id, highest_sequence FROM newest_backup").fetchall()
    connection.close()
    return found


with tempfile.TemporaryDirectory() as scratch:
    scratch = Path(scratch)
    database = scratch / "agent-seat-database.sqlite3"
    service.create_database_if_absent(database)
    live = sqlite3.connect(str(database), isolation_level=None)
    generation = live.execute("SELECT generation_id FROM database_generation").fetchone()[0]
    backups = scratch / "backups"

    code, printed, errors = run(database, backups)
    check("a database with no event yet is backed up, and its mark has no highest sequence number",
          code == 0 and newest_backup_row(database) == [(generation, None)], (code, errors))

    for number in range(1, 8):
        live.execute("INSERT INTO event (event_id, machine, operation, received_at, body) "
                     "VALUES (?, 'mac', 'agent-seat-paused', 'now', '{}')", (f"e{number}",))
    live.execute("DELETE FROM event WHERE sequence = 7")
    for first_copy in backups.iterdir():
        first_copy.unlink()
    old_copies = [backups / f"agent-seat-database-20260101T0000{second:02d}Z.sqlite3"
                  for second in range(14)]
    for old_copy in old_copies:
        old_copy.write_bytes(b"old")
    code, printed, errors = run(database, backups)
    kept = sorted(backups.glob("agent-seat-database-*.sqlite3"))
    newest = kept[-1]
    copy = sqlite3.connect(str(newest))
    check("the copy is kept as one file, with every event and the database's generation ID",
          code == 0 and newest.name.startswith("agent-seat-database-2")
          and copy.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
          and copy.execute("SELECT count(*) FROM event").fetchone()[0] == 6
          and copy.execute("SELECT generation_id FROM database_generation").fetchone()[0]
          == generation and not list(backups.glob("*.partial")), (code, errors))
    copy.close()
    check("the database's newest_backup holds the copy's own highest sequence number and "
          "generation ID", newest_backup_row(database) == [(generation, 6)],
          newest_backup_row(database))
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
          and sorted(backups.glob("agent-seat-database-*.sqlite3")) == kept, (code, errors))
    check("after a failed check the older copies and the database's newest_backup stay as they were",
          newest_backup_row(database) == [(generation, 6)] and old_copies[1].exists(),
          newest_backup_row(database))
    check("the failure names the failed copy, the database and what the check printed",
          str(failed[0]) in errors and str(database) in errors and "Page 3 is never used" in errors
          and "tell the user" in errors, errors)
    check("the real integrity check passes a sound database",
          real_check(sqlite3.connect(str(database))) == ["ok"])

    missing = scratch / "missing.sqlite3"
    try:
        run(missing, backups)
        raised = None
    except sqlite3.OperationalError as error:
        raised = error
    check("a database that does not exist is an error, and no empty database is made",
          raised is not None and not missing.exists(), raised)

raise SystemExit(1 if failures else 0)
