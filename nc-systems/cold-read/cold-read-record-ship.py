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

The store's directories are created on first use, and a README.md at the
store's root is written when absent -- it says what the store is and that
cold-read-records dated before 2026-09-08 predate the frozen cold-read-target
-- from the text in this file.

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
import os
import importlib.util
import pathlib
import socket
import subprocess
import sys
import tempfile

# This file sits in nc-systems/cold-read/, two directories below the root.
REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
# What a cold-read-record is called and where it lives, defined once in a
# module so no program keeps its own copy (user-ruled 2026-09-19, walk
# file-naming-and-location-standards-cold-read-findings, item 4). The
# convention -- importlib for a module whose filename has hyphens -- is
# nc-systems/cold-read/cold-read-cell-common.py's.
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

EXIT_SHIPPED = 0
EXIT_FAILED = 1
EXIT_REFUSED = 2
EXIT_BAD_INVOCATION = 64

# The note at the door of the log-store, written into it by this program.
#
# AGENT-FACING TEXT, so it is instruction and nothing else: what the store is,
# how to cite a file in it, where the naming rules are, and what to edit to
# change this file. No dates, no ruling citations, no account of why it reads
# this way -- those live here and in `refresh_store_readme` below, where a
# maintainer reads them (user-ruled 2026-09-18, on the force-push guard's
# refusal, in CLAUDE.md).
#
# It used to list every kind and how its files were named. That restatement
# went stale at each ruling that changed one, and when the cold-read-records'
# triage file was renamed from dispositions.md to triage.md a reader following
# this text would have looked for the old name, not found it, and reported a
# finished triage as unfinished. The rules now live in the wiki page it points
# at; what the store is and how to cite a file in it do not change
# (user-ruled 2026-09-19, walk
# file-naming-and-location-standards-cold-read-findings, item 5). The
# 2026-09-07 ruling that made the store at all is "separate the system from
# its logs".
STORE_README = """\
# nedschorus-logs

The log-store: the byproducts of the nedschorus project's work that are not
the system. Good data, never part of the repository. One subdirectory per
kind.

Cite a file here with its host, in the form scp takes:
`nedlern@ned-box:/home/nedlern/nedschorus-logs/<kind>/<path>`.

What each subdirectory holds, and how its files are named, is not written
here. Read it in the nedschorus repository, which this machine also clones:
docs/nedschorus-wiki/nedschorus-file-naming-and-location-standards.md

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


def rsync_one_file_command(host, source: pathlib.Path,
                           target: pathlib.PurePosixPath) -> list:
    """rsync of ONE file over the store's copy of it: the replace path rule 4
    describes, which the add-only copy above cannot take (--ignore-existing is
    what it is for). The source is a file and not a directory, so no trailing
    slash is appended to either side.

    --ignore-times, because whether to copy was already decided here by
    comparing sha256 on both sides. rsync's own quick check is size and
    modification time to the second and it skips a file the two agree on: a
    triage rewritten to the same length within the second the stored copy
    carries would be silently not copied, leaving the store's old bytes behind
    a line saying they had been replaced. Measured on this Mac's openrsync,
    which skipped exactly that file, by scripts/seat-shared-file-ship.py's
    `rsync_one_file`, and scripts/walk-files-ship.py passes the flag for the
    same reason. Never --inplace: rsync writes the file whole or not at all,
    so an interrupted replacement leaves the store's old copy intact."""
    destination = f"{host}:{target}" if host else str(target)
    command = ["rsync", "-a", "--ignore-times", "--timeout",
               RSYNC_IO_TIMEOUT_SECONDS]
    if host:
        command += ["-e", " ".join(SSH_COMMAND)]
    return command + [str(source), destination]


def refresh_store_readme(root) -> None:
    """STORE_README into <root>/README.md, on this machine, when it differs.

    REWRITTEN WHENEVER IT DIFFERS, not only when it is missing (user-ruled
    2026-09-19, walk file-naming-and-location-standards-cold-read-findings,
    item 5). The README was written once, when the store was new, and never
    again, so every later ruling that changed the text left the live file
    behind: read over ssh on 2026-09-19 it still gave cold-read-record names
    in the old date-first order, still called the triage file
    dispositions.md, still said a walk has four files, and had no analysis/
    entry at all. Refreshing here means the next shipment carries a change,
    and nobody edits a file on ned-box by hand to land one.

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
    world-readable (0664 on ned-box, read 2026-09-20), so the mode is widened
    before the rename rather than leaving the store's index owner-only.
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
    shipment happened to run to completion. Interruption is measured here,
    not hypothetical: the ssh link to ned-box dropped eight times across
    2026-09-19 and 2026-09-20, the last with `client_loop: send disconnect:
    Broken pipe`. `mkdir -p` of the kind's directory runs first and creates
    the root as its parent, so `mktemp` has somewhere to put the temporary on
    a store that is new, and the closing `rm -f` removes it when `cmp` found
    no difference.

    WHAT ARRIVED IS COUNTED BEFORE ANYTHING LANDS. A dropped link is not an
    error the shell can see: it is a clean EOF on a short stream, so `cat`
    returns 0 on the prefix that arrived, `cmp` finds a real difference, and
    `mv` publishes the truncation over a good README with the script exiting
    0. Measured by the merge lane on 2026-09-21 against the previous head: a
    60-byte prefix of this text replaced the live README, return code 0,
    nothing on stderr. So the text's byte count is written into this script
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
    two overlapping shipments on one name collide two ways, both measured by
    the merge lane on 2026-09-21: the winner's closing `rm -f` falls between
    the loser's `cat` and its `cmp`, so the loser exits 1 on a store that is
    correct; and when the two send different text, which two checkouts at
    different commits do, the winner's `mv` renames the inode out from under a
    writer still holding it open and the loser's remaining bytes land inside
    the live README. A unique name is reachable by neither. `mktemp` creates
    the temporary 0600, so the mode is widened before the rename, the store's
    README having always been world-readable (0664 on ned-box, read
    2026-09-20).

    A temporary orphaned by a drop is no longer overwritten by the next run,
    each run's name being its own: a drop that arrives as a short stream is
    refused and its temporary removed here, and one left by a shell killed
    outright stays beside the README, inert, until it is removed by hand. A
    sweep of README.md.* cannot be added here without racing exactly the
    overlap the unique name fixes.

    POSIX shell only -- ned-box's /bin/sh is dash, with uutils coreutils
    0.8.0 for `mktemp`, `wc` and `chmod` and GNU diffutils 3.12 for `cmp`; the
    template form of `mktemp` and `[ "$(wc -c < f)" -eq n ]` were run there on
    2026-09-20. `chmod` takes `--` BEFORE the mode: a trailing one is a file
    name to this Mac's BSD chmod, which then exits 1.
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
    rsync's own --itemize-changes was tried first and dropped: the Mac ships
    openrsync and ned-box ships rsync 3.4, and their itemize formats differ.
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
    # alone. The digest it displaces is kept for the stderr announcement, which
    # is written only once the copy has landed.
    displaced_triage_digest = None
    if TRIAGE_FILE_REPLACED_IN_THE_STORE in differing:
        differing.remove(TRIAGE_FILE_REPLACED_IN_THE_STORE)
        displaced_triage_digest = in_store[TRIAGE_FILE_REPLACED_IN_THE_STORE]
    if differing:
        # The loop only gathers; the one print comes after it, so a
        # cold-read-record with several differing files still gets
        # exactly one stdout line.
        described = []
        for relative in differing:
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

    if not new_files and displaced_triage_digest is None:
        print(f"shipped: {name} — nothing new, all files already there; "
              f"record at {citation}")
        return EXIT_SHIPPED
    if new_files:
        transferred = subprocess.run(
            rsync_command(host, record_dir, store_dir, "--ignore-existing"),
            capture_output=True, text=True, check=False)
        if transferred.returncode != 0:
            reason = ("ned-box unreachable" if transferred.returncode == RSYNC_EXIT_CONNECTION_FAILED
                      else f"rsync exit {transferred.returncode}")
            print(f"FAILED: {name} — {reason} during the copy; a later run finishes it.")
            sys.stderr.write(transferred.stderr)
            return EXIT_FAILED
    if displaced_triage_digest is not None:
        # The replacement is its own rsync of that one file: the copy above
        # passes --ignore-existing, which is what keeps every other file
        # add-only, and a file the store already holds is exactly what it
        # skips.
        triage_relative = TRIAGE_FILE_REPLACED_IN_THE_STORE
        replaced = subprocess.run(
            rsync_one_file_command(host, record_dir / triage_relative,
                                   store_dir / triage_relative),
            capture_output=True, text=True, check=False)
        if replaced.returncode != 0:
            reason = ("ned-box unreachable" if replaced.returncode == RSYNC_EXIT_CONNECTION_FAILED
                      else f"rsync exit {replaced.returncode}")
            print(f"FAILED: {name} — {reason} while replacing "
                  f"{triage_relative}; a later run finishes it.")
            sys.stderr.write(replaced.stderr)
            return EXIT_FAILED
        # The triage's path in the store on ned-box, which the snapshots copy,
        # built from this module's constant, not written out again; the
        # destination may be a local override, the snapshots never.
        stored_triage = (split_destination(LOG_STORE_RECORDS_DESTINATION)[1]
                         / name / triage_relative)
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
    summary = []
    if new_files:
        summary.append(f"{len(new_files)} file(s) added")
    if displaced_triage_digest is not None:
        summary.append(f"{TRIAGE_FILE_REPLACED_IN_THE_STORE} replaced")
    print(f"shipped: {name} — {'; '.join(summary)}; record at {citation}")
    return EXIT_SHIPPED


def ship_from_command_line(description: str, records_dir: pathlib.Path,
                           destination, argv=None) -> int:
    """The `<record directory> | --all` command line, for this program and for
    the other kinds that ship record directories the same way.

    scripts/sanity-check-record-ship.py (nedschorus#392) is the second caller:
    same command line, same rules, same exits, its own kind directory in the
    store and its own directory in the checkout. It calls this rather than
    holding a second copy, so the two cannot drift on what --all skips or what
    each exit code means.

    RULE 4 REACHES THAT KIND ONLY THROUGH THE NAME triage.md, which a
    sanity-check record does not use: its twice-written file is
    finding-dispositions.md, written at the run's close and updated as the
    findings' status moves, and it stays add-only and refused on difference.
    That is the same defect rule 4 fixes here, in a second program, and it is
    a second topic -- the 2026-09-20 ruling names this program's triage.md.

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
        # that made no reports left it, and counting it failed made every --all
        # exit 1 until somebody deleted it (found by PR #285's reviewer). A
        # single empty directory named on the command line is still exit 64.
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
