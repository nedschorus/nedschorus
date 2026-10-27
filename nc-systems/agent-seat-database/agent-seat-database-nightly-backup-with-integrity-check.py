#!/usr/bin/env python3
"""Copy the agent-seat database into ~/backups/agent-seat-database/ on ned-box, and check the copy.

Usage:
  nc-systems/agent-seat-database/agent-seat-database-nightly-backup-with-integrity-check.py
      [--database PATH] [--backup-directory DIR]

  --database          default ~/.local/state/nedschorus/agent-seat-database.sqlite3
  --backup-directory  default ~/backups/agent-seat-database

ned-box runs it each night, from the table
nc-systems/general-tools/scheduled-jobs-on-each-machine.json, which
nc-systems/general-tools/install-scheduled-jobs-on-this-machine.py installs as:

    15 2 * * * /usr/bin/python3 /home/nedlern/Projects/nedschorus/nc-systems/agent-seat-database/agent-seat-database-nightly-backup-with-integrity-check.py >> /home/nedlern/.claude/agent-seat-database-nightly-backup-with-integrity-check.log 2>&1

The copy is made with SQLite's online backup, never a plain file copy, which
can catch the file mid-write, into agent-seat-database-<UTC time>.sqlite3, as
a single file the Mac's nightly job can copy. The copy is checked with
PRAGMA integrity_check:
  - when the check passes, the copy is kept, the 14 newest copies are kept and
    older ones deleted, and the copy's own highest sequence number and generation
    ID are written into the database's newest_backup table, which every answer
    of the service gives, so the machines delete sent rows the copy holds;
  - when the check fails, the older copies stay as they are, newest_backup is
    not changed, the copy is renamed to end in .failed-integrity-check, which
    the page the sending job writes names, and the program prints the check's
    output and exits 1.

Exit codes: 0 a copy was made and passed its check; 1 the copy failed its check;
any other failure, such as a database that cannot be opened, ends with Python's
traceback and exit 1.
"""

import argparse
import importlib.util
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

PROGRAM = "nc-systems/agent-seat-database/agent-seat-database-nightly-backup-with-integrity-check.py"
BACKUP_DIRECTORY = Path.home() / "backups" / "agent-seat-database"
COPIES_KEPT = 14
FAILED_CHECK_SUFFIX = ".failed-integrity-check"
EXIT_COPY_KEPT = 0
EXIT_COPY_FAILED_ITS_CHECK = 1

_service_spec = importlib.util.spec_from_file_location(
    "agent_seat_database_service",
    Path(__file__).resolve().with_name("agent-seat-database-service.py"))
service = importlib.util.module_from_spec(_service_spec)
_service_spec.loader.exec_module(service)


def integrity_check(connection):
    return [row[0] for row in connection.execute("PRAGMA integrity_check")]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--database", default=str(service.DATABASE_PATH))
    parser.add_argument("--backup-directory", default=str(BACKUP_DIRECTORY))
    arguments = parser.parse_args(argv)
    backup_directory = Path(arguments.backup_directory)
    backup_directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    copy_path = backup_directory / f"agent-seat-database-{stamp}.sqlite3"
    partial_path = copy_path.with_name(copy_path.name + ".partial")

    # mode=rw: a missing database must fail here, not be created empty.
    source = sqlite3.connect(f"file:{arguments.database}?mode=rw", uri=True, timeout=30,
                             isolation_level=None)
    copy = sqlite3.connect(str(partial_path), isolation_level=None)
    try:
        source.backup(copy)
        copy.execute("PRAGMA journal_mode=DELETE")
        check = integrity_check(copy)
        if check == ["ok"]:
            highest_sequence = copy.execute("SELECT max(sequence) FROM event").fetchone()[0]
            generation = copy.execute(
                "SELECT generation_id FROM database_generation").fetchone()[0]
    finally:
        copy.close()

    if check != ["ok"]:
        failed_path = copy_path.with_name(copy_path.name + FAILED_CHECK_SUFFIX)
        partial_path.rename(failed_path)
        source.close()
        print(f"{PROGRAM}: FAILED — the copy of {arguments.database} failed PRAGMA "
              f"integrity_check, so it is not kept as a backup and the older copies in "
              f"{backup_directory} stay as they are. The failed copy is {failed_path}. "
              f"The check printed:\n" + "\n".join(check) + "\n"
              f"What to do: check the database itself, on ned-box (from the Mac, put the "
              f"command inside ssh nedlern@ned-box '...'):\n"
              f"  python3 -c \"import sqlite3; print(sqlite3.connect('{arguments.database}')"
              f".execute('PRAGMA integrity_check').fetchall())\"\n"
              f"If it prints [('ok',)], only the copy was damaged: delete the failed copy on "
              f"ned-box with `rm {failed_path}`; the next night's run makes a new copy.\n"
              f"If it prints anything else, the database itself is damaged: leave the "
              f"database and the copies as they are, and tell the user that the agent-seat "
              f"database {arguments.database} fails its integrity check, quoting both checks' "
              f"output; a restore is his decision. If you are a subagent, tell the agent that "
              f"dispatched you instead, with the same quotes.",
              file=sys.stderr)
        return EXIT_COPY_FAILED_ITS_CHECK

    partial_path.rename(copy_path)
    try:
        source.execute("BEGIN IMMEDIATE")
        source.execute("DELETE FROM newest_backup")
        source.execute("INSERT INTO newest_backup VALUES (?, ?)", (generation, highest_sequence))
        source.execute("COMMIT")
    finally:
        source.close()
    for old_copy in sorted(backup_directory.glob("agent-seat-database-*.sqlite3"))[:-COPIES_KEPT]:
        old_copy.unlink()
    print(f"{PROGRAM}: kept {copy_path}, highest sequence number {highest_sequence}")
    return EXIT_COPY_KEPT


if __name__ == "__main__":
    sys.exit(main())
