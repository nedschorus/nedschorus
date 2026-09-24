#!/usr/bin/env python3
"""Put one file a seat must share into the log-store, and print its citation.

WHAT PROBLEM THIS SOLVES (user-ruled 2026-09-08). A seat often has a file the
other machine must read and git will not carry: a measurement output, a
prompt draft, a survey, a scratch report another seat is asked to look at.
Until now those stayed where they were written, and a citation of them was
unreachable from anywhere else -- the 2026-09-08 cross-machine survey
measured 127 unresolvable citations against 14 resolvable. The user's ruling:
"give every agent a directory ... to put all the files it needs to share that
are not in git or git-main". This program is the way a file gets there.

WHERE IT GOES. `seats/<seat>/<name>` under the log-store, alongside the kinds
that are organized by kind:

    nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/<seat>/<name>

`seats/` is the one kind organized by PRODUCER rather than by kind, because
what it holds has nothing else in common: it is whatever one seat needed to
share. A file that belongs to an existing kind -- a cold-read record, a
walk's five files, a transcript -- goes to that kind through its own program,
not here.

THERE IS NO NETWORK DRIVE, and this is not one. The store is a directory on
ned-box's internal disk, snapshotted by Timeshift to a separate internal disk.
Off-machine, not off-site.

THE SNAPSHOT CADENCE IS NOT A PROMISE, which is why no printed line states it.
Measured on 2026-09-23 with `sudo -n timeshift --list` on ned-box: daily
snapshots through 2026-09-21_16-10-01, ten-minute ones only from
2026-09-22_10-50-02 on (the configuration keeps 24 hourly, and older ones rotate
out), and `/home/nedlern/**` included. Until 2026-09-22 these programs printed
"the store is snapshotted every ten minutes by Timeshift" at the moment an
agent decides whether a displaced file is recoverable; for the corrupted walk
minutes of 2026-09-21 that was false, and it sent the search after a snapshot
that never existed. The printed line now says only where to look and how to
list what exists (task 112 of the cold-read-research seat; CLAUDE.md: text a
program hands an agent at the moment it must act is instruction and nothing
else).

THE STORE'S RULES HOLD HERE, WITH ONE DIFFERENCE INSIDE `seats/`. FAIL
LOUDLY is the record shipper's (nc-systems/cold-read/cold-read-record-ship.py) and is
kept: an unreachable ned-box prints a line opening FAILED and exits non-zero
with the file still on disk for a later run. ADD-ONLY and REFUSE ON
DIFFERENCE remain the rules of the records kind, which that program still
enforces unchanged; here a file of the same name whose content differs is
REPLACED, and the replacement is announced.

    A SEAT REPLACES ITS OWN FILES. USER-RULED 2026-09-09, verbatim: "seats
    can replace their own files." Add-only was ruled for RECORDS, which are
    immutable logs, and the collision it prevents is two writers landing on
    one path -- two machines reviewing one document on one day. Inside
    `seats/<seat>/` that seat is the only writer, so that collision cannot
    arise, and refusing bought nothing while costing friction: a seat's
    shared file evolves -- a draft revised twice in an afternoon -- and under
    add-only each revision needed a name of its own. Friction is what drives
    non-use, and non-use is the problem this shared area exists to solve. So
    a plain invocation replaces. There is no flag to ask for it, because a
    flag is the friction again.

    THE REPLACEMENT IS NOT SILENT, AND THAT IS THE POINT. A seat is a series
    of SESSIONS, not one process. This fleet hands off constantly, and a
    fresh session can hold an older local copy of a file a previous session
    already shipped; shipping that copy overwrites the newer stored one, and
    silence would leave nothing to notice it by. So a replacement prints on
    stderr that it replaced a file and the sha256 the store held. The event
    is then visible in the session's own output, and the bytes it displaced
    are identifiable by that digest in a Timeshift snapshot on ned-box, if a
    snapshot taken before the replacement is still kept (see THE SNAPSHOT
    CADENCE IS NOT A PROMISE, above). stdout does not change: one line, the
    citation.

WHY IT PRINTS THE CITATION. The line this program prints on success is the
exact text to paste into a document, in the scp form that works from either
machine. That is deliberate and it is the point: an agent that needs a
citable path gets the correct one faster by running this than by writing a
local path from memory. A tool nobody has a reason to run does not get run --
the same store's `2026-09-05-perfect-test-cases` directory sat unshipped for
three days with a working shipper on disk.

THE CITATION ALWAYS CARRIES THE HOST, ned-box included, where the copy itself
is a local one that wants no ssh. The host to COPY to and the host to CITE
are two different things, and `seats_path_for_this_machine` keeps them apart;
its docstring says why, because collapsing them back into one host is what
printed an unusable citation on the machine that writes most of them.

WHAT DOES NOT ENFORCE USE. Nothing here fires on its own. The mechanical
check that catches an unreachable citation after the fact is filed as a
caller on nedschorus#42, the reference-integrity checker; a citation is the
observable moment, since a file nobody cites needs no sharing.

USAGE
  scripts/seat-shared-file-ship.py <file> [<file> ...]
  scripts/seat-shared-file-ship.py --seat merge-lane notes.md
  scripts/seat-shared-file-ship.py --as survey-2026-09-08.md /tmp/out.md

THE SEAT NAME comes from `--seat`, else from CLAUDE_CODE_TASK_LIST_ID, which
the supervisor sets to `nedschorus-<seat name>-tasks` in every seat's
environment. With neither, the program refuses rather than guessing: a
directory named for the wrong seat is worse than an error, because the file
is then filed where nobody will look for it.

OUTPUT. Exactly one line on stdout per file -- the citation, or `FAILED:`.
Everything else is on stderr, the line announcing a replacement included.
Exit 0 when every file shipped, 1 when any failed, 64 for a bad invocation.

THE DESTINATION IS DERIVED from the record shipper's one constant, so a move
of the store is still one edit in one file. The environment variable
COLD_READ_RECORD_SHIP_DESTINATION overrides it, as it does there, which is
how the tests point at a scratch directory.
"""

import argparse
import hashlib
import importlib.util
import os
import pathlib
import subprocess
import sys
import typing

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
PROGRAM = "seat-shared-file-ship"

# The record shipper is imported rather than copied, so the two programs
# cannot drift on what the store is, how ssh and rsync are invoked, or how an
# scp-form destination is split. The convention -- importlib for a module
# whose filename has hyphens -- is the cold-read cell launchers'.
_shipper_spec = importlib.util.spec_from_file_location(
    "cold_read_record_ship", REPO_ROOT / "nc-systems" / "cold-read" / "cold-read-record-ship.py")
shipper = importlib.util.module_from_spec(_shipper_spec)
_shipper_spec.loader.exec_module(shipper)

SEATS_KIND_DIRECTORY = "seats"
SEAT_NAME_ENVIRONMENT_VARIABLE = "CLAUDE_CODE_TASK_LIST_ID"
SEAT_NAME_PREFIX = "nedschorus-"
SEAT_NAME_SUFFIX = "-tasks"

EXIT_SHIPPED = shipper.EXIT_SHIPPED
EXIT_FAILED = shipper.EXIT_FAILED
EXIT_BAD_INVOCATION = shipper.EXIT_BAD_INVOCATION



def seat_name_from_environment():
    """The seat's name from the task-list id the supervisor sets, or None.

    `nedschorus-cold-read-research-tasks` -> `cold-read-research`. Anything
    not of that shape returns None rather than a guess.
    """
    value = os.environ.get(SEAT_NAME_ENVIRONMENT_VARIABLE, "").strip()
    if not value.startswith(SEAT_NAME_PREFIX) or not value.endswith(SEAT_NAME_SUFFIX):
        return None
    name = value[len(SEAT_NAME_PREFIX):-len(SEAT_NAME_SUFFIX)]
    return name or None


class SeatsStoreDestination(typing.NamedTuple):
    """Where this run copies to, what host its citations name, and the path.

    The two hosts are separate fields rather than one because they differ,
    and the fields are named so a caller cannot pass them in the wrong
    order. `seats_path_for_this_machine` is what fills it in.
    """

    copy_host: typing.Optional[str]
    citation_host: typing.Optional[str]
    seats_path: pathlib.PurePosixPath


def seats_path_for_this_machine() -> SeatsStoreDestination:
    """The record shipper's destination with the kind swapped to `seats`, so
    the store's location stays defined in exactly one place -- and with the
    copy's host and the citation's host told apart.

    TWO HOSTS, AND THEY ARE NOT THE SAME HOST. The COPY host is what ssh and
    rsync are handed: on ned-box itself it is None, because the store is a
    directory on that machine's own disk and no ssh should run. The CITATION
    host is what the printed line carries, and CLAUDE.md fixes that form --
    the scp form shown in this module's docstring -- because a citation is
    pasted into a document that is read from EITHER machine. The seats run
    ON ned-box, so the machine where the copy needs no host is exactly the
    machine that writes most of the citations.

    So when the destination comes from the record shipper's constant, the
    citation host is that constant's host whatever machine we are on, while
    the copy host stays None on ned-box and the copy stays local. When
    COLD_READ_RECORD_SHIP_DESTINATION overrides the destination -- which is
    how the tests point at a scratch directory -- both hosts come from the
    override, and there a bare local path legitimately has none.

    Do not simplify the two back into one. One host is what this had first,
    and on ned-box it printed a bare /home/nedlern/... path that resolves
    from nowhere else.
    """
    copy_host, records_path = shipper.destination_for_this_machine()
    if os.environ.get(shipper.DESTINATION_ENVIRONMENT_VARIABLE):
        citation_host = copy_host
    else:
        citation_host, _ = shipper.split_destination(
            shipper.LOG_STORE_RECORDS_DESTINATION)
    return SeatsStoreDestination(copy_host, citation_host,
                                 records_path.parent / SEATS_KIND_DIRECTORY)


def ensure_seat_directory(destination: SeatsStoreDestination, seat: str):
    """The seat's directory exists and the store's root holds STORE_README.

    BOTH THE DIRECTORY AND THE README ARE THE RECORD SHIPPER'S RULES, called
    here rather than restated: `refresh_store_readme` locally and
    `make_directory_and_refresh_readme_script` over ssh, so this program and
    nc-systems/cold-read/cold-read-record-ship.py cannot disagree about when the README is
    rewritten. One ssh round trip remotely, as before.

    THIS PROGRAM USED TO APPEND A `seats/` BULLET to a README that lacked
    one, placing it inside the list of kinds. The README stopped listing the
    kinds on 2026-09-19 (user-ruled, walk
    file-naming-and-location-standards-cold-read-findings, item 5): what each
    subdirectory holds and how its files are named lives in
    docs/nedschorus-wiki/nedschorus-file-naming-and-location-standards.md
    instead, because a restatement here went stale at every ruling. With no
    list of kinds there is no bullet to place, and appending one would have
    started a fight: this program would add it, the record shipper would see
    the text differ from STORE_README and write the pointer back, on every
    shipment either made.

    The stdin encoding is pinned to UTF-8, as it is in the record shipper's
    `ensure_store`, because the remote script counts the bytes it receives
    against a count taken in UTF-8.
    """
    seat_directory = destination.seats_path / seat
    root = destination.seats_path.parent
    if destination.copy_host is None:
        pathlib.Path(seat_directory).mkdir(parents=True, exist_ok=True)
        shipper.refresh_store_readme(root)
        return subprocess.CompletedProcess([], 0, "", "")
    script = shipper.make_directory_and_refresh_readme_script(
        seat_directory, root)
    return subprocess.run(
        shipper.SSH_COMMAND + [destination.copy_host, script],
        input=shipper.STORE_README,
        capture_output=True, text=True, encoding="utf-8", check=False)


def stored_digest(copy_host, target):
    """(process, digest-or-None) for the store's copy of one file.

    None means the file is not there; an unreachable host is the process's
    non-zero return with a digest of None, which the caller separates by
    checking the return code.
    """
    if copy_host is None:
        path = pathlib.Path(target)
        if not path.is_file():
            return subprocess.CompletedProcess([], 0, "", ""), None
        return (subprocess.CompletedProcess([], 0, "", ""),
                hashlib.sha256(path.read_bytes()).hexdigest())
    script = f"if [ -f '{target}' ]; then sha256sum -- '{target}'; fi"
    completed = subprocess.run(shipper.SSH_COMMAND + [copy_host, script],
                               capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        return completed, None
    digest = completed.stdout.split(" ", 1)[0].strip()
    return completed, digest or None


def rsync_one_file(copy_host, source: pathlib.Path,
                   target) -> subprocess.CompletedProcess:
    """One file into the store. Never --inplace: rsync writes it whole or not
    at all, so an interrupted copy leaves no half file behind.

    --ignore-times because whether to copy was already decided here, by
    comparing sha256 on both sides. rsync's own quick check is size and
    modification time to the second, and it skips a file the two agree on:
    a revision that kept the file's length and was written in the same
    second as the stored copy's timestamp would be silently not copied,
    leaving the store's old bytes behind a printed citation and a line
    saying they had been replaced. Measured on this Mac's openrsync, which
    skipped exactly that file. With nothing in the store to skip the flag
    does nothing.
    """
    destination = f"{copy_host}:{target}" if copy_host else str(target)
    command = ["rsync", "-a", "--ignore-times", "--timeout",
               shipper.RSYNC_IO_TIMEOUT_SECONDS]
    if copy_host:
        command += ["-e", " ".join(shipper.SSH_COMMAND)]
    return subprocess.run(command + [str(source), destination],
                          capture_output=True, text=True, check=False)


def ship_one_file(destination: SeatsStoreDestination, seat: str,
                  source: pathlib.Path, stored_name: str) -> int:
    """One file, one stdout line, one exit code.

    The copy goes to the destination's copy host and the printed citation
    names its citation host, which on ned-box is a host the copy did not
    need. See `seats_path_for_this_machine`.
    """
    target = destination.seats_path / seat / stored_name
    citation = (f"{destination.citation_host}:{target}"
                if destination.citation_host else str(target))

    if not source.is_file():
        print(f"FAILED: {source} is not a file", flush=True)
        return EXIT_FAILED

    prepared = ensure_seat_directory(destination, seat)
    if prepared.returncode != 0:
        print(f"FAILED: {seat}/{stored_name} — the store could not be reached "
              f"or prepared", flush=True)
        print(prepared.stderr.strip(), file=sys.stderr)
        return EXIT_FAILED

    completed, existing_digest = stored_digest(destination.copy_host, target)
    if completed.returncode != 0:
        print(f"FAILED: {seat}/{stored_name} — the store could not be read",
              flush=True)
        print(completed.stderr.strip(), file=sys.stderr)
        return EXIT_FAILED

    local_digest = hashlib.sha256(source.read_bytes()).hexdigest()
    replaced_digest = None
    if existing_digest is not None:
        if existing_digest == local_digest:
            print(citation, flush=True)
            print(f"{PROGRAM}: already in the store, byte-identical; nothing "
                  f"copied", file=sys.stderr)
            return EXIT_SHIPPED
        replaced_digest = existing_digest

    copied = rsync_one_file(destination.copy_host, source, target)
    if copied.returncode != 0:
        print(f"FAILED: {seat}/{stored_name} — rsync exited "
              f"{copied.returncode}", flush=True)
        print(copied.stderr.strip(), file=sys.stderr)
        return EXIT_FAILED
    print(citation, flush=True)
    if replaced_digest is not None:
        # Never on stdout: that line is the citation and nothing else. See
        # "THE REPLACEMENT IS NOT SILENT" in this module's docstring for what
        # this line is for.
        # The store on ned-box, which the snapshots copy: the record shipper's
        # constant, never written out again here.
        store_root = shipper.split_destination(
            shipper.LOG_STORE_RECORDS_DESTINATION)[1].parent
        print(f"{PROGRAM}: REPLACED {seat}/{stored_name} in the store — the "
              f"content it held was sha256 {replaced_digest}, and what is "
              f"there now is sha256 {local_digest}.\n"
              f"{PROGRAM}: a seat replaces its own files (user-ruled "
              f"2026-09-09). If the displaced bytes were wanted, look for the "
              f"file whose sha256 is the first digest above in ned-box's "
              f"Timeshift snapshots, one directory per snapshot under "
              f"`/mnt/backup/timeshift/snapshots/<snapshot>/localhost{store_root}/` "
              f"on ned-box; `scripts/find-deleted-path-across-backups.py` "
              f"searches them by path.", file=sys.stderr)
    return EXIT_SHIPPED


def main() -> int:
    parser = argparse.ArgumentParser(
        prog=PROGRAM,
        description="Put a file into this seat's shared area in the log-store "
                    "and print the citation for it.")
    parser.add_argument("files", nargs="+", type=pathlib.Path,
                        help="the file or files to share")
    parser.add_argument("--seat", default=None,
                        help="the seat's name; defaults to the one in "
                             "CLAUDE_CODE_TASK_LIST_ID")
    parser.add_argument("--as", dest="stored_name", default=None,
                        help="the name to store it under; defaults to the "
                             "file's own name. One file only.")
    arguments = parser.parse_args()

    seat = arguments.seat or seat_name_from_environment()
    if not seat:
        print(f"{PROGRAM}: no seat name — pass --seat, or run where "
              f"{SEAT_NAME_ENVIRONMENT_VARIABLE} is set to "
              f"{SEAT_NAME_PREFIX}<seat>{SEAT_NAME_SUFFIX}", file=sys.stderr)
        return EXIT_BAD_INVOCATION
    if "/" in seat or seat in (".", ".."):
        print(f"{PROGRAM}: a seat name is one path segment, not {seat!r}",
              file=sys.stderr)
        return EXIT_BAD_INVOCATION
    if arguments.stored_name:
        if len(arguments.files) != 1:
            print(f"{PROGRAM}: --as names one file's destination, so it takes "
                  f"one file, not {len(arguments.files)}", file=sys.stderr)
            return EXIT_BAD_INVOCATION
        if "/" in arguments.stored_name or arguments.stored_name in (".", ".."):
            print(f"{PROGRAM}: --as is one path segment, not "
                  f"{arguments.stored_name!r}", file=sys.stderr)
            return EXIT_BAD_INVOCATION

    destination = seats_path_for_this_machine()
    worst = EXIT_SHIPPED
    for source in arguments.files:
        stored_name = arguments.stored_name or source.name
        if ship_one_file(destination, seat, source, stored_name) == EXIT_FAILED:
            worst = EXIT_FAILED
    return worst


if __name__ == "__main__":
    sys.exit(main())
