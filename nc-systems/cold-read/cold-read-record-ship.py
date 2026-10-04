#!/usr/bin/env python3
"""Ship one cold-read-record to the log-store on ned-box.

Usage:
  nc-systems/cold-read/cold-read-record-ship.py <record directory>
  nc-systems/cold-read/cold-read-record-ship.py --all

WHAT THE LOG-STORE IS (user-ruled 2026-09-07, walk
docs/walk/cold-read-records-branch-and-agent-instructions-queue.md): the
repository is the system and a reviewer report is a log, so cold-read-records
never enter git. They go to the log-store, `/home/nedlern/nedschorus-logs/` on
ned-box, one subdirectory per kind of byproduct; cold-read-records are the kind
`cold-read-records/`, keeping their directory names. A cold-read-record
there is cited with its host in scp form, so an agent on either machine
knows the command:
`nedlern@ned-box:/home/nedlern/nedschorus-logs/cold-read-records/2026-09-05-SKILL/dispositions.md` (a record from before triage.md took that file's name).
The cold-read-record in the checkout stays what it was: a
gitignored directory under cold-read-records/, written by the cold-read-grid
and by the agent.

WHAT ONE RUN DOES. The directory is copied whole to the store under its own
name by rsync -- over ssh from the Mac, as a local copy on ned-box, the store
itself being the only difference -- under four rules, the first three ruled
with the design:

  1. ADD-ONLY, EVERY FILE BUT triage.md. Files are added and never deleted or
     replaced, so a report, written once, is what the store keeps for good.
     rsync writes each file whole or not at all (its default
     temporary-file-and-rename; --inplace is never passed), so a copy
     interrupted midway is finished by the next run.
  2. REFUSE ON DIFFERENCE. An add-only file already in the store whose content
     differs from the local one is refused before anything is copied: the one
     line names every such file and prints the provenance comment each report
     opens with, from both copies, and the person renames the local
     directory with a -2 suffix and ships again. Two machines reviewing one document on one day
     produce exactly this, and rsync alone would overwrite the first silently.
  3. FAIL LOUDLY. When ned-box cannot be reached the run prints a line
     opening FAILED and exits non-zero; the cold-read-record stays on disk,
     unshipped, for a later run. ssh runs in batch mode with a connect timeout,
     so an automated caller never waits on a prompt.
  4. triage.md IS REPLACED, AND EACH DISPLACED COPY'S sha256 IS ANNOUNCED
     (user-ruled 2026-09-20, item 4 of the walk
     md-skills-seat-open-decisions-2026-09-20). triage.md is the one file in a
     cold-read-record written twice on purpose: the agent triages the
     reviewers' findings into it, and it is written again with the user's
     rulings once the approval-walk closes. Rules 1 and 2 refused that second
     write. What made the defect visible: the post-walk triage of
     `nedlern@ned-box:/home/nedlern/nedschorus-logs/cold-read-records/2026-09-14-nedschorus-file-naming-and-location-standards-3/`
     reached the store on 2026-09-20 ONLY because the file had also been
     renamed dispositions.md -> triage.md on 2026-09-18, so the shipper saw a
     name it did not hold and a new name is an add; under its old name that
     shipment would have been refused and five of the user's rulings would
     never have reached the store at all. So a stored triage.md whose bytes
     differ is overwritten, and the sha256 of the copy it displaced is
     announced on its own stderr line: a triage shipped three times leaves a
     trace of each displaced version rather than one silent overwrite.
     This is what scripts/walk-files-ship.py already does for a walk's minutes
     and dispositions -- same digest announcement, same stderr form -- ruled by
     the user on 2026-09-18 at item 5 of the walk
     skill-sentences-and-shipper-questions-2026-09-18 and landed in PR
     "walk-files-ship: a walk's five files reach the log-store's walk/ kind at
     the walk's close" (https://github.com/nedschorus/nedschorus/pull/501). The
     point of the 2026-09-20 ruling is that the two shippers stop differing.

     ONLY triage.md, AND ONLY THE RECORD'S OWN. The name is matched as the
     record directory's own top-level file, never by basename anywhere under
     it: `target/<repository path>/triage.md` is the frozen cold-read-target's
     bytes -- the reviewed document itself, which happens to be a triage file
     -- and it stays add-only like every other file. Nothing else gained a
     replace path, the reviewer reports above all: they record what was said,
     and a store that can rewrite them is no longer evidence.

     A DIFFERING ADD-ONLY FILE STILL REFUSES THE WHOLE RECORD, triage.md
     included, and copies nothing. A report that differs from the stored one
     says the local directory is a SECOND READ of the document -- the two
     machines on one day rule 2 was written for -- and that read's triage
     belongs beside that read's own reports, under the -2 name the refusal
     asks for. Landing it here would file one read's rulings with another
     read's reports. scripts/walk-files-ship.py ships a walk's remaining
     files through such a refusal because a reopened walk's second run exists
     to deliver the minutes and there is only ever one walk of that name; a
     record's -2 rename gives the second read a directory of its own, and
     nothing is lost by waiting for it.

ONE STEP, JUDGED BY WHAT THE STORE HOLDS. The new files are copied into a
staging directory beside the record's (`.ship-staging-<name>-<random>`),
whose name is this shipment's alone. Everything that reads or writes the
record's directory then runs as ONE step, one ssh call to ned-box running
place_staged_files_and_read_them_back in python3, or the same function in
this process when the store is local: it takes the store's inventory again,
judges it under rules 2 and 4, places the new files, replaces triage.md,
reads the store's digests back, and removes the staging directory.

  PLACING BY HARD LINK. The new files are placed into the record's directory
  by hard link, one at a time, in a fixed order. A hard link is never made
  over an existing file -- the link call fails when the name exists, in one
  step -- so a file already in the store is never replaced, and placing stops
  at the first name holding other bytes; triage.md is then left as the store
  holds it. The store's digests of the new files are read back: a file
  holding other bytes is REFUSED under rule 2, a file the store does not hold
  is FAILED, and `shipped:` is printed only when every new file holds this
  shipment's bytes.

  NO LOCK. The shipper takes no lock. Two shipments of one record name at one
  moment do not occur in real use: each record is shipped by the seat that
  made it, and repeat shipments of one record arrive one after another. If
  two ever do overlap and disagree on a file, the read-back finds that the
  store does not hold this shipment's bytes for it, and the shipper prints
  REFUSED or FAILED instead of `shipped:`. A file only one of the two has
  lands either way, so the record can then hold files of both, which the
  shipment that failed has said. Preventing the overlap would take a lock
  whose abandoned copies need reclaiming, which costs more than the failure
  it prevents.

A staging directory outlives its shipment only when the copy into it fails
and ned-box cannot be reached to remove it, or the shipment is killed before
the step; nothing reads it.

NO LOCK IN THE REPLACE STEP EITHER. replace_with_staged_files, the path a
walk's minutes, dispositions and appended walk text and a seat's files take,
takes no lock, for the reason NO LOCK gives above. Before any rename it looks
for another staging directory of the same name; if one is there, another
shipment is running or left it behind, so the step replaces nothing and the
shipper prints FAILED naming it.

The store's directories are created on first use, and a README.md at the
store's root is rewritten from STORE_README in this file whenever it differs:
it says what the store is, how to cite a file in it, and which program or
skill owns each kind.

WHO CALLS IT. nc-systems/cold-read/cold-read-grid.py at the end of every run, whatever the
outcome; the agent after writing triage.md (the cold-read skill's step
7); nc-systems/cold-read/cold-read-fast-read.py when it writes into cold-read-records/.
A shipping failure never fails the cold read: the caller prints this
program's one line and goes on. `--all` ships every directory under
cold-read-records/ in this checkout, continuing past a refused or failed one
and listing them at the end; being add-only it is safe over directories
already in the store, which is how a seat catches up after the box was down,
and how the cold-read-records that predate the store were shipped once.

OUTPUT. Exactly one line on stdout per cold-read-record -- `shipped:`,
`REFUSED:` or `FAILED:`, or under --all `skipped:` for an empty directory,
which is not a cold-read-record -- and, under --all, one summary line after
them. Everything else is on stderr, the REPLACED line rule 4 announces
included: that line is a trace for whoever reads the store, never the summary a
caller prints. Exit 0 when every directory shipped, 2 when
any was refused and none failed, 1 when any failed, 64 for a bad invocation.

THE CITATION NAMES THE HOST ON BOTH MACHINES. On ned-box the copy is local
and the ssh/rsync host is None, but the printed line is pasted into
documents read from either machine, so it carries the store's host from
the constant whatever machine ran the copy (nedschorus#299; the seats run
on ned-box, so that is where most citations are written). Only a test's
override, a bare local path, prints without one.

THE DESTINATION IS ONE CONSTANT, LOG_STORE_RECORDS_DESTINATION, so a move to
cloud storage, which the user named as the fallback if ned-box proves
unreliable, is one edit here plus one rsync of the store's contents. The
environment variable COLD_READ_RECORD_SHIP_DESTINATION overrides it for the
tests, which point it at a scratch directory (local mode, real rsync) or at
the real string with stub rsync and ssh binaries on PATH (remote mode, to see
the invocation). A destination with no `host:` prefix is local.
"""

import argparse
import hashlib
import inspect
import json
import shlex
import os
import importlib.util
import pathlib
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import textwrap
import typing

# This file sits in nc-systems/cold-read/, two directories below the root.
REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
# What a cold-read-record is called and where it lives, defined once in a
# module so no program keeps its own copy. importlib, because the filename
# has hyphens.
_record_names_spec = importlib.util.spec_from_file_location(
    "cold_read_record_names",
    pathlib.Path(__file__).with_name("cold-read-record-names.py"))
record_names = importlib.util.module_from_spec(_record_names_spec)
_record_names_spec.loader.exec_module(record_names)
RECORDS_DIR = record_names.RECORDS_DIR
PROGRAM = "cold-read-record-ship"

# The one constant. Host and path in scp form; the path's parent is the
# store's root, where the README lives.
LOG_STORE_RECORDS_DESTINATION = "nedlern@ned-box:/home/nedlern/nedschorus-logs/cold-read-records"
LOG_STORE_HOSTNAME = "ned-box"
DESTINATION_ENVIRONMENT_VARIABLE = "COLD_READ_RECORD_SHIP_DESTINATION"

# The one file in a cold-read-record a later shipment REPLACES in the store,
# rule 4 above. Held here because this program is the one that compares a
# record's files by name; it is matched as the record directory's own
# top-level file, so the frozen cold-read-target's own copy of a file by this
# name is add-only like the rest of that directory. nc-systems/cold-read/cold-read-grid.py
# names the same file in the prose it hands the agent, which is prose naming a
# file rather than a second definition of a path a program builds -- the
# distinction nc-systems/cold-read/tests/cold-read-record-names-test.py draws.
TRIAGE_FILE_REPLACED_IN_THE_STORE = "triage.md"

SSH_COMMAND = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10"]
# Seconds rsync waits on a silent connection before giving up.
RSYNC_IO_TIMEOUT_SECONDS = "120"
# ssh's exit code when it could not connect, which rsync passes through.
RSYNC_EXIT_CONNECTION_FAILED = 255
PROVENANCE_COMMENT_PREFIX = "<!-- provenance:"

# The new files of one shipment are copied into a directory of this name
# beside the record's own, then hard-linked into place; see ONE STEP, JUDGED
# BY WHAT THE STORE HOLDS above. A leading dot keeps it out of an ordinary
# listing of the store; the record's name and a random part keep two
# shipments apart.
STAGING_DIRECTORY_PREFIX = ".ship-staging-"
# Marks the one ssh call that runs the placing step, so a test's stub `ssh`
# can tell it from the inventory.
PLACE_STAGED_FILES_MARKER = "# cold-read-record-ship: place staged files"
# Marks the one ssh call that links a walk's add-only files into the store,
# for the same reason; see link_staged_files_never_over_existing.
LINK_STAGED_FILES_MARKER = "# cold-read-record-ship: link staged files"
# Marks the one ssh call that replaces store files with staged ones, for the
# same reason; see replace_with_staged_files.
REPLACE_WITH_STAGED_FILES_MARKER = "# cold-read-record-ship: replace with staged files"

EXIT_SHIPPED = 0
EXIT_FAILED = 1
EXIT_REFUSED = 2
EXIT_BAD_INVOCATION = 64

# The note at the door of the log-store, written into it by this program.
#
# AGENT-FACING TEXT, so it says what the store is, how to cite a file in it,
# which program or skill owns each kind, and what to edit to change this file,
# with a reason wherever the reason helps the reader act. It cites no ruling
# and no date: a ruling or a date says only who decided and when, which does
# not help a reader use the store.
#
# It lists the kinds, each naming ONLY its owner, never a naming rule: a
# restated naming rule goes stale whenever the owner changes it, and a reader
# following the stale text looks for a file by a name it no longer has. An
# owner changes far less often than a naming rule, and the naming rule stays
# with the owner.
STORE_README = """\
# nedschorus-logs

The log-store: the byproducts of the nedschorus project's work that are not
the system. Good data, never part of the repository. One subdirectory per
kind.

Cite a file here with its host, in the form scp takes:
`nedlern@ned-box:/home/nedlern/nedschorus-logs/<kind>/<path>`.

What each kind holds and how its files are named is decided by its owner,
in the nedschorus repository, which this machine also clones:

- `cold-read-records/` -- cold-read-records, named by
  `nc-systems/cold-read/cold-read-record-names.py`
- `sanity-check-records/` -- the /sanity-check skill's records, shipped by
  `scripts/sanity-check-record-ship.py`
- `walk/` -- approval-walk files, named by the walk-me-through skill, shipped
  by `scripts/walk-files-ship.py`
- `transcripts/` -- session transcripts, mirrored by
  `scripts/transcript-mirror-to-log-store.py`
- `seats/` -- a seat's shared files, shipped by
  `scripts/seat-shared-file-ship.py`
- `analysis/` -- analyses, placed by hand
- `daily-full-test-runs/` -- each machine's daily run of every test suite on
  main, written by `scripts/daily-full-test-run-of-main.py`
- `pull-request-head-test-runs/` -- each machine's test log of a pull request's
  head, one per commit, written by `scripts/pull-request-head-test-run.py`
- `daily-memory-review-marks/` -- the daily memory review's started and done
  marks, written by `nc-systems/handoff/daily-memory-review-mark.py`

To change this file, edit STORE_README in
nc-systems/cold-read/cold-read-record-ship.py. The next shipment rewrites this file
whenever it differs from that text, so an edit made here is lost.
"""


def split_destination(destination: str):
    """(host, path) from an scp-form destination; host is None for a local path.

    A colon before the first slash is the host separator; a bare path never
    has one there.
    """
    head = destination.split("/", 1)[0]
    if ":" in head:
        host, _, rest = destination.partition(":")
        return host, pathlib.PurePosixPath(rest)
    return None, pathlib.PurePosixPath(destination)


def destination_for_this_machine() -> tuple:
    """Where this run ships to: the override, else the constant, which on
    ned-box itself is the same path with no host (a local copy)."""
    override = os.environ.get(DESTINATION_ENVIRONMENT_VARIABLE)
    if override:
        return split_destination(override)
    host, path = split_destination(LOG_STORE_RECORDS_DESTINATION)
    if socket.gethostname().split(".")[0] == LOG_STORE_HOSTNAME:
        return None, path
    return host, path


def citation_host_for_this_machine():
    """The host the printed citation names: the constant's, on every machine,
    because the line is read from either. Only the test override's own host
    replaces it, and a bare local override has none.

    Kept apart from the COPY host destination_for_this_machine returns, which
    is None on ned-box on purpose -- the copy there is a local directory copy
    and must not run ssh (the seat shipper's namedtuple keeps the same two
    hosts apart, for the same reason)."""
    override = os.environ.get(DESTINATION_ENVIRONMENT_VARIABLE)
    host, _ = split_destination(override or LOG_STORE_RECORDS_DESTINATION)
    return host


def provenance_comment_of(first_line: str) -> str:
    line = first_line.strip()
    return line if line.startswith(PROVENANCE_COMMENT_PREFIX) else "(no provenance comment)"


def local_first_line(path: pathlib.Path) -> str:
    try:
        with path.open(encoding="utf-8", errors="replace") as handle:
            return handle.readline()
    except OSError:
        return ""


def remote_first_line(host: str, path: pathlib.PurePosixPath) -> str:
    completed = subprocess.run(
        SSH_COMMAND + [host, f"head -n 1 -- '{path}'"],
        capture_output=True, text=True, check=False)
    return completed.stdout if completed.returncode == 0 else ""


def rsync_command(host, source: pathlib.Path, target: pathlib.PurePosixPath, *extra) -> list:
    """rsync of the directory's contents into the store's directory of the
    same name. -a and never --delete or --inplace: see the rules above."""
    destination = f"{host}:{target}/" if host else f"{target}/"
    command = ["rsync", "-a", "--timeout", RSYNC_IO_TIMEOUT_SECONDS, *extra]
    if host:
        command += ["-e", " ".join(SSH_COMMAND)]
    return command + [f"{source}/", destination]


def refresh_store_readme(root) -> None:
    """STORE_README into <root>/README.md, on this machine, when it differs.

    REWRITTEN WHENEVER IT DIFFERS, not only when it is missing: a README
    written only once falls behind every later change to the text.
    Refreshing here means the next shipment carries a change, and nobody
    edits a file on ned-box by hand to make one.

    The README is the shippers' own file, so the add-only rule that protects
    the records does not cover it.

    It lands by rename, from a temporary written beside it, for the reason
    given in `make_directory_and_refresh_readme_script`: a reader sees the
    old file whole or the new one whole, never a half-written index.

    THE TEMPORARY'S NAME COMES FROM `mkstemp`, never a fixed README.md.new.
    This is the path the seats take, not the remote script's: they run on
    ned-box, where the copy is local, and every shipment of every kind
    refreshes this README with nothing locking it. On one name two
    overlapping shipments collide -- the winner's rename removes the shared
    path and the loser's `os.replace` raises FileNotFoundError, an
    uncaught traceback on a store that is correct.

    `mkstemp` creates the file 0600 and the store's README has always been
    world-readable, so the mode is widened before the rename rather than
    leaving the store's index owner-only.
    """
    readme = pathlib.Path(root) / "README.md"
    try:
        live = readme.read_text(encoding="utf-8")
    except OSError:
        live = None
    if live == STORE_README:
        return
    handle, name = tempfile.mkstemp(prefix="README.md.", dir=str(readme.parent))
    os.close(handle)
    temporary = pathlib.Path(name)
    try:
        temporary.write_text(STORE_README, encoding="utf-8")
        temporary.chmod(0o644)
        os.replace(temporary, readme)
    except OSError:
        temporary.unlink(missing_ok=True)
        raise


def make_directory_and_refresh_readme_script(directory, root) -> str:
    """The remote script for `mkdir -p <directory>` and the README refresh.

    ONE DEFINITION, here, called by every shipper that prepares the store:
    this program's `ensure_store` and scripts/seat-shared-file-ship.py's
    `ensure_seat_directory`. A second copy is how two programs come to
    disagree about when the README is rewritten -- and they would rewrite it
    against each other on every shipment.

    The new text arrives on stdin rather than quoted into the script, so a
    README holding quotes needs no escaping. `cmp` then decides: the text is
    landed only when it differs, so an unchanged store is not rewritten, and
    its modification time still says when the text last changed.

    IT LANDS BY RENAME, from a temporary written BESIDE the README -- same
    directory, so the same filesystem, so `mv` is one rename and a reader
    sees the old file whole or the new one whole. Writing through the live
    file instead would leave the store's own index empty or half-written when
    the shipment is interrupted, and nothing would repair it until a later
    shipment happened to run to completion; the ssh link to ned-box does
    drop. `mkdir -p` of the kind's directory runs first and creates
    the root as its parent, so `mktemp` has somewhere to put the temporary on
    a store that is new, and the closing `rm -f` removes it when `cmp` found
    no difference.

    WHAT ARRIVED IS COUNTED BEFORE ANYTHING LANDS. A dropped link is not an
    error the shell can see: it is a clean EOF on a short stream, so `cat`
    returns 0 on the prefix that arrived, `cmp` finds a real difference, and
    `mv` publishes the truncation over a good README with the script exiting
    0. So the text's byte count is written into this script
    and `wc -c` on the received temporary must equal it; a stream that ends
    short is refused and nothing is landed. The count is what STORE_README
    encodes to in UTF-8, which is the encoding `ensure_store` and the seat
    shipper pin on the ssh call that sends it.

    THE REFUSAL REMOVES THE TEMPORARY BEFORE IT REPORTS. The drop that causes
    a short stream has closed stderr as well, so writing the reason first can
    take SIGPIPE and end the shell with the temporary still there; the
    cleanup goes ahead of the diagnostic.

    THE TEMPORARY'S NAME COMES FROM `mktemp`, never a fixed README.md.new.
    Every shipment from every seat refreshes this README, nothing locks, and
    two overlapping shipments on one name collide two ways: the winner's
    closing `rm -f` falls between
    the loser's `cat` and its `cmp`, so the loser exits 1 on a store that is
    correct; and when the two send different text, which two checkouts at
    different commits do, the winner's `mv` renames the inode out from under a
    writer still holding it open and the loser's remaining bytes land inside
    the live README. A unique name is reachable by neither. `mktemp` creates
    the temporary 0600, so the mode is widened before the rename, the store's
    README having always been world-readable.

    A temporary orphaned by a drop is no longer overwritten by the next run,
    each run's name being its own: a drop that arrives as a short stream is
    refused and its temporary removed here, and one left by a shell killed
    outright stays beside the README, inert, until it is removed by hand. A
    sweep of README.md.* cannot be added here without racing exactly the
    overlap the unique name fixes.

    POSIX shell only -- ned-box's /bin/sh is dash, with uutils coreutils
    for `mktemp`, `wc` and `chmod` and GNU diffutils for `cmp`; the template
    form of `mktemp` and `[ "$(wc -c < f)" -eq n ]` work there. `chmod` takes
    `--` BEFORE the mode: a trailing one is a file name to the Mac's BSD
    chmod, which then exits 1.
    """
    return (f"mkdir -p -- '{directory}' || exit 1\n"
            f"readme_new=$(mktemp '{root}/README.md.XXXXXX') || exit 1\n"
            'cat > "$readme_new" || { rm -f -- "$readme_new"; exit 1; }\n'
            f'[ "$(wc -c < "$readme_new")" -eq {len(STORE_README.encode("utf-8"))} ] '
            '|| { rm -f -- "$readme_new"; '
            "printf '%s\\n' 'the log-store README arrived incomplete; "
            "nothing was landed. Ship again.' >&2; exit 1; }\n"
            'chmod -- 644 "$readme_new" || { rm -f -- "$readme_new"; exit 1; }\n'
            f'cmp -s -- "$readme_new" \'{root}/README.md\' '
            f'|| mv -- "$readme_new" \'{root}/README.md\' '
            '|| { rm -f -- "$readme_new"; exit 1; }\n'
            'rm -f -- "$readme_new"\n')


def ensure_store(host, records_path: pathlib.PurePosixPath) -> subprocess.CompletedProcess:
    """The records directory exists and the store's root holds STORE_README.
    One ssh round trip remotely; plain filesystem calls locally.

    The stdin encoding is pinned to UTF-8 rather than left to the locale,
    because the script counts the bytes it receives against a count taken in
    UTF-8; see `make_directory_and_refresh_readme_script`."""
    root = records_path.parent
    if host is None:
        pathlib.Path(records_path).mkdir(parents=True, exist_ok=True)
        refresh_store_readme(root)
        return subprocess.CompletedProcess([], 0, "", "")
    script = make_directory_and_refresh_readme_script(records_path, root)
    return subprocess.run(SSH_COMMAND + [host, script], input=STORE_README,
                          capture_output=True, text=True, encoding="utf-8",
                          check=False)


def local_inventory(record_dir: pathlib.Path) -> dict:
    """{relative path: sha256} of every file under the cold-read-record."""
    inventory = {}
    for path in sorted(p for p in record_dir.rglob("*") if p.is_file()):
        inventory[path.relative_to(record_dir).as_posix()] = hashlib.sha256(
            path.read_bytes()).hexdigest()
    return inventory


def store_inventory(host, store_dir: pathlib.PurePosixPath):
    """{relative path: sha256} of the store's copy of this cold-read-record,
    and the process that produced it. An absent directory is an empty
    inventory with exit 0; an unreachable host is ssh's exit 255 and an
    inventory of None.

    sha256 on both sides -- Python's hashlib here, sha256sum on ned-box -- is
    the digest the cold-read-grid already records for the cold-read-target, so
    a reader can compare a cold-read-record's frozen cold-read-target with the
    cold-read-grid's fingerprint by eye.
    Not rsync's --itemize-changes: the Mac ships openrsync and ned-box ships
    rsync, and their itemize formats differ.
    """
    if host is None:
        directory = pathlib.Path(store_dir)
        inventory = local_inventory(directory) if directory.is_dir() else {}
        return subprocess.CompletedProcess([], 0, "", ""), inventory
    script = (f"if [ -d '{store_dir}' ]; then cd '{store_dir}' && "
              f"find . -type f -exec sha256sum {{}} +; fi")
    completed = subprocess.run(SSH_COMMAND + [host, script],
                               capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        return completed, None
    inventory = {}
    for line in completed.stdout.splitlines():
        digest, _, name = line.partition("  ")
        if digest and name:
            inventory[name[2:] if name.startswith("./") else name] = digest
    return completed, inventory


def place_staged_files(host, staging_dir: pathlib.PurePosixPath,
                       store_dir: pathlib.PurePosixPath, local_digests: dict):
    """Run place_staged_files_and_read_them_back for this shipment and return
    the process and the step's outcome. One ssh round trip remotely, the
    function sent as a python3 program with its request as JSON on stdin, so
    no path is ever parsed by a shell; the same function in this process when
    the store is local. An unreachable host, or a step that did not finish,
    is an outcome of None. See ONE STEP, JUDGED BY WHAT THE STORE HOLDS in the
    docstring."""
    request = {"store_dir": str(store_dir), "staging_dir": str(staging_dir),
               "local_digests": local_digests,
               "replaceable": TRIAGE_FILE_REPLACED_IN_THE_STORE}
    if host is None:
        try:
            outcome = place_staged_files_and_read_them_back(request)
        except OSError as failed:
            # stdout carries the OS's own reason, which the FAILED line prints.
            return subprocess.CompletedProcess([], 1, failed.strerror or str(failed),
                                               f"{failed}\n"), None
        return subprocess.CompletedProcess([], 0, "", ""), outcome
    completed = subprocess.run(
        SSH_COMMAND + [host, f"python3 -c {shlex.quote(place_staged_files_program())}"],
        input=json.dumps(request), capture_output=True, text=True,
        encoding="utf-8", check=False)
    if completed.returncode != 0:
        return completed, None
    try:
        outcome = json.loads(completed.stdout.strip().splitlines()[-1])
    except (IndexError, ValueError):
        return completed, None
    return completed, outcome if isinstance(outcome, dict) else None


def place_staged_files_program() -> str:
    """The python3 program the remote step runs on ned-box: the function
    below, by its own source, and a line that reads its request from stdin
    and prints its outcome as one line of JSON."""
    return (f"{PLACE_STAGED_FILES_MARKER}\n"
            f"import json, sys\n"
            f"{textwrap.dedent(inspect.getsource(place_staged_files_and_read_them_back))}"
            f"print(json.dumps(place_staged_files_and_read_them_back("
            f"json.load(sys.stdin))))\n")


def place_staged_files_and_read_them_back(request: dict) -> dict:
    """The one step that reads and writes the record's directory in the store:
    inventory, rules 2 and 4, placing by hard link, the triage.md replacement
    and the read-back. It removes the staging directory however it ends. It
    runs on ned-box as its own python3 program, sent by its source, so it
    imports what it uses and calls nothing else in this file.

    `request` holds store_dir, staging_dir, local_digests ({relative path:
    sha256} of the whole record) and replaceable (triage.md). The outcome:
      differing -- add-only files the store holds with other bytes; when any
        is named, nothing was placed (rule 2).
      added -- the files the store did not hold, which this step tried to
        place.
      displaced -- the store's digest of the triage.md this step replaced,
        or None (rule 4). triage.md is replaced only after every new file
        was placed.
      stored -- the store's digest of each added file and of a replaced
        triage.md, read after placing; a name absent here is not in the store.
    """
    import hashlib
    import os
    import pathlib
    import shutil

    store = pathlib.Path(request["store_dir"])
    staging = pathlib.Path(request["staging_dir"])
    local = request["local_digests"]
    replaceable = request["replaceable"]

    def digest_of(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    try:
        store.mkdir(parents=True, exist_ok=True)
        in_store = {path.relative_to(store).as_posix(): digest_of(path)
                    for path in sorted(store.rglob("*")) if path.is_file()}
        differing = sorted(relative for relative, digest in local.items()
                           if relative != replaceable and relative in in_store
                           and in_store[relative] != digest)
        if differing:
            return {"differing": differing, "added": [], "displaced": None,
                    "stored": {}}
        added = sorted(relative for relative in local if relative not in in_store)
        displaced = None
        for relative in added:
            target = store / relative
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                os.link(staging / relative, target)
            except FileExistsError:
                # Only another shipment of this name, running at the same
                # moment, can have placed it since the inventory above.
                if relative != replaceable and digest_of(target) != local[relative]:
                    break
            except OSError:
                break
        else:
            # Reached only when placing did not stop, so a shipment that
            # ends REFUSED or FAILED leaves the store's triage.md as it was.
            triage = store / replaceable
            if replaceable in local and triage.is_file():
                held = digest_of(triage)
                if held != local[replaceable]:
                    # A rename within one filesystem: the name holds the old
                    # file or the new one, never part of either.
                    os.replace(staging / replaceable, triage)
                    displaced = held
        read_back = added + ([replaceable] if displaced is not None
                             and replaceable not in added else [])
        stored = {relative: digest_of(store / relative) for relative in read_back
                  if (store / relative).is_file()}
        return {"differing": [], "added": added, "displaced": displaced,
                "stored": stored}
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def link_staged_files_never_over_existing(host, staging_dir: pathlib.PurePosixPath,
                                          store_dir: pathlib.PurePosixPath,
                                          relatives: list):
    """Hard-link each staged file into the store directory, in the order
    given, then remove the staging directory and return the process and the
    store's {relative path: sha256} of `relatives` -- the files the store now
    holds under those names, whoever put them there. An unreachable host is
    an inventory of None, as in store_inventory.

    A link is never made over an existing file: a name already taken is left
    as it is, and placing goes on past it, so the caller judges each file by
    the digest read back. This is scripts/walk-files-ship.py's add-only
    placing, which refuses a walk's files one by one while the rest still
    ship; a cold-read-record is placed by place_staged_files instead.

    One ssh round trip remotely, running
    link_staged_files_never_over_existing_script; plain filesystem calls and
    hashlib locally, as store_inventory does."""
    if host is None:
        staging, store = pathlib.Path(staging_dir), pathlib.Path(store_dir)
        try:
            for relative in relatives:
                target = store / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                try:
                    os.link(staging / relative, target)
                except FileExistsError:
                    continue
                except OSError:
                    break
        finally:
            shutil.rmtree(staging, ignore_errors=True)
        after = {relative: hashlib.sha256((store / relative).read_bytes()).hexdigest()
                 for relative in relatives if (store / relative).is_file()}
        return subprocess.CompletedProcess([], 0, "", ""), after
    script = link_staged_files_never_over_existing_script(staging_dir, store_dir, relatives)
    completed = subprocess.run(SSH_COMMAND + [host, script],
                               capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        return completed, None
    after = {}
    for line in completed.stdout.splitlines():
        digest, _, relative = line.partition("  ")
        if digest and relative:
            after[relative] = digest
    return completed, after


def link_staged_files_never_over_existing_script(staging_dir: pathlib.PurePosixPath,
                                                 store_dir: pathlib.PurePosixPath,
                                                 relatives: list) -> str:
    """The POSIX sh script link_staged_files_never_over_existing runs on
    ned-box: link each file, leaving a name already taken as it is, remove
    the staging directory, print `sha256sum`'s line for each of `relatives`
    the store holds. `ln` without -f fails when the name exists, and makes
    the link in the same step when it does not."""
    quoted_relatives = " ".join(shlex.quote(relative) for relative in relatives)
    staging = shlex.quote(str(staging_dir))
    store = shlex.quote(str(store_dir))
    return (
        f"{LINK_STAGED_FILES_MARKER}\n"
        f"for relative in {quoted_relatives}; do\n"
        f"  mkdir -p -- \"$(dirname -- {store}/\"$relative\")\" || break\n"
        f"  ln -- {staging}/\"$relative\" {store}/\"$relative\" 2>/dev/null || :\n"
        f"done\n"
        f"rm -rf -- {staging}\n"
        f"cd -- {store} || exit 0\n"
        f"for relative in {quoted_relatives}; do\n"
        f"  if [ -f \"$relative\" ]; then sha256sum -- \"$relative\"; fi\n"
        f"done\n")


class StagedReplacement(typing.NamedTuple):
    """What replace_with_staged_files did with one file. `displaced_sha256` is
    the store's digest of the file the rename replaced, read in the same step
    as the rename, or None when there was none; `stored_sha256` is the
    store's digest of the name after every rename of the call, whoever's
    bytes they are, or None when the name holds no file."""

    replaced: bool
    displaced_sha256: typing.Optional[str]
    stored_sha256: typing.Optional[str]


class OtherShipmentStaging(typing.NamedTuple):
    """replace_with_staged_files found another shipment's staging directory
    for the same name and replaced nothing. `paths` names each one."""

    paths: tuple


# The random part of a staging directory's name: secrets.token_hex(6).
STAGING_DIRECTORY_TOKEN_LENGTH = 12


def other_staging_directories_local(staging_dir: pathlib.Path) -> tuple:
    """Every other staging directory beside this one for the same name."""
    stem = staging_dir.name[:-STAGING_DIRECTORY_TOKEN_LENGTH]
    others = []
    if staging_dir.parent.is_dir():
        for entry in sorted(staging_dir.parent.iterdir()):
            token = entry.name[len(stem):]
            if (entry.name != staging_dir.name and entry.name.startswith(stem)
                    and len(token) == STAGING_DIRECTORY_TOKEN_LENGTH
                    and all(c in "0123456789abcdef" for c in token)
                    and entry.is_dir()):
                others.append(str(entry))
    return tuple(others)


def other_shipment_failure_lines(label: str, staging: OtherShipmentStaging) -> tuple:
    """The FAILED line for stdout and the instruction line for stderr, shared
    by every shipper whose replace step returned OtherShipmentStaging."""
    paths = ", ".join(staging.paths)
    return (f"FAILED: {label} — another shipment of it is running, or one left "
            f"its staging directory behind: {paths}; nothing was replaced.",
            f"When no other shipment of {label} is running, delete {paths} and "
            f"run this again.")


def replace_with_staged_files(host, staging_dir: pathlib.PurePosixPath,
                              store_dir: pathlib.PurePosixPath,
                              replacements: list):
    """Rename staged files over the store's, for the files a shipper REPLACES
    by design: the walk's minutes and dispositions, a walk text the walk only
    added to (scripts/walk-files-ship.py) and a seat's own files
    (scripts/seat-shared-file-ship.py). Returns the process and
    {store relative path: StagedReplacement}, or None for an unreachable
    host, as store_inventory does. The staging directory is left for the
    caller to remove, with remove_staging_directory or by placing the rest.

    `replacements` is a list of (staged relative path, store relative path,
    required sha256 or None). A required digest makes the rename conditional:
    it runs only while the store still holds those bytes, which is how the
    walk text's APPENDED TO rule is held to the stored copy it was tested
    against. None replaces whatever is there.

    WHY A RENAME OF A STAGED COPY, AND NOT rsync STRAIGHT ONTO THE NAME. A
    shipper that read the store's digest, decided, and then copied with
    rsync, which takes seconds over ssh, would replace a second shipment of
    the same name in those seconds without a word, the replacement
    announcement naming the bytes the first look saw, or nothing when it saw
    no file. Here the
    digest of what is about to be displaced is read immediately before the
    rename, in one shell, so the announcement names what was actually
    displaced, and the store is read again afterwards, so a caller judges its
    outcome on what the store holds.

    NO LOCK; A CHECK INSTEAD. Two shipments of one name at one moment do not
    occur in real use: each walk's or seat's files are shipped by the seat
    that owns them. A read-back cannot see a rename that runs after it, so an
    overlap is caught before it can do harm: each shipment's staging directory
    exists from its copy until its placing ends, and this step renames
    nothing when another staging directory for the same name is there,
    returning OtherShipmentStaging. Two shipments that overlap therefore both
    stop, or the later one replaces what the earlier one placed and names its
    digest. A leftover staging directory from a crashed shipment stops every
    shipment of that name until it is deleted; nothing here reclaims it.

    One ssh round trip remotely, running replace_with_staged_files_script;
    os.replace and hashlib locally."""
    if host is None:
        staging, store = pathlib.Path(staging_dir), pathlib.Path(store_dir)
        others = other_staging_directories_local(staging)
        if others:
            return subprocess.CompletedProcess([], 0, "", ""), OtherShipmentStaging(others)
        outcomes = {}
        store.mkdir(parents=True, exist_ok=True)
        for staged_relative, store_relative, required in replacements:
            target = store / store_relative
            target.parent.mkdir(parents=True, exist_ok=True)
            displaced = (hashlib.sha256(target.read_bytes()).hexdigest()
                         if target.is_file() else None)
            replaced = required is None or displaced == required
            if replaced:
                os.replace(staging / staged_relative, target)
            outcomes[store_relative] = (replaced, displaced)
        stored = {
            store_relative: hashlib.sha256(
                (store / store_relative).read_bytes()).hexdigest()
            for store_relative in outcomes
            if (store / store_relative).is_file()}
        return subprocess.CompletedProcess([], 0, "", ""), {
            store_relative: StagedReplacement(replaced, displaced,
                                              stored.get(store_relative))
            for store_relative, (replaced, displaced) in outcomes.items()}
    script = replace_with_staged_files_script(staging_dir, store_dir, replacements)
    completed = subprocess.run(SSH_COMMAND + [host, script],
                               capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        return completed, None
    acted, stored, others = {}, {}, []
    for line in completed.stdout.splitlines():
        word, _, rest = line.partition(" ")
        digest, _, relative = rest.partition(" ")
        if not relative:
            continue
        if word == "other":
            others.append(relative)
        elif word in ("replaced", "kept"):
            acted[relative] = (word == "replaced", None if digest == "-" else digest)
        elif word == "stored":
            stored[relative] = digest
    if others:
        return completed, OtherShipmentStaging(tuple(others))
    return completed, {
        relative: StagedReplacement(replaced, displaced, stored.get(relative))
        for relative, (replaced, displaced) in acted.items()}


def replace_with_staged_files_script(staging_dir: pathlib.PurePosixPath,
                                     store_dir: pathlib.PurePosixPath,
                                     replacements: list) -> str:
    """The POSIX sh script replace_with_staged_files runs on ned-box. For each
    file: read the store's digest of the name (`-` for none), rename the
    staged copy over it when no digest is required or the store's is the
    required one, and print `replaced <digest> <name>` or `kept <digest>
    <name>`. Then print `stored <digest> <name>` for each name the store
    holds. `mv -f` within one directory tree is a rename, so the name holds
    the old file or the new one, never part of either. A digest that cannot
    be read exits 1 before anything more is renamed. First it prints
    `other - <path>` for each other staging directory of the same name and,
    if there is one, renames nothing: see NO LOCK; A CHECK INSTEAD in
    replace_with_staged_files."""
    arguments = " ".join(
        f"{shlex.quote(staged)} {shlex.quote(target)} {required or '-'}"
        for staged, target, required in replacements)
    quoted_targets = " ".join(shlex.quote(target) for _, target, _ in replacements)
    staging = shlex.quote(str(staging_dir))
    store = shlex.quote(str(store_dir))
    return (
        f"{REPLACE_WITH_STAGED_FILES_MARKER}\n"
        f"self={staging}; others=0\n"
        f"stem=$(basename -- \"$self\"); stem=${{stem%{'?' * STAGING_DIRECTORY_TOKEN_LENGTH}}}\n"
        f"for other in \"$(dirname -- \"$self\")\"/\"$stem\"{'[0-9a-f]' * STAGING_DIRECTORY_TOKEN_LENGTH}; do\n"
        f"  if [ -d \"$other\" ] && [ \"$other\" != \"$self\" ]; then\n"
        f"    printf 'other - %s\\n' \"$other\"; others=1\n"
        f"  fi\n"
        f"done\n"
        f"[ $others = 0 ] || exit 0\n"
        f"mkdir -p -- {store} || exit 1\n"
        f"set -- {arguments}\n"
        f"while [ $# -gt 0 ]; do\n"
        f"  staged=$1; target=$2; required=$3; shift 3\n"
        f"  mkdir -p -- \"$(dirname -- {store}/\"$target\")\" || exit 1\n"
        f"  current=-\n"
        f"  if [ -f {store}/\"$target\" ]; then\n"
        f"    current=$(sha256sum < {store}/\"$target\" | cut -d' ' -f1)\n"
        f"    [ -n \"$current\" ] || exit 1\n"
        f"  fi\n"
        f"  if [ \"$required\" = - ] || [ \"$required\" = \"$current\" ]; then\n"
        f"    mv -f -- {staging}/\"$staged\" {store}/\"$target\" || exit 1\n"
        f"    printf 'replaced %s %s\\n' \"$current\" \"$target\"\n"
        f"  else\n"
        f"    printf 'kept %s %s\\n' \"$current\" \"$target\"\n"
        f"  fi\n"
        f"done\n"
        f"for target in {quoted_targets}; do\n"
        f"  if [ -f {store}/\"$target\" ]; then\n"
        f"    printf 'stored %s %s\\n' \"$(sha256sum < {store}/\"$target\" | cut -d' ' -f1)\" \"$target\"\n"
        f"  fi\n"
        f"done\n")


def remove_staging_directory(host, staging_dir: pathlib.PurePosixPath) -> None:
    """Remove a staging directory a failed copy may have left. Best effort: the
    copy that failed may have failed because ned-box is unreachable, and then
    this fails too and the directory stays, which nothing reads."""
    if host is None:
        shutil.rmtree(pathlib.Path(staging_dir), ignore_errors=True)
        return
    subprocess.run(SSH_COMMAND + [host, f"rm -rf -- {shlex.quote(str(staging_dir))}"],
                   capture_output=True, text=True, check=False)


def ship_one(host, records_path: pathlib.PurePosixPath, record_dir: pathlib.Path) -> int:
    """One directory, one stdout line, one exit code."""
    name = record_dir.name
    store_dir = records_path / name
    citation_host = citation_host_for_this_machine()
    citation = f"{citation_host}:{store_dir}" if citation_host else str(store_dir)

    if not record_dir.is_dir() or not any(record_dir.iterdir()):
        print(f"FAILED: {name} — not a record directory with files: {record_dir}")
        return EXIT_BAD_INVOCATION

    ensured = ensure_store(host, records_path)
    if ensured.returncode != 0:
        print(f"FAILED: {name} — could not reach the log-store to prepare it "
              f"({host or records_path}, exit {ensured.returncode}); the record "
              f"stays on disk, unshipped.")
        sys.stderr.write(ensured.stderr)
        return EXIT_FAILED

    # Taken to refuse, or to find nothing new, before anything is copied. Both
    # answers stand: an add-only file never changes once in the store. The
    # placing step takes the inventory again.
    listed, in_store = store_inventory(host, store_dir)
    if in_store is None:
        reason = ("ned-box unreachable" if listed.returncode == RSYNC_EXIT_CONNECTION_FAILED
                  else f"ssh exit {listed.returncode}")
        print(f"FAILED: {name} — {reason}; the record stays on disk, unshipped.")
        sys.stderr.write(listed.stderr)
        return EXIT_FAILED
    local = local_inventory(record_dir)
    differing = sorted(relative for relative, digest in local.items()
                       if relative in in_store and in_store[relative] != digest)
    new_files = sorted(relative for relative in local if relative not in in_store)
    # Rule 4: the record's own triage.md is replaced rather than refused, so it
    # leaves `differing` here and the refusal below is about the add-only files
    # alone.
    triage_differs = TRIAGE_FILE_REPLACED_IN_THE_STORE in differing
    if triage_differs:
        differing.remove(TRIAGE_FILE_REPLACED_IN_THE_STORE)
    def refuse(differing_files):
        # The loop only gathers; the one print comes after it, so a
        # cold-read-record with several differing files still gets
        # exactly one stdout line.
        described = []
        for relative in differing_files:
            local_line = provenance_comment_of(local_first_line(record_dir / relative))
            if host:
                store_line = provenance_comment_of(remote_first_line(host, store_dir / relative))
            else:
                store_line = provenance_comment_of(
                    local_first_line(pathlib.Path(store_dir) / relative))
            described.append(f"{relative} (store: {store_line}; local: {local_line})")
        print(f"REFUSED: {name} — already in the store with different content: "
              f"{'; '.join(described)}. Rename the local directory with a -2 suffix "
              f"and ship again.")
        return EXIT_REFUSED

    def nothing_new():
        print(f"shipped: {name} — nothing new, all files already there; "
              f"record at {citation}")
        return EXIT_SHIPPED

    if differing:
        return refuse(differing)
    if not new_files and not triage_differs:
        return nothing_new()

    # Copied beside the record's directory, then placed into it by the one
    # step: see ONE STEP, JUDGED BY WHAT THE STORE HOLDS in the docstring.
    staging_dir = records_path / (f"{STAGING_DIRECTORY_PREFIX}{name}-"
                                  f"{secrets.token_hex(6)}")
    transferred = subprocess.run(
        rsync_command(host, record_dir, staging_dir),
        capture_output=True, text=True, check=False)
    if transferred.returncode != 0:
        remove_staging_directory(host, staging_dir)
        reason = ("ned-box unreachable" if transferred.returncode == RSYNC_EXIT_CONNECTION_FAILED
                  else f"rsync exit {transferred.returncode}")
        print(f"FAILED: {name} — {reason} during the copy; a later run finishes it.")
        sys.stderr.write(transferred.stderr)
        return EXIT_FAILED
    placed, outcome = place_staged_files(host, staging_dir, store_dir, local)
    if outcome is None:
        if host is None:
            reason = placed.stdout
        elif placed.returncode == RSYNC_EXIT_CONNECTION_FAILED:
            reason = "ned-box unreachable"
        else:
            reason = f"ssh exit {placed.returncode}"
        print(f"FAILED: {name} — {reason} while placing the copied files; "
              f"a later run finishes it.")
        sys.stderr.write(placed.stderr)
        return EXIT_FAILED
    if outcome["differing"]:
        return refuse(outcome["differing"])
    added, stored = outcome["added"], outcome["stored"]
    displaced_triage_digest = outcome["displaced"]
    if displaced_triage_digest is not None and TRIAGE_FILE_REPLACED_IN_THE_STORE in added:
        added.remove(TRIAGE_FILE_REPLACED_IN_THE_STORE)
    if displaced_triage_digest is not None:
        triage_relative = TRIAGE_FILE_REPLACED_IN_THE_STORE
        # The triage's path in the store on ned-box, which the snapshots copy:
        # the store's root from this module's constant, since the destination
        # may be a local override and the snapshots never are, and the kind
        # from the destination this call was given, since a caller such as
        # scripts/sanity-check-record-ship.py ships its own kind. Quoted, with
        # the snapshot glob left outside the quotes for the shell to expand.
        stored_triage = shlex.quote(str(
            split_destination(LOG_STORE_RECORDS_DESTINATION)[1].parent
            / records_path.name / name / triage_relative))
        # After the copy has landed and never on stdout, which carries the
        # summary and the citation. See rule 4 for what this line is for.
        print(f"{PROGRAM}: REPLACED {triage_relative} in the store — the content "
              f"it held was sha256 {displaced_triage_digest}, and what is there "
              f"now is sha256 {local[triage_relative]}.\n"
              f"{PROGRAM}: if the displaced triage was wanted, look for the file "
              f"whose sha256 is the first digest above in ned-box's Timeshift "
              f"snapshots: on ned-box, run `sha256sum "
              f"/mnt/backup/timeshift/snapshots/*/localhost{stored_triage}` and "
              f"take a snapshot whose line shows that digest.", file=sys.stderr)
    # The replaced triage.md is read back and judged like an added file: an
    # overlapping shipment's replacement can land after this one's, and then
    # the store holds the other shipment's triage, not this one's.
    judged = added + ([TRIAGE_FILE_REPLACED_IN_THE_STORE]
                      if displaced_triage_digest is not None else [])
    taken = sorted(relative for relative in judged
                   if relative in stored and stored[relative] != local[relative])
    if taken:
        return refuse(taken)
    missing = sorted(relative for relative in judged if relative not in stored)
    if missing:
        print(f"FAILED: {name} — not in the store after the copy: "
              f"{', '.join(missing)}; a later run finishes it.")
        sys.stderr.write(placed.stderr)
        return EXIT_FAILED
    if not added and displaced_triage_digest is None:
        return nothing_new()
    summary = []
    if added:
        summary.append(f"{len(added)} file(s) added")
    if displaced_triage_digest is not None:
        summary.append(f"{TRIAGE_FILE_REPLACED_IN_THE_STORE} replaced")
    print(f"shipped: {name} — {'; '.join(summary)}; record at {citation}")
    return EXIT_SHIPPED


def ship_from_command_line(description: str, records_dir: pathlib.Path,
                           destination, argv=None) -> int:
    """The `<record directory> | --all` command line, for this program and for
    the other kinds that ship record directories the same way.

    scripts/sanity-check-record-ship.py is the second caller:
    same command line, same rules, same exits, its own kind directory in the
    store and its own directory in the checkout. It calls this rather than
    holding a second copy, so the two cannot drift on what --all skips or what
    each exit code means.

    RULE 4 REACHES THAT KIND ONLY THROUGH THE NAME triage.md, which a
    sanity-check record does not use: its twice-written file is
    finding-dispositions.md, written at the run's close and updated as the
    findings' status moves, and it stays add-only and refused on difference.
    That is the same defect rule 4 fixes here, left open in that kind.

    `records_dir` is where --all looks in this checkout; `destination` is the
    (host, path) pair the caller got from destination_for_this_machine, with
    its kind already chosen.
    """
    parser = argparse.ArgumentParser(
        description=description, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("record_directory", nargs="?",
                        help="one record directory, relative to the repo root or absolute")
    parser.add_argument("--all", action="store_true",
                        help=f"every directory under {records_dir.name}/ in this checkout")
    args = parser.parse_args(argv)
    if bool(args.record_directory) == args.all:
        print("FAILED: give one record directory, or --all")
        return EXIT_BAD_INVOCATION

    host, records_path = destination

    if not args.all:
        record_dir = pathlib.Path(args.record_directory)
        if not record_dir.is_absolute():
            record_dir = REPO_ROOT / record_dir
        return ship_one(host, records_path, record_dir.resolve())

    directories = sorted(p for p in records_dir.glob("*") if p.is_dir()) \
        if records_dir.is_dir() else []
    shipped, refused, failed, skipped = [], [], [], []
    for record_dir in directories:
        # An empty directory is not a cold-read-record and not a failure: a run
        # that made no reports leaves one, and counting it failed would make
        # every --all exit 1 until somebody deleted it. A single empty
        # directory named on the command line is still exit 64.
        if not any(record_dir.iterdir()):
            print(f"skipped: {record_dir.name} — empty directory")
            skipped.append(record_dir.name)
            continue
        code = ship_one(host, records_path, record_dir)
        {EXIT_SHIPPED: shipped, EXIT_REFUSED: refused}.get(code, failed).append(record_dir.name)
    print(f"--all: {len(shipped)} shipped, {len(refused)} refused"
          f"{' (' + ', '.join(refused) + ')' if refused else ''}, {len(failed)} failed"
          f"{' (' + ', '.join(failed) + ')' if failed else ''}, {len(skipped)} skipped"
          f"{' (' + ', '.join(skipped) + ')' if skipped else ''}, of {len(directories)}")
    if failed:
        return EXIT_FAILED
    return EXIT_REFUSED if refused else EXIT_SHIPPED


def main() -> int:
    return ship_from_command_line(__doc__, RECORDS_DIR, destination_for_this_machine())


if __name__ == "__main__":
    sys.exit(main())
