#!/usr/bin/env python3
"""Write a user-alert naming each file named *.token or .env in the home directory that the Linux sandboxes leave readable.

    python3 <this file>

On Linux the sandboxes of the Codex and agy cold-read-cells deny a reviewer program only the folders
CREDENTIAL_DIRECTORIES lists and the login files REVIEWER_PROGRAM_LOGIN_FILES lists, both in
nc-systems/cold-read/cold-read-cell-common.py, except that the agy cell's sandbox leaves agy's own login
files readable. They do not deny by the two name patterns of
CREDENTIAL_FILE_NAME_PATTERNS, `*.token` and `.env`; only the macOS sandboxes and the Claude cell's
Read(//**/<pattern>) rule do. A file with such a name anywhere else under the home directory is therefore
readable to the Codex and agy reviewer programs. This program walks the home directory, read from HOME,
skipping the folders CREDENTIAL_DIRECTORIES lists and the log-store (~/nedschorus-logs, whose test leftovers match the patterns but
hold no credential), and when it finds such a file writes one user-alert naming every one found, through
nc-systems/general-tools/user-alerts-pending-and-claimed-files-write-claim-release-and-delete-common.py.
It keeps no state, so the alert comes again each day until the file is moved into a folder
CREDENTIAL_DIRECTORIES lists or deleted, or its folder is added to CREDENTIAL_DIRECTORIES; a file directly
in the home folder can only be moved or deleted.

It runs once a day on ned-box, from the table nc-systems/general-tools/scheduled-jobs-on-each-machine.json,
which nc-systems/general-tools/install-scheduled-jobs-on-this-machine.py installs as this cron line:
    45 7 * * * /usr/bin/python3 /home/nedlern/Projects/nedschorus/nc-systems/cold-read/cold-read-cell-credential-files-outside-denied-directories-daily-check-user-alert-write.py >> /home/nedlern/.claude/cold-read-cell-credential-files-outside-denied-directories-daily-check-user-alert-write.log 2>&1

Skipped: a folder this user cannot read, because the reviewers run as the same user and cannot read it
either; a folder removed while the walk runs; the target of a symbolic link to a folder.
Not found: a credential file named by neither pattern.

Exit status: 0 when nothing was found or the alert naming the files was written. 1 when the walk failed,
whether or not the user-alert reporting that failure was written, or when the alert naming the files
could not be written; an error the program cannot put in a user-alert is printed only, to the cron log
above. The program writes only to the user-alerts directory, and cron appends its output to that log.
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
    "there; or move the file into a folder already listed. A file directly in the home folder can only be moved. "
    "Only the user can say whether the file holds a credential.")
NAME_PATTERNS = " or ".join(cell_common.CREDENTIAL_FILE_NAME_PATTERNS)
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
        text = (f"The search of {home} for files named {NAME_PATTERNS} outside CREDENTIAL_DIRECTORIES ended "
                f"before it had looked everywhere: {error!r}")
        print(text, file=sys.stderr)
        try:
            user_alerts.user_alert_write_to_pending(FAILED_TITLE, text, FAILED_ACTION)
        except OSError as alert_error:
            print(f"The user-alert saying so could not be written either, so no alert reached pending/: "
                  f"{alert_error!r}", file=sys.stderr)
        return 1
    if not found:
        print(f"The search found no file named {NAME_PATTERNS} under {home} outside the folders CREDENTIAL_DIRECTORIES "
              f"lists in nc-systems/cold-read/cold-read-cell-common.py and outside the log-store {home / 'nedschorus-logs'}.")
        return 0
    text = (f"Each file below is named {NAME_PATTERNS} and lies in no folder that CREDENTIAL_DIRECTORIES lists in "
            "nc-systems/cold-read/cold-read-cell-common.py, so on Linux the Codex and agy programs that the "
            "cold-read-cells start can read it:\n"
            + "\n".join(str(path) for path in found))
    print(text)
    try:
        alert_id = user_alerts.user_alert_write_to_pending(FOUND_TITLE, text, FOUND_ACTION)
    except OSError as error:
        print(f"The user-alert naming these files could not be written, so no alert reached pending/: {error!r}",
              file=sys.stderr)
        return 1
    print(f"This program wrote user-alert {alert_id} into the user-alerts pending/ folder.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
