#!/usr/bin/env python3
"""Mirror this machine's Claude Code transcripts and handoffs into the log-store on ned-box.

Usage:
  scripts/transcript-mirror-to-log-store.py                   # one pass, one line per source
  scripts/transcript-mirror-to-log-store.py --failures-only   # one pass, only FAILED lines (cron)

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
no-overwrite rule nc-systems/cold-read/cold-read-record-ship.py applies to cold-read
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

--failures-only prints the FAILED lines and nothing else, and passes rsync's
stderr through only for a source that failed: a mirrored source, a missing
source directory, files that vanished mid-run and a run held off by the lock
all print nothing. The exits are the same. It is what cron runs, so the log
holds failures only. It also skips the file counts, so a quiet pass makes no
`find` over ssh on ned-box. The lock is silent because a run still going when
the next minute's starts is expected: the first pass after a machine was off
moves everything since. A stalled run does not hold the lock for long:
every ssh it opens, rsync's included, gives up about a minute after ned-box
stops answering (ServerAliveInterval 15, ServerAliveCountMax 4), as when the
Mac sleeps mid-run, and rsync's --timeout ends a transfer that stops moving.
The run then ends and frees the lock, and a directory preparation or rsync
that ended that way prints its FAILED line. One gap: openrsync's exit 23 is
taken as files vanishing, so on the Mac any other partial transfer openrsync
reports with 23 is silent too, its stderr dropped with the rest. The Mac's
hourly log held no exit-23 run and no line from openrsync in 461 runs
(measured 2026-09-30), so there is no sample to tell the two apart by their
text.

WHEN IT LAST RAN. The log cannot say: a healthy quiet run appends nothing.
Every run rewrites the lock file, `~/.claude/.transcript-mirror.lock`
(LOCK_FILE_NAME, opened for writing), as it starts, so its mtime is when
cron last started the mirror on that machine: `stat -f %Sm
~/.claude/.transcript-mirror.lock` on the Mac, `stat -c %y
~/.claude/.transcript-mirror.lock` on ned-box. A time more than a few
minutes old means cron has not started it since: the machine was off or
asleep, or its cron line is gone. A run that started and failed also left a
FAILED line in the log. The newest file in the store's copy is
not a run clock: rsync -a keeps each file's own mtime, so it says when a
transcript was last written, which can be hours ago on a healthy mirror while
no session runs. Measured 2026-09-30 at 18:24Z: both lock files had been
rewritten that minute, and both logs still dated from 17:17Z.

SCHEDULE. Every minute, by cron on both machines, so the store's copy of each
machine's transcripts is at most about a minute behind (user-ruled
2026-09-30; hourly before). A pass that finds little changed is cheap:
measured on the Mac on 2026-09-30, a dry run over projects/ (4,421 files,
3.3 GB, 12 changed) took 0.8 s, and over handoffs/ 0.7 s. Cron, not launchd
on the Mac: the project's escaped-bug dataset records that launchd never
fires StartInterval jobs on this Mac
(docs/working/research/escaped-bug-dataset-2026-07.md in the legacy
repository; com.nedlern.agent-ping was the casualty). Each machine runs its
own `python3`: the Mac's Homebrew link and ned-box's system one. The lines,
run from each machine's reference checkout, which the stop hook keeps on
main, are installed by
nc-systems/general-tools/install-scheduled-jobs-on-this-machine.py from the
table beside that program, which is where a change to them is made:

  Mac:     * * * * * /opt/homebrew/bin/python3 /Users/el/Projects/nedschorus/scripts/transcript-mirror-to-log-store.py --failures-only >> /Users/el/.claude/transcript-mirror.log 2>&1
  ned-box: * * * * * /usr/bin/python3 /home/nedlern/Projects/nedschorus/scripts/transcript-mirror-to-log-store.py --failures-only >> /home/nedlern/.claude/transcript-mirror.log 2>&1

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

import argparse
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

# Store name and path relative to the source home.
SOURCES = (
    ("projects", pathlib.Path(".claude") / "projects"),
    ("handoffs", pathlib.Path(".claude") / "handoffs"),
)

# Bound dead SSH sessions so a sleeping Mac cannot hold the mirror lock indefinitely.
SSH_COMMAND = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
               "-o", "ServerAliveInterval=15", "-o", "ServerAliveCountMax=4"]
RSYNC_IO_TIMEOUT_SECONDS = "300"
# Vanishing files are expected in a live transcript tree.
RSYNC_EXIT_VANISHED_GNU = 24
RSYNC_EXIT_VANISHED_OPENRSYNC = 23
LOCK_FILE_NAME = ".transcript-mirror.lock"

EXIT_MIRRORED = 0
EXIT_FAILED = 1
EXIT_LOCKED = 3


@functools.lru_cache(maxsize=None)
def rsync_vanished_exit_code() -> int:
    """Return the installed rsync’s exit code for vanished source files."""
    # GNU uses 24; openrsync uses 23, which can also hide other partial-transfer errors.
    completed = subprocess.run(["rsync", "--version"], capture_output=True, text=True, check=False)
    first_line = completed.stdout.partition("\n")[0]
    return RSYNC_EXIT_VANISHED_OPENRSYNC if first_line.startswith("openrsync") else RSYNC_EXIT_VANISHED_GNU


def split_destination(destination: str):
    """Return (host, path) from an scp destination; host is None for local paths."""
    head = destination.split("/", 1)[0]
    if ":" in head:
        host, _, rest = destination.partition(":")
        return host, pathlib.PurePosixPath(rest)
    return None, pathlib.PurePosixPath(destination)


def this_machine_name() -> str:
    hostname = socket.gethostname().split(".")[0]
    return MACHINE_NAME_ON_STORE_HOST if hostname == LOG_STORE_HOSTNAME else MACHINE_NAME_ELSEWHERE


def destination_for_this_machine():
    """Return (host, machine-specific store path); host is None for a local copy."""
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
    # Never use --delete: transcripts removed locally must remain in the store.
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
    """Return the file count, or None if the store could not be queried."""
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


def mirror_one(host, machine_path: pathlib.PurePosixPath, name: str, source: pathlib.Path,
               failures_only: bool = False) -> int:
    if not source.is_dir():
        if not failures_only:
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
    vanished = rsync_vanished_exit_code()
    if completed.returncode not in (0, vanished):
        sys.stderr.write(completed.stderr)
        print(f"FAILED: {name} — rsync exit {completed.returncode}"
              f"{' (ned-box unreachable)' if completed.returncode == 255 else ''}")
        return EXIT_FAILED
    if failures_only:
        return EXIT_MIRRORED
    sys.stderr.write(completed.stderr)
    note = " (some files vanished mid-run: a session ended)" \
        if completed.returncode == vanished else ""
    in_store = count_files_in_store(host, target)
    print(f"mirrored: {name} — local {count_files_local(source)} files, store "
          f"{'unknown' if in_store is None else in_store} files{note}")
    return EXIT_MIRRORED


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Mirror this machine's Claude Code transcripts and handoffs into the log-store.")
    parser.add_argument("--failures-only", action="store_true",
                        help="print FAILED lines only, for cron")
    failures_only = parser.parse_args(argv).failures_only
    home = source_home()
    lock_path = home / ".claude" / LOCK_FILE_NAME
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            if not failures_only:
                print(f"{PROGRAM}: another run holds {lock_path}; leaving it to finish")
            return EXIT_LOCKED
        host, machine_path = destination_for_this_machine()
        outcomes = [mirror_one(host, machine_path, name, home / relative, failures_only)
                    for name, relative in SOURCES]
    return EXIT_FAILED if EXIT_FAILED in outcomes else EXIT_MIRRORED


if __name__ == "__main__":
    sys.exit(main())
