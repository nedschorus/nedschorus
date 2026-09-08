#!/usr/bin/env python3
"""Ship one cold-read record directory to the log-store on ned-box.

Usage:
  scripts/cold-read-record-ship.py <record directory>
  scripts/cold-read-record-ship.py --all

WHAT THE LOG-STORE IS (user-ruled 2026-09-07, walk
docs/walk/cold-read-records-branch-and-agent-instructions-queue.md): the
repository is the system and a reviewer report is a log, so cold-read records
never enter git. They go to the log-store, `/home/nedlern/nedschorus-logs/` on
ned-box, one subdirectory per kind of byproduct; records are the kind
`cold-read-records/`, keeping their directory names. A record there is cited
with its host in scp form, so an agent on either machine knows the command:
`nedlern@ned-box:/home/nedlern/nedschorus-logs/cold-read-records/2026-09-05-SKILL/dispositions.md`.
The record directory in the checkout stays what it was: a gitignored
directory under cold-read-records/, written by the grid and by the agent.

WHAT ONE RUN DOES. The directory is copied whole to the store under its own
name by rsync -- over ssh from the Mac, as a local copy on ned-box, the store
itself being the only difference -- under three rules ruled with the design:

  1. ADD-ONLY. Files are added and never deleted or replaced, so
     dispositions.md, written hours after the reports, joins them on a second
     run and nothing already there is touched. rsync writes each file whole
     or not at all (its default temporary-file-and-rename; --inplace is never
     passed), so a copy interrupted midway is finished by the next run.
  2. REFUSE ON DIFFERENCE. A file already in the store whose content differs
     from the local one is refused before anything is copied: the line names
     the file and prints the provenance comment each report opens with, from
     both copies, and the person renames the local directory with a -2
     suffix and ships again. Two machines reviewing one document on one day
     produce exactly this, and rsync alone would overwrite the first silently.
  3. FAIL LOUDLY. When ned-box cannot be reached the run prints a line
     opening FAILED and exits non-zero; the record stays on disk, unshipped,
     for a later run. ssh runs in batch mode with a connect timeout, so an
     automated caller never waits on a prompt.

The store's directories are created on first use, and a README.md at the
store's root is written when absent -- it says what the store is and that
records dated before 2026-09-08 predate the frozen target -- from the text in
this file.

WHO CALLS IT. scripts/cold-read-grid.py at the end of every run, whatever the
outcome; the agent after writing dispositions.md (the cold-read skill's step
7); scripts/cold-read-fast-read.py when it writes into cold-read-records/.
A shipping failure never fails the cold read: the caller prints this
program's one line and goes on. `--all` ships every directory under
cold-read-records/ in this checkout, continuing past a refused or failed one
and listing them at the end; being add-only it is safe over directories
already in the store, which is how a seat catches up after the box was down,
and how the records that predate the store were shipped once.

OUTPUT. Exactly one line on stdout per record directory -- `shipped:`,
`REFUSED:` or `FAILED:` -- and, under --all, one summary line after them.
Everything else is on stderr. Exit 0 when every directory shipped, 2 when
any was refused and none failed, 1 when any failed, 64 for a bad invocation.

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
import pathlib
import socket
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
RECORDS_DIR = REPO_ROOT / "cold-read-records"
PROGRAM = "cold-read-record-ship"

# The one constant. Host and path in scp form; the path's parent is the
# store's root, where the README lives.
LOG_STORE_RECORDS_DESTINATION = "nedlern@ned-box:/home/nedlern/nedschorus-logs/cold-read-records"
LOG_STORE_HOSTNAME = "ned-box"
DESTINATION_ENVIRONMENT_VARIABLE = "COLD_READ_RECORD_SHIP_DESTINATION"

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

STORE_README = """\
# nedschorus-logs

The log-store: the byproducts of the nedschorus project's work that are not
the system -- good data, never part of the repository (user-ruled
2026-09-07: "separate the system from its logs"). One subdirectory per kind.

- `cold-read-records/` -- one directory per cold-read run, named
  `<date>-<document name>` with `-2`, `-3` for later runs on one day, holding
  the reviewer reports, `dispositions.md` when the agent finished its triage
  (its absence means a triage that never finished, which is true state), and
  `target/<repository path>` with the exact bytes the reviewers read. Records
  dated before 2026-09-08 predate that freeze and hold no `target/`; the
  grid recorded only a hash of the target then.
- `walk/` -- the four files of each walk-me-through walk: draft, suggestions,
  walk, minutes.
- `transcripts/` -- Claude Code session transcripts and handoffs, one
  subdirectory per machine (nedschorus#7).

Cite a file here with its host, in the form scp takes:
`nedlern@ned-box:/home/nedlern/nedschorus-logs/<kind>/<path>`.

Written by scripts/cold-read-record-ship.py in the nedschorus repository when
it found no README here; that program is what puts records in
`cold-read-records/`, add-only, never overwriting a file whose content
differs.
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


def ensure_store(host, records_path: pathlib.PurePosixPath) -> subprocess.CompletedProcess:
    """The records directory exists and the store's root has its README.
    One ssh round trip remotely; plain filesystem calls locally."""
    root = records_path.parent
    if host is None:
        pathlib.Path(records_path).mkdir(parents=True, exist_ok=True)
        readme = pathlib.Path(root) / "README.md"
        if not readme.exists():
            readme.write_text(STORE_README, encoding="utf-8")
        return subprocess.CompletedProcess([], 0, "", "")
    script = (f"mkdir -p -- '{records_path}' && "
              f"{{ test -e '{root}/README.md' || cat > '{root}/README.md'; }}")
    return subprocess.run(SSH_COMMAND + [host, script], input=STORE_README,
                          capture_output=True, text=True, check=False)


def local_inventory(record_dir: pathlib.Path) -> dict:
    """{relative path: sha256} of every file under the record directory."""
    inventory = {}
    for path in sorted(p for p in record_dir.rglob("*") if p.is_file()):
        inventory[path.relative_to(record_dir).as_posix()] = hashlib.sha256(
            path.read_bytes()).hexdigest()
    return inventory


def store_inventory(host, store_dir: pathlib.PurePosixPath):
    """{relative path: sha256} of the store's copy of this record, and the
    process that produced it. An absent directory is an empty inventory with
    exit 0; an unreachable host is ssh's exit 255 and an inventory of None.

    sha256 on both sides -- Python's hashlib here, sha256sum on ned-box -- is
    the digest the grid already records for the target, so a reader can
    compare a record's frozen target with the grid's fingerprint by eye.
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
    citation = f"{host}:{store_dir}" if host else str(store_dir)

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
    if differing:
        for relative in differing:
            local_line = provenance_comment_of(local_first_line(record_dir / relative))
            if host:
                store_line = provenance_comment_of(remote_first_line(host, store_dir / relative))
            else:
                store_line = provenance_comment_of(
                    local_first_line(pathlib.Path(store_dir) / relative))
            print(f"REFUSED: {name} — {relative} is already in the store with different "
                  f"content; store: {store_line}; local: {local_line}. Rename the local "
                  f"directory with a -2 suffix and ship again.")
        return EXIT_REFUSED

    if not new_files:
        print(f"shipped: {name} — nothing new, all files already in {citation}")
        return EXIT_SHIPPED
    transferred = subprocess.run(
        rsync_command(host, record_dir, store_dir, "--ignore-existing"),
        capture_output=True, text=True, check=False)
    if transferred.returncode != 0:
        reason = ("ned-box unreachable" if transferred.returncode == RSYNC_EXIT_CONNECTION_FAILED
                  else f"rsync exit {transferred.returncode}")
        print(f"FAILED: {name} — {reason} during the copy; a later run finishes it.")
        sys.stderr.write(transferred.stderr)
        return EXIT_FAILED
    print(f"shipped: {name} — {len(new_files)} file(s) added to {citation}")
    return EXIT_SHIPPED


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("record_directory", nargs="?",
                        help="one record directory, relative to the repo root or absolute")
    parser.add_argument("--all", action="store_true",
                        help="every directory under cold-read-records/ in this checkout")
    args = parser.parse_args()
    if bool(args.record_directory) == args.all:
        print("FAILED: give one record directory, or --all")
        return EXIT_BAD_INVOCATION

    host, records_path = destination_for_this_machine()

    if not args.all:
        record_dir = pathlib.Path(args.record_directory)
        if not record_dir.is_absolute():
            record_dir = REPO_ROOT / record_dir
        return ship_one(host, records_path, record_dir.resolve())

    directories = sorted(p for p in RECORDS_DIR.glob("*") if p.is_dir()) \
        if RECORDS_DIR.is_dir() else []
    shipped, refused, failed = [], [], []
    for record_dir in directories:
        code = ship_one(host, records_path, record_dir)
        {EXIT_SHIPPED: shipped, EXIT_REFUSED: refused}.get(code, failed).append(record_dir.name)
    print(f"--all: {len(shipped)} shipped, {len(refused)} refused"
          f"{' (' + ', '.join(refused) + ')' if refused else ''}, {len(failed)} failed"
          f"{' (' + ', '.join(failed) + ')' if failed else ''}, of {len(directories)}")
    if failed:
        return EXIT_FAILED
    return EXIT_REFUSED if refused else EXIT_SHIPPED


if __name__ == "__main__":
    sys.exit(main())
