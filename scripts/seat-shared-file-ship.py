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
walk's four files, a transcript -- goes to that kind through its own program,
not here.

THERE IS NO NETWORK DRIVE, and this is not one. The store is a directory on
ned-box's internal disk, snapshotted every ten minutes by Timeshift to a
separate internal disk. Off-machine, not off-site.

THE THREE RULES ARE THE RECORD SHIPPER'S (scripts/cold-read-record-ship.py),
because this writes into the same store: ADD-ONLY, so a file already there is
never replaced; REFUSE ON DIFFERENCE, so a second file of the same name whose
content differs is refused before anything copies, naming both; FAIL LOUDLY,
so an unreachable ned-box prints a line opening FAILED and exits non-zero
with the file still on disk for a later run.

    A KNOWN FRICTION, RAISED FOR THE USER'S RULING AND NOT DECIDED HERE.
    Add-only was ruled for RECORDS, which are immutable logs. A seat's shared
    file often evolves -- a draft revised twice in an afternoon -- and under
    add-only each revision needs a new name. The collision add-only exists to
    prevent (two machines writing one path on one day) cannot arise inside a
    seat's own directory, where that seat is the only writer, so allowing
    replacement there is defensible. It is not done unilaterally: the store's
    rule is the store's rule until the user changes it. `--replace` is the
    one flag this would take.

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

OUTPUT. Exactly one line on stdout per file -- the citation, or `REFUSED:`,
or `FAILED:`. Everything else is on stderr. Exit 0 when every file shipped,
2 when any was refused and none failed, 1 when any failed, 64 for a bad
invocation.

THE DESTINATION IS DERIVED from the record shipper's one constant, so a move
of the store is still one edit in one file. The environment variable
COLD_READ_RECORD_SHIP_DESTINATION overrides it, as it does there, which is
how the tests point at a scratch directory.
"""

import argparse
import hashlib
import importlib.util
import json
import os
import pathlib
import shlex
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
    "cold_read_record_ship", REPO_ROOT / "scripts" / "cold-read-record-ship.py")
shipper = importlib.util.module_from_spec(_shipper_spec)
_shipper_spec.loader.exec_module(shipper)

SEATS_KIND_DIRECTORY = "seats"
SEAT_NAME_ENVIRONMENT_VARIABLE = "CLAUDE_CODE_TASK_LIST_ID"
SEAT_NAME_PREFIX = "nedschorus-"
SEAT_NAME_SUFFIX = "-tasks"

EXIT_SHIPPED = shipper.EXIT_SHIPPED
EXIT_FAILED = shipper.EXIT_FAILED
EXIT_REFUSED = shipper.EXIT_REFUSED
EXIT_BAD_INVOCATION = shipper.EXIT_BAD_INVOCATION

# Appended to the store's README when it does not already describe this kind.
# The record shipper's STORE_README carries the same bullet, so a store born
# fresh is complete and one that predates this program is completed on first
# use. The two copies are the drift this program accepts; they are one PR's
# worth of text and the test asserts they match.
SEATS_README_BULLET = """\
- `seats/` -- the one kind organized by PRODUCER rather than by kind: one
  directory per agent seat, holding the files that seat must cite from the
  other machine and that belong to no other kind. Written by
  scripts/seat-shared-file-ship.py in the nedschorus repository, which prints
  the citation to paste. Add-only, like the records beside it.
"""


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


def readme_with_seats_bullet(existing: str) -> str:
    """The README's text with the seats bullet in its list of kinds.

    An append to the end of the file would put the bullet after the closing
    paragraph, where it reads as an afterthought rather than as one of the
    kinds -- which is what a first version of this did to the live store. The
    bullet goes after the last existing bullet and its indented continuation
    lines instead, so the list stays a list. A README with no bullet list at
    all is appended to, which is the only thing left to do with it.
    """
    lines = existing.splitlines(keepends=True)
    last_bullet_end = None
    for index, line in enumerate(lines):
        if line.startswith("- "):
            last_bullet_end = index + 1
        elif last_bullet_end == index and line.startswith("  ") and line.strip():
            last_bullet_end = index + 1
    if last_bullet_end is None:
        separator = "" if existing.endswith("\n") or not existing else "\n"
        return existing + separator + SEATS_README_BULLET
    return "".join(lines[:last_bullet_end]) + SEATS_README_BULLET + "".join(
        lines[last_bullet_end:])


def ensure_seat_directory(destination: SeatsStoreDestination, seat: str):
    """The seat's directory exists and the store's root has a README.

    Two cases, and they match the record shipper's `ensure_store`. NO README
    AT ALL -- a store whose first writer was this program -- gets the record
    shipper's whole STORE_README, imported rather than copied; that text
    already lists the seats kind, so there is no bullet left to append. A
    README that is already there and predates this program gains the bullet
    in its list of kinds instead.

    The README is only ever ADDED to: one that already describes the kind is
    untouched. Remotely both writes are done by a Python one-liner over ssh
    rather than a shell append, because placing the bullet in the list needs
    more than `cat >>`; the two texts go over stdin as JSON, and the file is
    written whole to a temporary sibling and renamed, so an interrupted run
    cannot leave a half README.
    """
    seat_directory = destination.seats_path / seat
    root = destination.seats_path.parent
    readme_path = f"{root}/README.md"
    if destination.copy_host is None:
        pathlib.Path(seat_directory).mkdir(parents=True, exist_ok=True)
        readme = pathlib.Path(readme_path)
        if not readme.exists():
            readme.write_text(shipper.STORE_README, encoding="utf-8")
        else:
            existing = readme.read_text(encoding="utf-8")
            if existing and f"`{SEATS_KIND_DIRECTORY}/`" not in existing:
                readme.write_text(readme_with_seats_bullet(existing),
                                  encoding="utf-8")
        return subprocess.CompletedProcess([], 0, "", "")
    remote_program = (
        "import json,os,pathlib,sys\n"
        f"p=pathlib.Path({readme_path!r})\n"
        "texts=json.loads(sys.stdin.read())\n"
        f"k={'`' + SEATS_KIND_DIRECTORY + '/`'!r}\n"
        "out=None\n"
        "if not p.exists():\n"
        "    out=texts['store_readme']\n"
        "else:\n"
        "    t=p.read_text(encoding='utf-8')\n"
        "    if t and k not in t:\n"
        "        b=texts['seats_bullet']\n"
        "        lines=t.splitlines(keepends=True); end=None\n"
        "        for i,l in enumerate(lines):\n"
        "            if l.startswith('- '): end=i+1\n"
        "            elif end==i and l.startswith('  ') and l.strip(): end=i+1\n"
        "        out=(t+b) if end is None else (''.join(lines[:end])+b+''.join(lines[end:]))\n"
        "if out is not None:\n"
        "    tmp=p.with_name(p.name+'.new')\n"
        "    tmp.write_text(out,encoding='utf-8'); os.replace(tmp,p)\n")
    script = (f"mkdir -p -- '{seat_directory}' && "
              f"python3 -c {shlex.quote(remote_program)}")
    return subprocess.run(
        shipper.SSH_COMMAND + [destination.copy_host, script],
        input=json.dumps({"store_readme": shipper.STORE_README,
                          "seats_bullet": SEATS_README_BULLET}),
        capture_output=True, text=True, check=False)


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
    at all, so an interrupted copy leaves no half file behind."""
    destination = f"{copy_host}:{target}" if copy_host else str(target)
    command = ["rsync", "-a", "--timeout", shipper.RSYNC_IO_TIMEOUT_SECONDS]
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
    if existing_digest is not None:
        if existing_digest == local_digest:
            print(citation, flush=True)
            print(f"{PROGRAM}: already in the store, byte-identical; nothing "
                  f"copied", file=sys.stderr)
            return EXIT_SHIPPED
        print(f"REFUSED: {seat}/{stored_name} — a different file of that name "
              f"is already in the store; nothing was copied", flush=True)
        print(f"{PROGRAM}: store has sha256 {existing_digest}, local file has "
              f"{local_digest}.\n"
              f"{PROGRAM}: the store is add-only. Ship under another name "
              f"(--as), or read the stored one first:\n"
              f"  scp {citation} ./", file=sys.stderr)
        return EXIT_REFUSED

    copied = rsync_one_file(destination.copy_host, source, target)
    if copied.returncode != 0:
        print(f"FAILED: {seat}/{stored_name} — rsync exited "
              f"{copied.returncode}", flush=True)
        print(copied.stderr.strip(), file=sys.stderr)
        return EXIT_FAILED
    print(citation, flush=True)
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
        outcome = ship_one_file(destination, seat, source, stored_name)
        if outcome == EXIT_FAILED or worst == EXIT_FAILED:
            worst = EXIT_FAILED
        elif outcome == EXIT_REFUSED:
            worst = EXIT_REFUSED
    return worst


if __name__ == "__main__":
    sys.exit(main())
