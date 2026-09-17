#!/usr/bin/env python3
"""Ship one sanity-check record directory to the log-store on ned-box.

Usage:
  scripts/sanity-check-record-ship.py <record directory>
  scripts/sanity-check-record-ship.py --all

WHY THIS EXISTS (user-ruled 2026-09-15, nedschorus#392). The reports and
`finding-dispositions.md` that scripts/sanity-check-attacks.py writes under
`sanity-check-records/` are logs: the user ruled on 2026-08-25 that review
records are kept as logs, and CLAUDE.md puts logs in the log-store, never in
the repository. Cold-read records reach it through
scripts/cold-read-record-ship.py; these had no way there at all, so the runner
told its caller to DELETE the record when the
work it served landed, and a sanity-check that shaped a design could not be
cited afterwards.

WHAT IT IS: the cold-read record shipper with the store's kind swapped.
scripts/cold-read-record-ship.py holds the ship logic and the store's rules --
ADD-ONLY, REFUSE ON DIFFERENCE, FAIL LOUDLY, what the store is, how ssh and
rsync are invoked, the store's README -- and this program imports it rather
than copying any of it, the way scripts/seat-shared-file-ship.py does. Read
that module's docstring for the rules; the only thing that differs here is the
kind: `sanity-check-records/` beside `cold-read-records/` in the store, and
`sanity-check-records/` in the checkout for --all.

ONE CONSEQUENCE OF ADD-ONLY WORTH KNOWING BEFORE YOU SHIP. A file already in
the store whose content differs from the local one is refused, not replaced.
So `finding-dispositions.md` shipped early and then edited is refused on the
next run: finish the triage, then ship, or ship the edited record under a `-2`
name as the record shipper's rule says. Nothing is lost either way -- a refusal
copies nothing and names every differing file.

WHO CALLS IT. scripts/sanity-check-attacks.py at the end of every run that
wrote reports, whatever the cells' outcome, printing this program's one line
as `record:`; and the requesting agent again after writing
`finding-dispositions.md`, when the add-only copy sends only that new file.
A shipping failure never fails the sanity check: the caller prints the line and
goes on, and the record stays on disk for a later run.

OUTPUT AND EXITS are the record shipper's, unchanged: one line per record
directory on stdout (`shipped:`, `REFUSED:`, `FAILED:`, or `skipped:` under
--all), everything else on stderr, and exit 0 when every directory shipped, 2
when any was refused and none failed, 1 when any failed, 64 for a bad
invocation.

THE DESTINATION is the record shipper's one constant with the kind swapped, so
a move of the store stays one edit in that file. Its environment override,
COLD_READ_RECORD_SHIP_DESTINATION, moves this kind with it, which is how the
tests point both at a scratch directory.
"""

import importlib.util
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

# The record shipper is imported rather than copied, so the two programs cannot
# drift on the store's rules or its location. The convention -- importlib for a
# module whose filename has hyphens -- is scripts/seat-shared-file-ship.py's.
_shipper_spec = importlib.util.spec_from_file_location(
    "cold_read_record_ship", REPO_ROOT / "scripts" / "cold-read-record-ship.py")
shipper = importlib.util.module_from_spec(_shipper_spec)
_shipper_spec.loader.exec_module(shipper)

SANITY_CHECK_KIND_DIRECTORY = "sanity-check-records"
RECORDS_DIR = REPO_ROOT / SANITY_CHECK_KIND_DIRECTORY


def destination_for_this_machine() -> tuple:
    """(host, path) for this kind: the record shipper's destination with the
    kind directory swapped, so the store's location is defined in exactly one
    place. The host is that function's -- None on ned-box itself, where the
    store is a local directory, and the store's host from anywhere else."""
    host, records_path = shipper.destination_for_this_machine()
    return host, records_path.parent / SANITY_CHECK_KIND_DIRECTORY


def main() -> int:
    return shipper.ship_from_command_line(
        __doc__, RECORDS_DIR, destination_for_this_machine())


if __name__ == "__main__":
    sys.exit(main())
