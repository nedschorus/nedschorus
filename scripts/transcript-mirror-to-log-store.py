#!/usr/bin/env python3
"""Mirror this machine's Claude Code transcripts, handoffs, task lists, seat-briefs
and global CLAUDE.md into the log-store on ned-box.

Usage:
  scripts/transcript-mirror-to-log-store.py                   # one pass, one line per source
  scripts/transcript-mirror-to-log-store.py --failures-only   # one pass, only FAILED lines (cron)

WHAT IT MIRRORS AND WHERE (user-ruled 2026-09-07, "I think we should backup
our transcripts to the nedbox"; recorded on nedschorus#7). Five sources under
the home, the SOURCES table: `~/.claude/projects/`, which holds every
session's transcript (`<project-key>/<session-id>.jsonl`) and beside them the
memory store (`<project-key>/memory/`); `~/.claude/handoffs/`;
`~/.claude/tasks/`, each agent-seat's task list (`<list-name>/<task-id>.json`);
the seat-brief of each agent-seat, the `CLAUDE.local.md` at the root of each
directory directly under `~/agents/`, skipping a directory that has none, such
as a worktree; and `~/.claude/CLAUDE.md`, the machine's global instructions.
Git tracks none of these; for the Mac, the store's copy is the only one off
the machine.
They go to the log-store as the third kind of byproduct, one subdirectory per
machine. Under it the layout is that of `~/.claude/`, so a file is found the
same way it is found locally, apart from the seat-briefs, which go to
`seat-briefs/` because `~/.claude/agents/` is Claude Code's own directory of
subagent definitions:

  /home/nedlern/nedschorus-logs/transcripts/mac/projects/<project-key>/<session-id>.jsonl
  /home/nedlern/nedschorus-logs/transcripts/mac/handoffs/<file>
  /home/nedlern/nedschorus-logs/transcripts/mac/tasks/<list-name>/<task-id>.json
  /home/nedlern/nedschorus-logs/transcripts/mac/seat-briefs/<seat>/CLAUDE.local.md
  /home/nedlern/nedschorus-logs/transcripts/mac/CLAUDE.md
  /home/nedlern/nedschorus-logs/transcripts/ned-box/projects/...

`mac` and `ned-box` are the names CLAUDE.md uses for the two machines; this
program tells them apart by hostname. On ned-box the copy is local -- its
transcripts are already on that disk inside Timeshift's coverage, and the
copy makes the store the one place to look for any session from either
machine. A file there is cited with its host in scp form, like everything in
the store: `nedlern@ned-box:/home/nedlern/nedschorus-logs/transcripts/mac/handoffs/<file>`.

HOW. `rsync -a` of each source into its place, over ssh in batch mode with a
connect timeout from the Mac, never `--delete`: a transcript that vanishes
locally stays in the store, and so does the seat-brief of a removed agent-seat.
The seat-briefs and the global CLAUDE.md are single files picked out of a
directory: the program lists them and hands rsync the list on its stdin
(`--files-from=-`), and a source whose list is empty has nothing to mirror.
GNU rsync exits 23, not 24, for a listed file that is gone by the time it
looks, so on ned-box a seat-brief removed in that instant is a FAILED line
for that one run. This is a mirror, not a record -- a live
session's transcript grows between runs and rsync sends the delta -- so the
no-overwrite rule nc-systems/cold-read/cold-read-record-ship.py applies to cold-read
records does not apply here. Two things rsync meets on a live tree are
expected and not failures: files that vanish between its listing and its
transfer (a scratch project directory removed by a session ending; exit 24
from GNU rsync on ned-box) and files that change while being read. The Mac's
openrsync exits 23 for vanished files, and 23 is also its exit for every
other partial transfer, so rsync_vanished_exit_code gives openrsync no
vanished code: on the Mac a file vanishing mid-run is a FAILED line, with
openrsync's stderr, for that one run. A run
that overlaps a slow earlier run -- the first pass moves about a gigabyte --
exits quietly on the lock rather than racing it.

OUTPUT. One line per source on stdout: `mirrored: <source> — local N files,
store M files` (the two counts differ by a file or two while a session runs,
which is why both are printed and neither is asserted; for the seat-briefs
and the global CLAUDE.md both count only the files listed this pass), or a
line opening FAILED naming the source and rsync's exit. Exit 0 when no
source failed, 1 when any failed, 3 when another run holds the lock.

--failures-only prints the FAILED lines and nothing else, and passes rsync's
stderr through only for a source that failed: a mirrored source, a source
with nothing to mirror, files that vanished mid-run and a run held off by the
lock all print nothing. The exits are the same. It is what cron runs, so the log
holds failures only. It also skips the file counts, so a quiet pass makes no
`find` over ssh on ned-box. The lock is silent because a run still going when
the next minute's starts is expected: the first pass after a machine was off
moves everything since. A stalled run does not hold the lock for long:
every ssh it opens, rsync's included, gives up about a minute after ned-box
stops answering (ServerAliveInterval 15, ServerAliveCountMax 4), as when the
Mac sleeps mid-run, and rsync's --timeout ends a transfer that stops moving.
The run then ends and frees the lock, and a directory preparation or rsync
that ended that way prints its FAILED line.

WHEN IT LAST COMPLETED A PASS, SEEN FROM NED-BOX. A run in which every
source mirrored ends by writing the UTC time that pass started, as one line
like `2026-10-03T23:40:12Z`, to MIRROR_PASS_STAMP_FILE_NAME in the store beside
that machine's projects/ and the other copies, writing a `.partial` file and renaming
it over the stamp. The start time, not the end, so that every transcript
written before the stamp's time is in the copy. A run with any FAILED source
leaves the stamp alone, so its time is the last pass that reached the store
whole; so does a run in which no source had anything to mirror, because it
copied nothing and a fresh stamp would make a mirror reading the wrong home look
current. A stamp that cannot be written is itself a FAILED line and exit 1, on
either machine. The backup search on ned-box reads
the Mac's stamp to say how far behind its copy may be, which the lock file
below cannot tell it, because that file is on the Mac.

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
import shlex
import socket
import subprocess
import sys
import time

PROGRAM = "transcript-mirror-to-log-store"

LOG_STORE_TRANSCRIPTS_DESTINATION = "nedlern@ned-box:/home/nedlern/nedschorus-logs/transcripts"
LOG_STORE_HOSTNAME = "ned-box"
MACHINE_NAME_ON_STORE_HOST = "ned-box"
MACHINE_NAME_ELSEWHERE = "mac"
DESTINATION_ENVIRONMENT_VARIABLE = "TRANSCRIPT_MIRROR_DESTINATION"
SOURCE_HOME_ENVIRONMENT_VARIABLE = "TRANSCRIPT_MIRROR_SOURCE_HOME"

SEAT_BRIEF_FILE_NAME = "CLAUDE.local.md"
GLOBAL_INSTRUCTIONS_FILE_NAME = "CLAUDE.md"


def seat_briefs_in(agents: pathlib.Path) -> list:
    """Return `<seat>/CLAUDE.local.md` for each directory directly under ~/agents that has one."""
    return sorted(f"{agent_home.name}/{SEAT_BRIEF_FILE_NAME}" for agent_home in agents.iterdir()
                  if (agent_home / SEAT_BRIEF_FILE_NAME).is_file())


def global_instructions_in(dot_claude: pathlib.Path) -> list:
    return [GLOBAL_INSTRUCTIONS_FILE_NAME] if (dot_claude / GLOBAL_INSTRUCTIONS_FILE_NAME).is_file() else []


# Name printed, source directory relative to the home, store directory relative
# to the machine's copy, and the files to take: None for the whole tree, or a
# function returning paths relative to the source directory.
SOURCES = (
    ("projects", pathlib.Path(".claude") / "projects", "projects", None),
    ("handoffs", pathlib.Path(".claude") / "handoffs", "handoffs", None),
    ("tasks", pathlib.Path(".claude") / "tasks", "tasks", None),
    ("seat-briefs", pathlib.Path("agents"), "seat-briefs", seat_briefs_in),
    (GLOBAL_INSTRUCTIONS_FILE_NAME, pathlib.Path(".claude"), ".", global_instructions_in),
)
# mirror_one's outcome for a source that is absent or has no files to take.
NOTHING_TO_MIRROR = "nothing to mirror"

# Bound dead SSH sessions so a sleeping Mac cannot hold the mirror lock indefinitely.
SSH_COMMAND = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
               "-o", "ServerAliveInterval=15", "-o", "ServerAliveCountMax=4"]
RSYNC_IO_TIMEOUT_SECONDS = "300"
# Vanishing files are expected in a live transcript tree.
RSYNC_EXIT_VANISHED_GNU = 24
LOCK_FILE_NAME = ".transcript-mirror.lock"
# The backup search on ned-box reads this file beside the Mac copy's projects/.
MIRROR_PASS_STAMP_FILE_NAME = "last-complete-mirror-pass-utc.txt"

EXIT_MIRRORED = 0
EXIT_FAILED = 1
EXIT_LOCKED = 3


@functools.lru_cache(maxsize=None)
def rsync_vanished_exit_code():
    """Return the installed rsync's exit code that means only that source files vanished, or None for openrsync."""
    # openrsync's 23 means vanished files and every other partial transfer alike.
    completed = subprocess.run(["rsync", "--version"], capture_output=True, text=True, check=False)
    first_line = completed.stdout.partition("\n")[0]
    return None if first_line.startswith("openrsync") else RSYNC_EXIT_VANISHED_GNU


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


def rsync_command(host, source: pathlib.Path, target: pathlib.PurePosixPath,
                  files_on_stdin: bool = False) -> list:
    # Never use --delete: transcripts removed locally must remain in the store.
    destination = f"{host}:{target}/" if host else f"{target}/"
    command = ["rsync", "-a", "--timeout", RSYNC_IO_TIMEOUT_SECONDS]
    if files_on_stdin:
        command += ["--files-from=-"]
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
    if path.is_file():
        return 1
    return sum(1 for p in path.rglob("*") if p.is_file()) if path.is_dir() else 0


def count_files_in_store(host, path: pathlib.PurePosixPath, files=None):
    """Return the file count under path, or of the listed files in it; None if the store could not be queried."""
    paths = [path] if files is None else [path / file for file in files]
    if host is None:
        return sum(count_files_local(pathlib.Path(p)) for p in paths)
    # Without pipefail a failed find still counts what it found, and the pipe exits 0.
    completed = subprocess.run(
        SSH_COMMAND + [host, f"set -o pipefail; "
                             f"find {' '.join(shlex.quote(str(p)) for p in paths)} -type f | wc -l"],
        capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        sys.stderr.write(completed.stderr)
        return None
    try:
        return int(completed.stdout.strip())
    except ValueError:
        return None


def mirror_one(host, target: pathlib.PurePosixPath, name: str, source: pathlib.Path,
               select=None, failures_only: bool = False):
    """Mirror one source; return EXIT_MIRRORED, EXIT_FAILED or NOTHING_TO_MIRROR."""
    if not source.is_dir():
        if not failures_only:
            print(f"mirrored: {name} — nothing to mirror, {source} is not a directory")
        return NOTHING_TO_MIRROR
    files = None if select is None else select(source)
    if files == []:
        if not failures_only:
            print(f"mirrored: {name} — nothing to mirror, none found in {source}")
        return NOTHING_TO_MIRROR
    prepared = ensure_directory(host, target)
    if prepared.returncode != 0:
        print(f"FAILED: {name} — could not prepare {host or ''}:{target} (exit {prepared.returncode})")
        sys.stderr.write(prepared.stderr)
        return EXIT_FAILED
    # The file list goes on rsync's stdin (--files-from=-); a whole tree gets an empty stdin.
    completed = subprocess.run(rsync_command(host, source, target, files is not None),
                               input="".join(f"{file}\n" for file in files or ()),
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
    in_store = count_files_in_store(host, target, files)
    local = count_files_local(source) if files is None else len(files)
    print(f"mirrored: {name} — local {local} files, store "
          f"{'unknown' if in_store is None else in_store} files{note}")
    return EXIT_MIRRORED


def write_mirror_pass_stamp(host, machine_path: pathlib.PurePosixPath,
                            pass_started_at: time.struct_time) -> int:
    """Record in the store the UTC start time of a pass in which every source mirrored."""
    # Write then rename, so a reader never sees a half-written time.
    stamp_text = time.strftime("%Y-%m-%dT%H:%M:%SZ", pass_started_at) + "\n"
    stamp = machine_path / MIRROR_PASS_STAMP_FILE_NAME
    partial = machine_path / (MIRROR_PASS_STAMP_FILE_NAME + ".partial")
    if host is None:
        try:
            pathlib.Path(machine_path).mkdir(parents=True, exist_ok=True)
            pathlib.Path(partial).write_text(stamp_text)
            os.replace(partial, stamp)
        except OSError as error:
            print(f"FAILED: pass-time stamp — could not write {stamp} ({error})")
            return EXIT_FAILED
        return EXIT_MIRRORED
    completed = subprocess.run(
        SSH_COMMAND + [host, f"mkdir -p -- {shlex.quote(str(machine_path))} && "
                             f"printf %s {shlex.quote(stamp_text)} > {shlex.quote(str(partial))} && "
                             f"mv -f -- {shlex.quote(str(partial))} {shlex.quote(str(stamp))}"],
        capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        print(f"FAILED: pass-time stamp — could not write {host}:{stamp} (exit {completed.returncode})")
        sys.stderr.write(completed.stderr)
        return EXIT_FAILED
    return EXIT_MIRRORED


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Mirror this machine's Claude Code transcripts, handoffs, task lists, "
                    "seat-briefs and global CLAUDE.md into the log-store.")
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
        pass_started_at = time.gmtime()
        outcomes = [mirror_one(host, machine_path / store_directory, name, home / relative,
                               select, failures_only)
                    for name, relative, store_directory, select in SOURCES]
        if EXIT_FAILED not in outcomes and any(o != NOTHING_TO_MIRROR for o in outcomes):
            outcomes.append(write_mirror_pass_stamp(host, machine_path, pass_started_at))
    return EXIT_FAILED if EXIT_FAILED in outcomes else EXIT_MIRRORED


if __name__ == "__main__":
    sys.exit(main())
