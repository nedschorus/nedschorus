#!/usr/bin/env python3
"""Write a user-alert naming each credential file in the home directory that no cold-read-cell is denied.

    python3 <this file>

On Linux the cold-read-cells' sandboxes deny a reviewer program only the folders CREDENTIAL_DIRECTORIES
lists in nc-systems/cold-read/cold-read-cell-common.py, not files matched by CREDENTIAL_FILE_NAME_PATTERNS.
A file matching one of those patterns anywhere else under the home directory is readable to every
reviewer. This program walks the home directory, read from HOME, skipping those folders and the log-store
(~/nedschorus-logs, whose test leftovers match the patterns but hold no credential), and when it finds
such a file writes one user-alert naming every one found, through
nc-systems/general-tools/user-alerts-pending-and-claimed-files-write-claim-release-and-delete-common.py.
It keeps no state, so the alert comes again each day until the file's folder is added to
CREDENTIAL_DIRECTORIES or the file is moved or deleted.

It runs once a day on ned-box, from the table nc-systems/general-tools/scheduled-jobs-on-each-machine.json,
which nc-systems/general-tools/install-scheduled-jobs-on-this-machine.py installs as this cron line:
    45 7 * * * /usr/bin/python3 /home/nedlern/Projects/nedschorus/nc-systems/cold-read/cold-read-cell-credential-files-outside-denied-directories-daily-check-user-alert-write.py >> /home/nedlern/.claude/cold-read-cell-credential-files-outside-denied-directories-daily-check-user-alert-write.log 2>&1

Not handled: a folder this user cannot read is skipped, because the reviewers run as the same user and
cannot read it either; a folder removed while the walk runs is skipped. Symbolic links to folders are not
followed. Only the two patterns are looked for: a credential file with any other name is not found.

Exit status: 0 when nothing was found or the alert was written. 1 when the walk or the alert write failed;
a failed walk is itself reported in a user-alert, and when that write fails too the error is printed only,
to the cron log above. The program changes nothing but the user-alerts directory.
"""
import argparse
import fnmatch
import importlib.util
import os
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]


def _load(name, path):
    specification = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


cell_common = _load("cold_read_cell_common", REPOSITORY / "nc-systems" / "cold-read" / "cold-read-cell-common.py")
user_alerts = _load(
    "user_alerts_pending_and_claimed_files_write_claim_release_and_delete_common",
    REPOSITORY / "nc-systems" / "general-tools"
    / "user-alerts-pending-and-claimed-files-write-claim-release-and-delete-common.py")

THIS_PROGRAM = "nc-systems/cold-read/cold-read-cell-credential-files-outside-denied-directories-daily-check-user-alert-write.py"
FOUND_TITLE = "A credential file on ned-box is readable to the cold-read-cells' reviewer programs"
FOUND_ACTION = (
    "An agent on ned-box can, after asking the user which: add the file's folder to CREDENTIAL_DIRECTORIES in "
    "nc-systems/cold-read/cold-read-cell-common.py in a pull request, if the file holds a credential that must stay "
    "there; or move the file into a folder already listed. Only the user can say whether the file holds a credential.")
FAILED_TITLE = "The daily search of ned-box for credential files the cold-read-cells can read failed"
FAILED_ACTION = (
    f"An agent on ned-box can run python3 {THIS_PROGRAM} by hand, read the error it prints, and fix its cause; "
    "until then a new credential file outside CREDENTIAL_DIRECTORIES goes unreported.")


def skipped_directories(home):
    return {Path(directory) for directory in cell_common.CREDENTIAL_DIRECTORIES} | {home / "nedschorus-logs"}


def _raise_unless_unreadable_or_gone(error):
    # The reviewers run as this same user, so a folder this user cannot read is no leak.
    if not isinstance(error, (PermissionError, FileNotFoundError)):
        raise error


def credential_files_outside_denied_directories(home):
    """Every file under home whose name matches CREDENTIAL_FILE_NAME_PATTERNS and that no skipped directory holds."""
    skipped = skipped_directories(home)
    found = []
    for directory, subdirectories, files in os.walk(home, onerror=_raise_unless_unreadable_or_gone):
        subdirectories[:] = [name for name in subdirectories if Path(directory) / name not in skipped]
        found += [Path(directory) / name for name in files
                  if any(fnmatch.fnmatchcase(name, pattern) for pattern in cell_common.CREDENTIAL_FILE_NAME_PATTERNS)]
    return sorted(found)


def main(argv=None):
    argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter).parse_args(argv)
    home = Path.home()
    try:
        found = credential_files_outside_denied_directories(home)
    except OSError as error:
        text = f"The search of {home} for credential files stopped: {error!r}"
        print(text, file=sys.stderr)
        try:
            user_alerts.user_alert_write_to_pending(FAILED_TITLE, text, FAILED_ACTION)
        except OSError as alert_error:
            print(f"The user-alert saying so could not be written either: {alert_error!r}", file=sys.stderr)
        return 1
    if not found:
        print(f"No credential file outside CREDENTIAL_DIRECTORIES and the log-store under {home}.")
        return 0
    text = ("Each file below matches CREDENTIAL_FILE_NAME_PATTERNS and is in no folder of CREDENTIAL_DIRECTORIES, "
            "so on Linux every reviewer program a cold-read-cell starts can read it:\n"
            + "\n".join(str(path) for path in found))
    print(text)
    try:
        alert_id = user_alerts.user_alert_write_to_pending(FOUND_TITLE, text, FOUND_ACTION)
    except OSError as error:
        print(f"The user-alert naming these files could not be written: {error!r}", file=sys.stderr)
        return 1
    print(f"Wrote user-alert {alert_id}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
