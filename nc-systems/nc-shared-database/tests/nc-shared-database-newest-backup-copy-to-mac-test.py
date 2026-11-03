#!/usr/bin/env python3
"""Tests for nc-systems/nc-shared-database/nc-shared-database-newest-backup-copy-to-mac.py.

A fake `ssh` on PATH runs the remote command locally against a temporary
directory that plays ned-box's backup directory, and fails a chosen step on
request: the newest backup copied, a copy already on the Mac, no backup on
ned-box, and ssh failing while listing or while copying.

Run: python3 nc-systems/nc-shared-database/tests/nc-shared-database-newest-backup-copy-to-mac-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import importlib.util
import io
import os
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

PROGRAM_PATH = (Path(__file__).resolve().parents[1]
                / "nc-shared-database-newest-backup-copy-to-mac.py")
_spec = importlib.util.spec_from_file_location("nc_shared_database_newest_backup_copy_to_mac",
                                               PROGRAM_PATH)
copier = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(copier)

failures = 0


def check(name, condition, detail=None):
    global failures
    if condition:
        print(f"PASS  {name}")
    else:
        failures += 1
        print(f"FAIL  {name}: {detail!r}")


FAKE_SSH = """#!/bin/sh
for remote_command; do :; done
echo "$remote_command" >> "$FAKE_SSH_LOG"
case "$remote_command" in
  "$FAKE_SSH_FAIL"*) echo "ssh: connect to host ned-box port 22: No route to host" >&2; exit 255;;
esac
exec sh -c "$(printf '%s' "$remote_command" | sed "s#$NED_BOX_BACKUPS#$FAKE_REMOTE#g")"
"""


def run(mac_directory, fail=""):
    os.environ["FAKE_SSH_FAIL"] = fail or "never-matches"
    printed, errors = io.StringIO(), io.StringIO()
    with redirect_stdout(printed), redirect_stderr(errors):
        code = copier.main(["--mac-backup-directory", str(mac_directory)])
    return code, printed.getvalue(), errors.getvalue()


with tempfile.TemporaryDirectory() as scratch:
    scratch = Path(scratch)
    bin_directory = scratch / "bin"
    bin_directory.mkdir()
    (bin_directory / "ssh").write_text(FAKE_SSH, encoding="utf-8")
    (bin_directory / "ssh").chmod(0o755)
    remote = scratch / "ned-box-backups"
    log = scratch / "ssh.log"
    os.environ.update(PATH=f"{bin_directory}:{os.environ['PATH']}", FAKE_SSH_LOG=str(log),
                      FAKE_REMOTE=str(remote), NED_BOX_BACKUPS=copier.NED_BOX_NC_SHARED_DATABASE_BACKUP_DIRECTORY)
    mac = scratch / "mac" / "backups"

    check("ned-box's backup directory is the backup job's, under ned-box's home",
          copier.NED_BOX_NC_SHARED_DATABASE_BACKUP_DIRECTORY == "/home/nedlern/backups/nc-shared-database")
    code, printed, errors = run(mac)
    check("ssh failing while listing: exit 1, naming the step and what ssh said",
          code == 1 and "listing nedlern@ned-box:/home/nedlern/backups/nc-shared-database failed"
          in errors and "No such file" in errors
          and "Quote this message, from its first line, the program's name included, through "
              "the line that ends \"tries again.\"" in errors
          and "Say that copying" not in errors,
          (code, errors))

    remote.mkdir()
    (remote / "nc-shared-database-20261025T021500Z.sqlite3.failed-integrity-check").write_bytes(b"x")
    code, printed, errors = run(mac)
    check("no backup on ned-box: exit 1, pointing at the backup job's output file",
          code == 1 and "holds no backup" in errors
          and "nc-shared-database-nightly-backup-with-integrity-check.log" in errors,
          (code, errors))

    (remote / "nc-shared-database-20261023T021500Z.sqlite3").write_bytes(b"oldest")
    (remote / "nc-shared-database-20261024T021500Z.sqlite3").write_bytes(b"older")
    (remote / "nc-shared-database-20261026T021500Z.sqlite3").write_bytes(b"newest backup")
    (remote / "nc-shared-database-20261027T021500Z.sqlite3.partial").write_bytes(b"partial")
    code, printed, _ = run(mac, fail="cat ")
    check("ssh failing while copying: exit 1, and no copy or partial file is left on the Mac",
          code == 1 and list(mac.iterdir()) == [], (code, list(mac.iterdir())))

    code, printed, errors = run(mac)
    newest = mac / "nc-shared-database-20261026T021500Z.sqlite3"
    check("the newest backup is copied to the Mac under its own name, and nothing else is",
          code == 0 and newest.read_bytes() == b"newest backup"
          and [path.name for path in mac.iterdir()] == [newest.name]
          and str(newest) in printed, (code, printed, errors))
    log.write_text("", encoding="utf-8")
    code, printed, errors = run(mac)
    check("a backup the Mac already holds is not copied again",
          code == 0 and "already on the Mac" in printed
          and not any(line.startswith("cat ") for line in log.read_text().splitlines()),
          (code, printed, log.read_text()))
    check("ssh runs in batch mode against nedlern@ned-box",
          copier.SSH_COMMAND[-1] == "nedlern@ned-box" and "BatchMode=yes" in copier.SSH_COMMAND)

raise SystemExit(1 if failures else 0)
