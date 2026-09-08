#!/usr/bin/env python3
"""Mirror this machine's Claude Code transcripts and handoffs into the log-store on ned-box.

Usage:
  scripts/transcript-mirror-to-log-store.py          # one pass, one line per source

WHAT IT MIRRORS AND WHERE (user-ruled 2026-09-07, "I think we should backup
our transcripts to the nedbox"; recorded on nedschorus#7). Two directories
under the home: `~/.claude/projects/`, which holds every session's transcript
(`<project-key>/<session-id>.jsonl`) and beside them the memory store
(`<project-key>/memory/`), and `~/.claude/handoffs/`. They go to the
log-store as the third kind of byproduct, one subdirectory per machine,
keeping Claude Code's own layout underneath so a transcript is found the same
way it is found locally:

  /home/nedlern/nedschorus-logs/transcripts/mac/projects/<project-key>/<session-id>.jsonl
  /home/nedlern/nedschorus-logs/transcripts/mac/handoffs/<file>
  /home/nedlern/nedschorus-logs/transcripts/ned-box/projects/...

`mac` and `ned-box` are the names CLAUDE.md uses for the two machines; this
program tells them apart by hostname. On ned-box the copy is local -- its
transcripts are already on that disk inside Timeshift's coverage, and the
copy makes the store the one place to look for any session from either
machine. A file there is cited with its host in scp form, like everything in
the store: `nedlern@ned-box:/home/nedlern/nedschorus-logs/transcripts/mac/handoffs/<file>`.

HOW. `rsync -a` of each source into its place, over ssh in batch mode with a
connect timeout from the Mac, never `--delete`: a transcript that vanishes
locally stays in the store. This is a mirror, not a record -- a live
session's transcript grows between runs and rsync sends the delta -- so the
no-overwrite rule scripts/cold-read-record-ship.py applies to cold-read
records does not apply here. Two things rsync meets on a live tree are
expected and not failures: files that vanish between its listing and its
transfer (a scratch project directory removed by a session ending; exit 24
from GNU rsync on ned-box, exit 23 from the Mac's openrsync -- told apart by
rsync_vanished_exit_code) and files that change while being read. A run
that overlaps a slow earlier run -- the first pass moves about a gigabyte --
exits quietly on the lock rather than racing it.

OUTPUT. One line per source on stdout: `mirrored: <source> — local N files,
store M files` (the two counts differ by a file or two while a session runs,
which is why both are printed and neither is asserted), or a line opening
FAILED naming the source and rsync's exit. Exit 0 when every source mirrored,
1 when any failed, 3 when another run holds the lock.

SCHEDULE. Hourly, by cron on both machines -- not launchd on the Mac: the
project's escaped-bug dataset records that launchd never fires StartInterval
jobs on this Mac (docs/working/research/escaped-bug-dataset-2026-07.md in
the legacy repository; com.nedlern.agent-ping was the casualty). The lines,
run from each machine's reference checkout, which the stop hook keeps on
main:

  Mac:     17 * * * * /opt/homebrew/opt/python@3.13/libexec/bin/python3 /Users/el/Projects/nedschorus/scripts/transcript-mirror-to-log-store.py >> /Users/el/.claude/transcript-mirror.log 2>&1
  ned-box: 17 * * * * /usr/bin/python3 /home/nedlern/Projects/nedschorus/scripts/transcript-mirror-to-log-store.py >> /home/nedlern/.claude/transcript-mirror.log 2>&1

Cron's environment has no ssh agent; the Mac's key to ned-box carries no
passphrase, checked 2026-09-07 with `env -i HOME=/Users/el PATH=/usr/bin:/bin
ssh -o BatchMode=yes nedlern@ned-box true`.

THE DESTINATION IS ONE CONSTANT, LOG_STORE_TRANSCRIPTS_DESTINATION, the same
shape as the record shipper's; TRANSCRIPT_MIRROR_DESTINATION in the
environment overrides it for the tests, which point it at a scratch
directory (local mode, real rsync) or at the real string with stub rsync and
ssh on PATH (remote mode). TRANSCRIPT_MIRROR_SOURCE_HOME overrides the home
directory the sources are read from, for the same tests.
"""

import fcntl
import functools
import os
import pathlib
import socket
import subprocess
import sys

PROGRAM = "transcript-mirror-to-log-store"

LOG_STORE_TRANSCRIPTS_DESTINATION = "nedlern@ned-box:/home/nedlern/nedschorus-logs/transcripts"
LOG_STORE_HOSTNAME = "ned-box"
MACHINE_NAME_ON_STORE_HOST = "ned-box"
MACHINE_NAME_ELSEWHERE = "mac"
DESTINATION_ENVIRONMENT_VARIABLE = "TRANSCRIPT_MIRROR_DESTINATION"
SOURCE_HOME_ENVIRONMENT_VARIABLE = "TRANSCRIPT_MIRROR_SOURCE_HOME"

# (name in the store, path under the home) -- the store keeps the name.
SOURCES = (
    ("projects", pathlib.Path(".claude") / "projects"),
    ("handoffs", pathlib.Path(".claude") / "handoffs"),
)

SSH_COMMAND = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10"]
RSYNC_IO_TIMEOUT_SECONDS = "300"
# rsync: some source files vanished before they could be transferred. On a
# live tree that is a session ending, not a failure. The code depends on
# which rsync is on PATH; see rsync_vanished_exit_code.
RSYNC_EXIT_VANISHED_GNU = 24
RSYNC_EXIT_VANISHED_OPENRSYNC = 23
LOCK_FILE_NAME = ".transcript-mirror.lock"

EXIT_MIRRORED = 0
EXIT_FAILED = 1
EXIT_LOCKED = 3


@functools.lru_cache(maxsize=None)
def rsync_vanished_exit_code() -> int:
    """The exit the rsync on PATH gives when source files vanished mid-run:
    23 for openrsync, 24 for GNU rsync. Detected once per run from the first
    line of `rsync --version`, which opens "openrsync" on the Mac's
    /usr/bin/rsync and "rsync  version 3.4.1" on ned-box.

    Measured 2026-09-08 with a 4,000-file tree, 500 files deleted while rsync
    ran: exit 23 on the Mac (openrsync, stderr "open (2)" errors, everything
    else copied) and exit 24 on ned-box (rsync 3.4.1, "file has vanished").
    GNU's 23 is a genuine partial-transfer error and openrsync's 24 is not
    the vanished case, so each implementation gets exactly its own code.
    openrsync propagates ssh's 255 correctly; a transcript appended during
    transfer is exit 0 on both."""
    completed = subprocess.run(["rsync", "--version"], capture_output=True, text=True, check=False)
    first_line = completed.stdout.partition("\n")[0]
    return RSYNC_EXIT_VANISHED_OPENRSYNC if first_line.startswith("openrsync") else RSYNC_EXIT_VANISHED_GNU


def split_destination(destination: str):
    """(host, path) from an scp-form destination; host is None for a local path."""
    head = destination.split("/", 1)[0]
    if ":" in head:
        host, _, rest = destination.partition(":")
        return host, pathlib.PurePosixPath(rest)
    return None, pathlib.PurePosixPath(destination)


def this_machine_name() -> str:
    hostname = socket.gethostname().split(".")[0]
    return MACHINE_NAME_ON_STORE_HOST if hostname == LOG_STORE_HOSTNAME else MACHINE_NAME_ELSEWHERE


def destination_for_this_machine():
    """(host, transcripts path/<machine>): the override, else the constant,
    which on ned-box itself is the same path with no host."""
    override = os.environ.get(DESTINATION_ENVIRONMENT_VARIABLE)
    if override:
        host, path = split_destination(override)
    else:
        host, path = split_destination(LOG_STORE_TRANSCRIPTS_DESTINATION)
        if this_machine_name() == MACHINE_NAME_ON_STORE_HOST:
            host = None
    return host, path / this_machine_name()


def source_home() -> pathlib.Path:
    return pathlib.Path(os.environ.get(SOURCE_HOME_ENVIRONMENT_VARIABLE) or pathlib.Path.home())


def rsync_command(host, source: pathlib.Path, target: pathlib.PurePosixPath) -> list:
    """-a and never --delete: see the docstring."""
    destination = f"{host}:{target}/" if host else f"{target}/"
    command = ["rsync", "-a", "--timeout", RSYNC_IO_TIMEOUT_SECONDS]
    if host:
        command += ["-e", " ".join(SSH_COMMAND)]
    return command + [f"{source}/", destination]


def ensure_directory(host, path: pathlib.PurePosixPath) -> subprocess.CompletedProcess:
    if host is None:
        pathlib.Path(path).mkdir(parents=True, exist_ok=True)
        return subprocess.CompletedProcess([], 0, "", "")
    return subprocess.run(SSH_COMMAND + [host, f"mkdir -p -- '{path}'"],
                          capture_output=True, text=True, check=False)


def count_files_local(path: pathlib.Path) -> int:
    return sum(1 for p in path.rglob("*") if p.is_file()) if path.is_dir() else 0


def count_files_in_store(host, path: pathlib.PurePosixPath):
    """The store's file count under path, or None when it could not be asked."""
    if host is None:
        return count_files_local(pathlib.Path(path))
    completed = subprocess.run(
        SSH_COMMAND + [host, f"find '{path}' -type f | wc -l"],
        capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        return None
    try:
        return int(completed.stdout.strip())
    except ValueError:
        return None


def mirror_one(host, machine_path: pathlib.PurePosixPath, name: str, source: pathlib.Path) -> int:
    if not source.is_dir():
        print(f"mirrored: {name} — nothing to mirror, {source} is not a directory")
        return EXIT_MIRRORED
    target = machine_path / name
    prepared = ensure_directory(host, target)
    if prepared.returncode != 0:
        print(f"FAILED: {name} — could not prepare {host or ''}:{target} (exit {prepared.returncode})")
        sys.stderr.write(prepared.stderr)
        return EXIT_FAILED
    completed = subprocess.run(rsync_command(host, source, target),
                               capture_output=True, text=True, check=False)
    sys.stderr.write(completed.stderr)
    vanished = rsync_vanished_exit_code()
    if completed.returncode not in (0, vanished):
        print(f"FAILED: {name} — rsync exit {completed.returncode}"
              f"{' (ned-box unreachable)' if completed.returncode == 255 else ''}")
        return EXIT_FAILED
    note = " (some files vanished mid-run: a session ended)" \
        if completed.returncode == vanished else ""
    in_store = count_files_in_store(host, target)
    print(f"mirrored: {name} — local {count_files_local(source)} files, store "
          f"{'unknown' if in_store is None else in_store} files{note}")
    return EXIT_MIRRORED


def main() -> int:
    home = source_home()
    lock_path = home / ".claude" / LOCK_FILE_NAME
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            print(f"{PROGRAM}: another run holds {lock_path}; leaving it to finish")
            return EXIT_LOCKED
        host, machine_path = destination_for_this_machine()
        outcomes = [mirror_one(host, machine_path, name, home / relative)
                    for name, relative in SOURCES]
    return EXIT_FAILED if EXIT_FAILED in outcomes else EXIT_MIRRORED


if __name__ == "__main__":
    sys.exit(main())
