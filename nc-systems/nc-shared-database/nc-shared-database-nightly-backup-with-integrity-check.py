#!/usr/bin/env python3
"""Copy the nc-shared-database into ~/backups/nc-shared-database/ on ned-box, and check the copy.

Usage:
  nc-systems/nc-shared-database/nc-shared-database-nightly-backup-with-integrity-check.py
      [--database PATH] [--backup-directory DIR]

  --database          default ~/.local/state/nedschorus/nc-shared-database.sqlite3
  --backup-directory  default ~/backups/nc-shared-database

ned-box runs it each night, from the table
nc-systems/general-tools/scheduled-jobs-on-each-machine.json, which
nc-systems/general-tools/install-scheduled-jobs-on-this-machine.py installs as:

    15 2 * * * /usr/bin/python3 /home/nedlern/Projects/nedschorus/nc-systems/nc-shared-database/nc-shared-database-nightly-backup-with-integrity-check.py >> /home/nedlern/.claude/nc-shared-database-nightly-backup-with-integrity-check.log 2>&1

The copy is made with SQLite's online backup, never a plain file copy, which
can catch the file mid-write, into nc-shared-database-<UTC time>.sqlite3, as
a single file the Mac's nightly job can copy. The copy is checked with
PRAGMA integrity_check:
  - when the check passes, the copy is kept, and the 14 newest copies are kept
    and older ones deleted;
  - when the check fails, the older copies stay as they are, the copy is
    renamed to end in .failed-integrity-check, and the program prints the
    check's output, writes it as a user-alert and exits 1.

Any other failure, such as a database that cannot be opened, writes a user-alert
naming the error, then ends with Python's traceback and exit 1. A user-alert is
written through
nc-systems/general-tools/user-alerts-pending-and-claimed-files-write-claim-release-and-delete-common.py,
because cron appends this program's output to a log no one reads. When the
user-alert cannot be written either, both tracebacks go to that log.

Exit codes: 0 a copy was made and passed its check; 1 the copy failed its check,
or any other failure.
"""

import argparse
import importlib.util
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

PROGRAM = "nc-systems/nc-shared-database/nc-shared-database-nightly-backup-with-integrity-check.py"
BACKUP_DIRECTORY = Path.home() / "backups" / "nc-shared-database"
COPIES_KEPT = 14
FAILED_CHECK_SUFFIX = ".failed-integrity-check"
EXIT_COPY_KEPT = 0
EXIT_COPY_FAILED_ITS_CHECK = 1


def _load(name, path):
    specification = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


service = _load("nc_shared_database_service",
                Path(__file__).resolve().with_name("nc-shared-database-service.py"))
user_alerts = _load(
    "user_alerts_pending_and_claimed_files_write_claim_release_and_delete_common",
    Path(__file__).resolve().parents[1] / "general-tools"
    / "user-alerts-pending-and-claimed-files-write-claim-release-and-delete-common.py")

FAILED_CHECK_TITLE = "The nightly backup copy of the nc-shared-database failed its integrity check"
FAILED_CHECK_ACTION = (
    "An agent on ned-box can follow the 'What to do' steps in the alert text. If the database itself "
    "fails its check, only the user can decide on a restore.")
FAILED_TITLE = "The nightly backup of the nc-shared-database on ned-box failed, so no new copy was kept"
FAILED_ACTION = (
    f"An agent on ned-box can run python3 {PROGRAM} by hand, read the error it prints, and fix its cause; "
    "until then each night's run fails the same way and the newest backup copy grows older.")


def integrity_check(connection):
    return [row[0] for row in connection.execute("PRAGMA integrity_check")]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--database", default=str(service.NC_SHARED_DATABASE_FILE_PATH))
    parser.add_argument("--backup-directory", default=str(BACKUP_DIRECTORY))
    arguments = parser.parse_args(argv)
    try:
        return back_up_and_check(arguments)
    except Exception as error:
        database = Path(arguments.database)
        user_alerts.user_alert_write_to_pending(
            FAILED_TITLE,
            f"{PROGRAM} stopped with {error!r} while backing up {database} into "
            f"{arguments.backup_directory}. The database file "
            f"{'exists' if database.exists() else 'does not exist'}. The traceback is in "
            f"/home/nedlern/.claude/nc-shared-database-nightly-backup-with-integrity-check.log on ned-box.",
            FAILED_ACTION)
        raise


def back_up_and_check(arguments):
    backup_directory = Path(arguments.backup_directory)
    backup_directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    copy_path = backup_directory / f"nc-shared-database-{stamp}.sqlite3"
    partial_path = copy_path.with_name(copy_path.name + ".partial")

    # mode=rw: a missing database must fail here, not be created empty.
    source = sqlite3.connect(f"file:{arguments.database}?mode=rw", uri=True, timeout=30,
                             isolation_level=None)
    copy = sqlite3.connect(str(partial_path), isolation_level=None)
    try:
        source.backup(copy)
        copy.execute("PRAGMA journal_mode=DELETE")
        check = integrity_check(copy)
        passed = check == ["ok"]
        if passed:
            highest_sequence = copy.execute("SELECT max(sequence) FROM event").fetchone()[0]
    finally:
        copy.close()
        source.close()

    if not passed:
        failed_path = copy_path.with_name(copy_path.name + FAILED_CHECK_SUFFIX)
        partial_path.rename(failed_path)
        # Double quotes only, so the same command also works inside ssh's single quotes.
        check_command = (f'python3 -c "import sqlite3, sys; print(sqlite3.connect(sys.argv[1])'
                         f'.execute(sys.argv[2]).fetchall())" "{arguments.database}" '
                         f'"PRAGMA integrity_check"')
        failure = (f"{PROGRAM}: FAILED — the copy of {arguments.database} failed PRAGMA "
                   f"integrity_check, so it is not kept as a backup and the older copies in "
                   f"{backup_directory} stay as they are. The failed copy is {failed_path}. "
                   f"The check printed:\n" + "\n".join(check) + "\n"
                   f"What to do: check the database itself. On ned-box run\n"
                   f"  {check_command}\n"
                   f"or from the Mac run\n"
                   f"  ssh nedlern@ned-box '{check_command}'\n"
                   f"If the command itself fails, such as with a Python traceback, it checked "
                   f"nothing: it says nothing about the database, so find why it failed and run "
                   f"it again.\n"
                   f"If it prints [('ok',)], only the copy was damaged: delete the failed copy, on "
                   f"ned-box with `rm {failed_path}` or from the Mac with "
                   f"`ssh nedlern@ned-box 'rm {failed_path}'`; the next night's run makes a new "
                   f"copy.\n"
                   f"If it prints anything else, the database itself is damaged: leave the "
                   f"database and the copies as they are, and tell the user that the agent-seat "
                   f"database {arguments.database} fails its integrity check, quoting both checks' "
                   f"output; a restore is his decision. If you are a subagent, tell the agent that "
                   f"dispatched you instead, with the same quotes.")
        print(failure, file=sys.stderr)
        user_alerts.user_alert_write_to_pending(FAILED_CHECK_TITLE, failure, FAILED_CHECK_ACTION)
        return EXIT_COPY_FAILED_ITS_CHECK

    partial_path.rename(copy_path)
    for old_copy in sorted(backup_directory.glob("nc-shared-database-*.sqlite3"))[:-COPIES_KEPT]:
        old_copy.unlink()
    print(f"{PROGRAM}: kept {copy_path}, highest sequence number {highest_sequence}")
    return EXIT_COPY_KEPT


if __name__ == "__main__":
    sys.exit(main())
