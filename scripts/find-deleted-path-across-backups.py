#!/usr/bin/env python3
"""Find a file that is no longer on disk, across every history this fleet keeps.

WHY THIS EXISTS. On 2026-08-23 an agent followed a citation in nedschorus#46 to
`md-review-records/2026-08-11-ghi-info-agent-design/dispositions.md`, found
nothing, and built the ghi-info tool without the eleven deferred findings that
file held. The path had been deleted on 2026-08-14 (commit ab541cc) when review
records were retired. The content was never actually lost: it was in git, in the
predecessor's own session transcript, in Timeshift on the box, and in Time
Machine on the Mac. The failure was not that the agent forgot to look — it
reached for git reflexively — but that it did not know three of the four
surfaces existed. This script means no future agent has to know: it searches
every one of them and says plainly which it could not search, and why.

THE SEVEN SURFACES, in the order they are searched:

  1. local
     snapshots    — the hourly Time Machine snapshots macOS keeps on this Mac's
                    OWN INTERNAL disk, present whether or not the backup disk is
                    attached. Mounting one read-only NEEDS NO PASSWORD (measured
                    2026-08-31: `mount_apfs -o ro -s <snapshot>
                    /System/Volumes/Data <dir>` and `diskutil unmount <dir>`
                    both succeed as the ordinary user, in about 7 ms and 10 ms;
                    plain `umount` does NOT reliably release a snapshot, see
                    _local_snapshot_probe for what that cost). It is
                    searched first because it is the cheapest surface and the
                    only unprivileged one that keeps a point-in-time copy of the
                    working tree. Its memory is SHORT — macOS retains roughly a
                    day (measured 2026-08-23: 24 snapshots, 15 of them from that
                    day; re-measured 2026-08-31: 18) — so it is the right first
                    place to look for something lost minutes or hours ago and no
                    substitute at all for the archive surfaces below. macOS
                    mounts some of these for itself — the newest one especially,
                    which is the one this case needs — and those are read where
                    they already sit, because a snapshot that is already mounted
                    cannot be mounted again.
  2. git          — every ref in this repo, full history, including paths that
                    no commit reachable from HEAD still contains.
  3. git reflog   — the commits no branch or tag reaches any more, which only
                    a reflog still names: what a recreated branch, a reset or a
                    rebase left behind. Surface 2 walks refs and cannot see
                    them. git prunes these reflog entries after 30 days by
                    default, so this surface's memory is about a month.
  4. log-store    — every file name under /home/nedlern/nedschorus-logs on the
                    box, where seats ship what git does not carry. FOUND only
                    for a file whose path ends with the path asked for, the
                    rule git's surface uses; any other file whose name
                    contains the file's stem, the same name in another
                    directory included, is listed as a CANDIDATE, because a
                    copy is usually renamed on its way in, but not counted.
                    Read in place on the box; one ssh call from the Mac.
  5. transcripts  — agent session JSONL under ~/.claude/projects, on this Mac
                    AND on the box. A file's content often survives in the
                    transcript of the session that wrote or read it, even when
                    every copy on disk is gone. Run on the box, it greps the
                    box's own and the log-store's copy of the Mac's.
  6. Timeshift    — snapshots on ned-box at /mnt/backup/timeshift/snapshots.
                    Ordinary world-readable directories: no privilege needed.
                    Searched over ssh from the Mac, in place on the box.
  7. Time Machine — snapshots on the Mac's EXTERNAL backup disk. Enumerating
                    them needs no privilege; READING INSIDE ONE NEEDS ROOT
                    (measured 2026-08-23: `sudo mount_apfs -o ro` refused
                    without a password). The difference from surface 1 is the
                    VOLUME, not the command: the same mount_apfs runs
                    unprivileged against this Mac's internal Data volume and
                    needs a password against the external backup volume. A
                    reader who generalises either way gets it wrong. It is ONE
                    operation, which is what makes that wall crossable at all —
                    see CROSSING THE ROOT WALL below.

WHY SURFACES 3 AND 4, AND WHY EACH SURFACE PRINTS AS IT FINISHES. Both were
added on 2026-09-23 after the lost-file research
(nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/merge-lane/lost-file-research-report-2026-09-23.md,
episodes E11 and E14). Two seats, three days apart, could not find
docs/drafts/pr-main-process-design.md. It was in commits 12c18b5 and 28e4f5f,
which only the merge-lane worktree's HEAD reflog still named after its seat
branch was recreated, and in the log-store under two renamed copies. This
script searched neither place. Its two runs for that file also printed
nothing useful in time: `timeout 280` killed one at 283 s with no output at
all, because the whole report was printed only after the last surface
answered, and a process killed by a signal loses whatever its pipe buffer
held. The other took 533 s, 480 of them in Time Machine timeouts, and found
nothing. So the header and each surface's section are now printed and
flushed the moment that surface answers, and only the summary waits for the
end. A run that completes prints exactly the text render() composes, as one
print at the end did; a run that is killed keeps every surface that had
already answered.

WHY SURFACE 1 IS NOT REDUNDANT WITH SURFACE 7, measured 2026-08-31.
`tmutil isexcluded /private/tmp/claude-501` reports [Excluded], so the external
backup disk holds NOTHING under the scratchpad directory every agent in this
fleet is told to write its intermediate work to. The local snapshots do hold it,
because they are whole-volume and /private/tmp sits on the same Data volume as
the home directory. That day ten files were reaped from a worktree under it,
this script reported Time Machine UNAVAILABLE, and every one of them came back
out of the 11:51 local snapshot with no password typed.

THE HONESTY CONTRACT. Every surface reports one of three outcomes, and never
conflates the second with the third:

  FOUND        — with the exact command that recovers the content.
  NOT FOUND    — this surface was genuinely searched and does not have it.
  UNAVAILABLE  — this surface could NOT be searched, with the reason and the
                 command that would fix it.

A surface that cannot be read must never render as "not found". That distinction
is the whole point: an agent told "not in Time Machine" stops looking, and an
agent told "Time Machine needs your password, here is the command" asks for it.

READ-ONLY BY CONSTRUCTION. This script only lists and reads; the copying is
left to the recovery commands it prints. It never writes backup state, which
agents are forbidden to do (.claude/hooks/backup-and-snapshot-write-guard.py
holds the tool path; the rule binds shell commands too). Two calls it makes
change mount state and nothing else. `diskutil mount` on the Time Machine
destination mounts a disk the user already attached, which is how you read a
backup, not a modification of one; it is attempted only when the destination is
attached but unmounted, because the user's disk does go offline and a script
that gives up there is useless to him (user-ruled 2026-08-23). `mount_apfs -o
ro` on a local snapshot opens it READ-ONLY, which is reading a snapshot rather
than modifying one, and every snapshot this script opens is unmounted again in
a `finally` — including when the search inside it fails.

CROSSING THE ROOT WALL, WITH NOBODY IN THE ROOM. The whole of surface 7's
privilege is that one mount_apfs against the external backup volume. Two things
make it crossable, and they only work together.

  * A FIXED MOUNT POINT. Every Time Machine mount this file makes, and every
    Time Machine recovery command it prints, names
    TIME_MACHINE_READONLY_MOUNT_POINT and no other directory. That is what lets
    the sudoers rule shipped beside this script —
    config/sudoers-mount-apfs-readonly-for-backup-recovery — be tight enough to
    be worth installing: it grants one binary, the read-only flag, and that one
    path. A command naming any other directory does not match the rule and is
    asked for a password anyway, so the mount point is not cosmetic and must
    not be varied. The rule is NOT installed by anything here — writing
    /etc/sudoers.d is root's work and therefore the user's. With it installed
    the mount simply succeeds and nobody is asked anything; without it every
    behaviour described here is exactly what it was before.
  * The script's own root-prompt flag, off by default. Without it the script
    prints the resolved sudo command and carries on, which is what an
    unattended run needs. With it the script runs that command itself, so sudo
    asks in the terminal the person is already sitting at. It exists on the
    script alone and must never be handed to a hook: a hook has no terminal,
    and a password prompt with no terminal behind it can only hang until
    something kills it.

WHEN A HUMAN REALLY IS NEEDED, THIS MAC SAYS SO OUT LOUD. On 2026-08-31 this
script reported that Time Machine "needs your password"; the agent reading that
relayed it four paragraphs into a long message, and the user never saw it. The
channel worked exactly as built and still failed him. So a run that hits the
wall also speaks one short sentence through macOS `say`, which is the one
channel here that does not depend on an agent choosing to pass anything on. It
is gated hard so that it stays rare: speech_line_when_root_password_is_needed
holds the four conditions and what each of them is protecting against.

NO HARDCODED DEVICE NODES. `/dev/disk5s2` was the backup volume on 2026-08-23;
device numbers reshuffle across replugs. Everything resolves at runtime from the
destination name that `tmutil destinationinfo` reports. The local-snapshot
surface names no device at all: mount_apfs takes the Data volume's fixed mount
point, /System/Volumes/Data, directly as its source, so there is nothing to
resolve and nothing to go stale.

EVERY COMMAND THIS PROGRAM STARTS runs without the variables that point git at
another repository, so `git -C <repo>` answers for the repository it names.
`-C` changes git's directory, not its repository: a caller's GIT_DIR or
GIT_COMMON_DIR still wins over it. Reproduced by merge-lane-2 on 2026-09-30 in
a scratch fixture: with GIT_COMMON_DIR naming another clone, the git and
reflog surfaces went UNAVAILABLE with "bad object", and a file git could
recover exited 3 instead of 0. The locator has dropped the same variables from
every git it runs since PR "Every git the locator runs ignores a caller's
GIT_COMMON_DIR", and from this program when it starts it since PR "The
locator runs the backup search itself when it finds nothing"; this covers a
run by hand. User-ruled 2026-09-30 in merge-lane-2's session, under the
2026-09-29 walk item 17 ruling, "If we are going to use it, it should work
properly." The variables and the function that drops them are the locator's,
used through the same import as its host rule: the locator keeps its own copy
of that function only because it is sent whole to the other machine over ssh,
and this program never is.

The git recovery command it prints is run later in its caller's shell, where
those variables may still be set, so it is printed as `env -u GIT_DIR ...
git -C <repo> show <commit>:<path>`, unsetting the same variables itself.
The prefix is the locator's PRINTED_GIT_INVOCATION_WITHOUT_REDIRECTING_VARIABLES,
so the two programs print one form.
Printed as a bare `git -C`, under a caller's GIT_COMMON_DIR or GIT_DIR it
exited 128 instead of printing the file: Codex's review cell on PR "The
backup search's commands ignore a caller's git redirect variables", fixed
on the user's "y" in walk merge-lane-mac-helper-open-decisions-2026-09-30.

RUN ON NED-BOX ITSELF, the box's two surfaces are searched in place. Until
2026-09-30 every run reached "the box" by `ssh nedlern@ned-box`, from the box
too, where that ssh fails before logging in ("Host key verification failed.":
nedlern there has no known_hosts entry for itself). So from the seats, which
run on the box, Timeshift was never searched although its snapshots are on the
box's own disk, and every run that found nothing ended "Could NOT search:
transcripts, timeshift" (GHI "The backup search cannot search ned-box's
Timeshift when it runs on ned-box, because it reaches "the box" by ssh to
itself", reproduced by merge-lane-2). On the box, Timeshift now runs the same
probe script through a local bash, the shell that ssh ran it under, and
transcripts keeps its local grep, which there is the box's, and sends no
second grep over ssh to the same directory. Which machine this is is the
locator's test, the host name before its first dot against NED_BOX_HOSTNAME,
decided once in build_report.

THE MAC'S HALF OF TRANSCRIPTS, ON THE BOX, is the log-store's copy of the
Mac's ~/.claude/projects, which transcript-mirror-to-log-store.py keeps under
MAC_TRANSCRIPTS_COPY_UNDER_LOG_STORE. Until 2026-09-30 the box reported the
Mac's transcripts as not searched, for the locator's reason that no route from
the box to the Mac is documented, so every run on the box that found nothing
exited 3. The user ruled that day (walk
merge-lane-mac-helper-open-decisions-2026-09-30, loose end 3) that a run on the
box greps that copy instead. A copy that is grepped in full counts as searched,
by the rule every copy-based surface here already follows: the log-store,
Timeshift and both snapshot surfaces each answer for the copy they hold, and
NOT FOUND there means "this copy does not have it", not "it never existed".
UNAVAILABLE stays what it means everywhere else: a part that could not be read.
So a copy that is missing, holds no transcript, or makes grep fail keeps the
old "not searched" line and stays UNAVAILABLE, while a copy searched and empty
is NOT FOUND, so transcripts leaves the box's "Could NOT search" line. A run
on the box that finds nothing still exits 3: local snapshots and Time Machine
are the Mac's and stay UNAVAILABLE there (measured on ned-box 2026-09-30:
"Could NOT search: local snapshots, time machine").

What the copy cannot hold is a Mac transcript written after its last mirror
pass. Two lines after the search date the copy. The first says when the
copy's newest transcript was last written on the Mac, measured from the copy
itself, never an assumed schedule: `rsync -a` keeps each file's time from the
Mac, so this dates the newest transcript, not the pass. The second reads the
stamp the mirror writes beside the copy's projects/ at the end of every pass
in which every source reached the store, MAC_MIRROR_PASS_STAMP_FILE_NAME, and
says when that pass started, so every transcript written before that time is
in the copy, or says plainly that the stamp is missing or holds no
time, so the pass time is not known. A Mac that is asleep or off writes no
transcripts, so its copy stays complete however old either time is; a Mac
that is awake but whose mirror has stopped shows as a stamp that falls behind
while sessions run, which is the case these lines exist to expose. Neither
line changes the surface's status.
--box-ssh-host and --skip box keep their meaning: the first names the box only
for the Mac's ssh, and the second still leaves Timeshift out.

Usage:
  python3 scripts/find-deleted-path-across-backups.py <path>
  python3 scripts/find-deleted-path-across-backups.py <path> --skip box
  python3 scripts/find-deleted-path-across-backups.py <path> --skip localsnapshots
  python3 scripts/find-deleted-path-across-backups.py <path> --log-store-root /home/nedlern/nedschorus-logs
  python3 scripts/find-deleted-path-across-backups.py <path> --repo ~/Projects/nedschorus
  python3 scripts/find-deleted-path-across-backups.py <path> --prompt-for-root

There is no recovery flag: each FOUND line is followed by the exact command
that recovers the content, for you to run.

<path> may be repo-relative ("docs/issues/46-x.md"), absolute, or any trailing
fragment of a path ("dispositions.md"). Fragments match by path suffix. It
may also be written as it is cited: in the scp form
("nedlern@ned-box:/home/nedlern/nedschorus-logs/x.md", or "ned-box:<path>"),
from the current directory ("../x.md", "./x.md"), or from a home ("~/x.md").
Each of those is turned into the path it names before any surface is
searched, and the header shows both.

WHY THE CITED FORMS ARE READ. Until 2026-09-29 a query was searched exactly as
typed, and two forms an agent really writes were never found anywhere. The
scp form, which CLAUDE.md prescribes for citing a log-store file, ends no path
in any store, so a copy sitting at exactly that path was listed only as a
candidate in "another directory", NOT FOUND, exit 1 (measured on the walk
minutes of merge-lane-mac-helper-open-items-and-questions-2026-09-23 the day
they were shipped). A path through `../` was matched as a literal suffix, and
the local-snapshot surface joined it onto the repository's top level, testing
the directory ABOVE it. Both were raised as questions on PR "The lost-file tool
searches git's reflog and the log-store, and prints each place as it finishes"
(review 5298941029) and left unfiled until the user ruled, 2026-09-29, walk
merge-lane-mac-helper-open-items-and-questions-2026-09-23 item 17: "If we are
going to use it, it should work properly." Which prefixes are hosts, and which
hosts' homes are known, is the locator's rule, imported from
locate-file-copies-across-machines.py rather than copied; so the locator must
never import this file in turn, and runs it as a program. `~` is expanded to
a home. Only paths that begin with `.` or `..`, or hold a `..`, are placed
from the current directory: "docs/x.md" stays repo-relative or a fragment, as
the paragraph above says, where the locator would place it from the current
directory too.

ONE FORM THE LOCAL-SNAPSHOT SURFACE CANNOT TAKE. A mounted snapshot is tested
with a single `test -e`, which needs a known path; locating a trailing fragment
inside one would need a `find` over the whole volume, and this version does not
run that fan-out on either snapshot surface. So a bare filename makes surface 1
UNAVAILABLE naming that reason, and a relative path with a directory component
is read as repo-relative — if it was meant as a fragment of some other path,
surface 1 tested the wrong place and says which place it tested. git, its
reflog, transcripts and Timeshift answer the fragment forms; the log-store
lists by the file's name, whatever form it was given in, and counts as found
only a copy whose path ends with the form given.

Exit code: 0 when at least one surface FOUND it. 1 when every surface that ran
was searched and none has it — the only exit that means "stop looking", once
any log-store candidates the summary names have been checked. 3 when
nothing was found and at least one surface could NOT be searched: the same
thing the summary's "Could NOT search" line says, and the usual result of an
unattended run, because reading inside Time Machine needs root — unless the
sudoers rule described above is installed, which is exactly what makes that
surface answerable with nobody in the room. 2 on a usage error. The first
version returned 1 for the third case too, so a wrapper branching on $? was
told "not found" by a run that had searched nothing. Log-store candidates
never count toward 0: the summary names them on a line of their own instead,
because counting them told a wrapper "found" for a path that never existed.
"""

# Deferred annotations support the Mac's system Python 3.9.
from __future__ import annotations

import argparse
import calendar
import importlib.util
import os
import re
import shlex
import socket
import subprocess
import sys
import time
from pathlib import Path

_locator_spec = importlib.util.spec_from_file_location(
    "locate_file_copies_across_machines", Path(__file__).with_name("locate-file-copies-across-machines.py"))
locator = importlib.util.module_from_spec(_locator_spec)
_locator_spec.loader.exec_module(locator)

PRINTED_GIT_INVOCATION_WITHOUT_REDIRECTING_VARIABLES = locator.PRINTED_GIT_INVOCATION_WITHOUT_REDIRECTING_VARIABLES

FOUND = "FOUND"
NOT_FOUND = "NOT FOUND"
UNAVAILABLE = "UNAVAILABLE"

EXIT_FOUND = 0
EXIT_NOT_FOUND_EVERYWHERE = 1
EXIT_USAGE = 2
EXIT_INCOMPLETE = 3

DEFAULT_BOX_SSH_HOST = "nedlern@ned-box"
DEFAULT_TIMESHIFT_SNAPSHOT_ROOT = "/mnt/backup/timeshift/snapshots"
# Each seat has its own directory, so a repo-relative path may exist under several roots.
DEFAULT_BOX_SEARCH_ROOTS = (
    "/home/nedlern/Projects/nedschorus",
    "/home/nedlern/agents/*",
)
DEFAULT_TRANSCRIPTS_DIR = "~/.claude/projects"
DEFAULT_LOG_STORE_ROOT = "/home/nedlern/nedschorus-logs"
# Keep this path aligned with transcript-mirror-to-log-store.py's destination.
MAC_TRANSCRIPTS_COPY_UNDER_LOG_STORE = ("transcripts", "mac", "projects")
# Keep this name aligned with transcript-mirror-to-log-store.py's MIRROR_PASS_STAMP_FILE_NAME.
MAC_MIRROR_PASS_STAMP_FILE_NAME = "last-complete-mirror-pass-utc.txt"
MAC_MIRROR_PASS_STAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
LOG_STORE_HITS_SHOWN = 10

# Limit mounts because each costs seconds; git usually narrows the date first.
DEFAULT_TIME_MACHINE_SNAPSHOT_LIMIT = 4

# The sudoers rule pins this exact mount point; changing it requires changing
# config/sudoers-mount-apfs-readonly-for-backup-recovery too.
TIME_MACHINE_READONLY_MOUNT_POINT = "/private/tmp/nedschorus-backup-readonly-mount"

TIME_MACHINE_SNAPSHOT_NAME_PREFIX = "com.apple.TimeMachine."

SPOKEN_TOOL_NAME = "find deleted path across backups"

# The Data volume holds user files; snapshots of / hold only system updates.
MAC_DATA_VOLUME = "/System/Volumes/Data"

# Only .local snapshots hold local user files; .backup is external and os.update is system-only.
LOCAL_SNAPSHOT_NAME_SUFFIX = ".local"

# Use /private/tmp because mount reports the resolved path, not the /tmp symlink.
LOCAL_SNAPSHOT_MOUNT_POINT = "/private/tmp/find-deleted-path-across-backups-local-snapshot-ro"

# Bound waits so an ssh to a sleeping box cannot hang recovery.
SHORT_TIMEOUT_SECONDS = 20
LONG_TIMEOUT_SECONDS = 120
BOX_LOG_STORE_CONNECT_TIMEOUT_SECONDS = 5

# grep uses exits 0, 1 and 2; this separate status means the transcript directory is absent.
BOX_TRANSCRIPTS_DIR_MISSING = 3


class SurfaceReport:
    """One surface's result and recovery instructions."""

    def __init__(self, surface, status, lines=None, recovery=None):
        self.surface = surface
        self.status = status
        self.lines = list(lines or [])
        self.recovery = list(recovery or [])

    def render(self):
        out = ["%-15s %s" % (self.surface, self.status)]
        for line in self.lines:
            out.append("    " + line)
        for command in self.recovery:
            out.append("    $ " + command)
        return "\n".join(out)


def running_on_ned_box(hostname=None):
    if hostname is None:
        hostname = socket.gethostname()
    return hostname.split(".")[0] == locator.NED_BOX_HOSTNAME


def run_command(argv, timeout=SHORT_TIMEOUT_SECONDS, cwd=None):
    """Run a command and return (returncode, stdout, stderr)."""
    # Git redirect variables override -C and must not leak into recovery commands.
    try:
        completed = subprocess.run(
            argv,
            cwd=cwd,
            env=locator.environment_without_git_redirecting_variables(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
    except FileNotFoundError:
        return 127, "", "%s: not found on this machine" % argv[0]
    except subprocess.TimeoutExpired:
        return 124, "", "timed out after %ss: %s" % (timeout, " ".join(argv))
    return (
        completed.returncode,
        completed.stdout.decode("utf-8", "replace"),
        completed.stderr.decode("utf-8", "replace"),
    )


def _strip_dot_slash(path):
    path = path.strip()
    while path.startswith("./"):
        path = path[2:]
    return path


def path_matches(candidate, wanted):
    """Return whether candidate ends with wanted at a path-component boundary."""
    candidate = _strip_dot_slash(candidate)
    wanted = _strip_dot_slash(wanted)
    if candidate == wanted:
        return True
    return candidate.endswith("/" + wanted)


class CitedQueryCannotBePlaced(Exception):
    """A cited path cannot be resolved from the available host and directory information."""


def _plain_path_from_cited_query(query, cwd=None):
    """Resolve host, home and dot-relative forms, or raise CitedQueryCannotBePlaced."""
    host, path = locator.split_host(query)
    if host is not None and not path.startswith("/"):
        home = locator.KNOWN_HOST_HOMES.get(host.split(".")[0])
        inside = path[2:] if path.startswith("~/") else ("" if path == "~" else path)
        if home:
            return os.path.normpath(home + ("/" + inside if inside else ""))
        if "/" in inside.rstrip("/"):
            raise CitedQueryCannotBePlaced(
                "Give the file's absolute path on %s: this program does not know that host's home directory." % host)
        return inside
    if path == "~" or path.startswith("~/"):
        return os.path.expanduser(path)
    parts = path.split("/")
    if path.startswith("/") or not (parts[0] in (".", "..") or ".." in parts):
        return path
    if cwd is None:
        try:
            cwd = os.getcwd()
        except OSError:
            raise CitedQueryCannotBePlaced(
                "Give the file's absolute path: the current directory no longer exists, so %r cannot be placed "
                "from it." % query)
    return os.path.normpath(os.path.join(cwd, path))



def search_local_snapshots(wanted, repo, runner=run_command, mount_point=LOCAL_SNAPSHOT_MOUNT_POINT):
    # Resolve /tmp to /private/tmp so comparisons use the mount table's spelling.
    mount_point = os.path.realpath(mount_point)
    probe_path, unavailable_lines = _local_snapshot_probe_path(wanted, repo, runner)
    if probe_path is None:
        return SurfaceReport("local snapshots", UNAVAILABLE, unavailable_lines)

    snapshots, failure = _local_snapshots(runner)
    if failure is not None:
        return SurfaceReport(
            "local snapshots",
            UNAVAILABLE,
            ["could not list the local snapshots of %s — %s" % (MAC_DATA_VOLUME, failure),
             "this surface is macOS-only; on the box there are none to list and none to search"],
            ["tmutil listlocalsnapshots %s" % MAC_DATA_VOLUME],
        )
    if not snapshots:
        return SurfaceReport(
            "local snapshots",
            UNAVAILABLE,
            ["%s retains no local snapshots right now, so there was nothing here to search" % MAC_DATA_VOLUME,
             "macOS keeps roughly a day of them; anything older has to come from the archive surfaces"],
        )

    already_mounted = _local_snapshots_already_mounted(runner)
    # An occupied mount point blocks later mounts, but may belong to a live seat.
    # Report how to clear it; never unmount another run's snapshot automatically.
    occupying = sorted(name for name, where in already_mounted.items() if where == mount_point)
    hits = []
    searched = []
    in_place = []
    unsearched = []
    stuck = None
    for snapshot in snapshots:
        if stuck is not None:
            # Stop after a failed release: later mounts would all fail on the occupied mount point.
            unsearched.append((snapshot, "not reached: " + stuck))
            continue
        outcome, where, release_failure, read_in_place = _local_snapshot_probe(
            snapshot, probe_path, mount_point, runner, already_mounted.get(snapshot))
        if outcome == "unmounted":
            unsearched.append((snapshot, where))
        else:
            searched.append(snapshot)
            if read_in_place and where != mount_point:
                in_place.append(snapshot)
            if outcome == "hit":
                hits.append((snapshot, where, read_in_place))
        if release_failure is not None:
            # Add "not reached" only for later snapshots; this snapshot was searched.
            stuck = "%s stayed mounted on %s — %s" % (snapshot, mount_point, release_failure)

    lines = ["%d local snapshot(s) retained, %d searched — no password needed for any of it"
             % (len(snapshots), len(searched)),
             "tested %s inside each" % probe_path]
    if occupying:
        # Report the occupied mount point even when every readable snapshot was searched.
        lines.append("the mount point %s already had %s on it when this run started, so every snapshot "
                     "this run had to mount for itself was refused — mount_apfs exits 77, \"Operation "
                     "not permitted\", on an occupied mount point"
                     % (mount_point, ", ".join(occupying)))
    if in_place:
        lines.append("%d of them were read where macOS already had them mounted, mounting nothing: %s"
                     % (len(in_place), ", ".join(in_place[:3]) + (", ..." if len(in_place) > 3 else "")))
    for snapshot, reason, repeats in _grouped_by_reason(unsearched):
        lines.append("could not search %s — %s" % (snapshot, reason))
        if repeats:
            lines.append("    ... and %d more snapshot(s) with the same message" % repeats)

    if stuck and not unsearched:
        # A failed release on the last snapshot has no later unsearched entry to report it.
        lines.append(stuck)

    clear_first = bool(stuck) or bool(occupying)

    if hits:
        lines.append("%d snapshot(s) still have it, newest first:" % len(hits))
        for snapshot, _, _ in hits[:5]:
            lines.append("    " + snapshot)
        if len(hits) > 5:
            lines.append("    ... and %d older" % (len(hits) - 5))
        best_snapshot, best_where, best_read_in_place = hits[0]
        return SurfaceReport("local snapshots", FOUND, lines,
                             _local_snapshot_recovery(best_snapshot, probe_path, mount_point, clear_first,
                                                      already_at=best_where if best_read_in_place else None))

    if searched:
        lines.append("searched %s .. %s and none of them has it" % (searched[-1], searched[0]))
    if not wanted.startswith("/"):
        # A relative path is tested as repo-relative, so report the location in case a suffix was intended.
        lines.append("(%s was read as a path relative to the repository; a trailing fragment of some "
                     "other path would need a find over the volume, which this surface does not run)" % wanted)
    if unsearched:
        # macOS cannot mount a snapshot twice; recovery must read an existing mount in place.
        reachable = [snapshot for snapshot, _ in unsearched if snapshot not in already_mounted]
        if not reachable:
            lines.append("every snapshot that could not be searched is one macOS already has mounted; "
                         "mount_apfs cannot open a snapshot twice, and macOS's own mounts are not this "
                         "script's to clear — the rest were searched and do not have it")
        return SurfaceReport(
            "local snapshots",
            UNAVAILABLE,
            lines,
            _local_snapshot_recovery(reachable[0], probe_path, mount_point, clear_first) if reachable
            else ([_local_snapshot_clear_mount_point_command(mount_point)] if clear_first else []),
        )
    # A failed release does not undo a completed search; keep NOT FOUND and provide the clear command.
    return SurfaceReport("local snapshots", NOT_FOUND, lines,
                         [_local_snapshot_clear_mount_point_command(mount_point)] if clear_first else [])


def _local_snapshot_clear_mount_point_command(mount_point):
    return "diskutil unmount %s" % shlex.quote(mount_point)


def _local_snapshot_recovery(snapshot, probe_path, mount_point, clear_first=False, already_at=None):
    """Return commands to copy the file and release any mount opened for recovery."""
    # Internal Data snapshots need no sudo; an already-mounted snapshot must be read in place.
    if already_at == mount_point:
        # Copy before clearing this mount point, or recovery unmounts its own source.
        return [
            "cp %s . && %s"
            % (shlex.quote(already_at + probe_path), _local_snapshot_clear_mount_point_command(mount_point)),
        ]
    if already_at:
        return [
            "cp %s ." % shlex.quote(already_at + probe_path),
            "# macOS already has %s mounted there — nothing to mount, nothing to release" % snapshot,
        ]
    clear = [_local_snapshot_clear_mount_point_command(mount_point)] if clear_first else []
    return clear + [
        "mkdir -p %s && mount_apfs -o ro -s %s %s %s"
        % (shlex.quote(mount_point), snapshot, MAC_DATA_VOLUME, shlex.quote(mount_point)),
        "cp %s . && diskutil unmount %s"
        % (shlex.quote(mount_point + probe_path), shlex.quote(mount_point)),
    ]


def _grouped_by_reason(unsearched):
    """Return (first snapshot, reason, additional count) for each distinct failure."""
    grouped = []
    index = {}
    for snapshot, reason in unsearched:
        if reason in index:
            grouped[index[reason]][2] += 1
            continue
        index[reason] = len(grouped)
        grouped.append([snapshot, reason, 0])
    return [(snapshot, reason, repeats) for snapshot, reason, repeats in grouped]


def _local_snapshots(runner):
    """Return (snapshot names newest first, failure reason or None)."""
    code, out, stderr = runner(["tmutil", "listlocalsnapshots", MAC_DATA_VOLUME])
    if code != 0:
        first = stderr.strip().splitlines()[0] if stderr.strip() else "tmutil exited %s" % code
        return [], first
    names = {line.strip() for line in out.splitlines()
             if line.strip().endswith(LOCAL_SNAPSHOT_NAME_SUFFIX)}
    # Snapshot timestamps sort lexically.
    return sorted(names, reverse=True), None


def _local_snapshots_already_mounted(runner):
    """Return a map from snapshot names to existing mount points."""
    # macOS cannot mount a snapshot twice; mount table entries may be stale.
    code, out, _ = runner(["mount"])
    if code != 0:
        return {}
    mounted = {}
    for line in out.splitlines():
        name, at, rest = line.partition("@")
        if not at or not name.endswith(LOCAL_SNAPSHOT_NAME_SUFFIX) or " on " not in rest:
            continue
        mounted[name] = rest.split(" on ", 1)[1].rsplit(" (", 1)[0]
    return mounted


def _local_snapshot_probe_path(wanted, repo, runner):
    """Return (absolute snapshot path, why-not lines)."""
    # A bare filename would require a whole-volume find, not a single path test.
    stripped = _strip_dot_slash(wanted)
    if stripped.startswith("/"):
        return _below_data_volume(stripped), []
    if "/" not in stripped:
        return None, [
            "%r is a bare filename, and locating one inside a snapshot needs a find over the whole "
            "volume rather than a single test — this surface does not run that fan-out" % wanted,
            "git, transcripts and Timeshift do answer a bare filename; re-run with at least one "
            "directory component, or the absolute path, to search this surface too",
        ]
    code, out, _ = runner(["git", "-C", repo, "rev-parse", "--show-toplevel"])
    if code != 0 or not out.strip():
        return None, [
            "%r is relative and %s is not a git repository, so there is no top level to resolve it "
            "against and no absolute path to test inside a snapshot" % (wanted, repo),
            "re-run with the absolute path, or with --repo pointing at the repository it belongs to",
        ]
    return _below_data_volume(os.path.join(out.strip(), stripped)), []


def _below_data_volume(path):
    """Return the absolute path as a Data-volume snapshot spells it."""
    # /tmp, /etc and /var symlinks are on System; realpath does not strip the Data firmlink prefix.
    path = os.path.realpath(path)
    if path == MAC_DATA_VOLUME:
        return "/"
    if path.startswith(MAC_DATA_VOLUME + "/"):
        return path[len(MAC_DATA_VOLUME):]
    return path


def _local_snapshot_probe(snapshot, probe_path, mount_point, runner, already_mounted=None):
    """Return (outcome, location or reason, release failure, read in place)."""
    # Internal Data snapshots need no sudo; diskutil unmount avoids plain umount's busy failures.
    if already_mounted:
        resolves, _, _ = runner(["test", "-d", already_mounted])
        if resolves == 0:
            exists, _, _ = runner(["test", "-e", already_mounted + probe_path])
            return ("hit" if exists == 0 else "miss"), already_mounted, None, True
    runner(["mkdir", "-p", mount_point])
    code, _, stderr = runner(["mount_apfs", "-o", "ro", "-s", snapshot, MAC_DATA_VOLUME, mount_point])
    if code != 0:
        first = stderr.strip().splitlines()[0] if stderr.strip() else "no error text"
        return "unmounted", "mount_apfs exited %s: %s" % (code, first), None, False
    try:
        exists, _, _ = runner(["test", "-e", mount_point + probe_path])
        outcome = "hit" if exists == 0 else "miss"
    finally:
        released, _, release_error = runner(["diskutil", "unmount", mount_point])
    release_failure = None
    if released != 0:
        first = release_error.strip().splitlines()[0] if release_error.strip() else "no error text"
        release_failure = "diskutil unmount exited %s: %s" % (released, first)
    return outcome, mount_point, release_failure, False



def search_git(wanted, repo, runner=run_command):
    """Search all refs without pruning history for deleted paths."""
    report = _search_git_revisions(
        wanted, repo, runner, "git", GIT_REVISIONS_EVERY_REF,
        "no ref in %s has ever contained a path matching %r",
        "matching paths appear in history, but neither the commits that touched them nor those commits' "
        "parents hold the content")
    if report.status == FOUND:
        report.newest_date_held = max(report.dates_held) if report.dates_held else None
    return report


GIT_REVISIONS_EVERY_REF = ("--all",)
GIT_REVISIONS_REFLOG_ONLY = ("--reflog", "--not", "--all")


def _search_git_revisions(wanted, repo, runner, surface, revisions, never_contained_template, none_held_line,
                          parents_outside_every_ref=False):
    """Search revisions and return a report for the named surface."""
    code, _, stderr = runner(["git", "-C", repo, "rev-parse", "--git-dir"])
    if code != 0:
        return SurfaceReport(surface, UNAVAILABLE, ["%s is not a git repository (%s)" % (repo, stderr.strip())])

    wanted, toplevel = _repo_relative_form(wanted, repo, runner)
    if wanted.startswith("/"):
        return SurfaceReport(
            surface,
            UNAVAILABLE,
            ["%s is outside %s, so git was not asked for it" % (wanted, toplevel or repo),
             "re-run with the path relative to the repository, or a trailing fragment of it"],
        )

    # git pathspecs are relative to -C, but these queries and --name-only results are repo-relative.
    code, out, _ = runner(["git", "-C", repo, "rev-parse", "--show-toplevel"])
    top_level = out.strip() if code == 0 and out.strip() else repo

    lines = []
    recovery = []
    dates_held = []
    try:
        paths = _git_candidate_paths(wanted, top_level, runner, revisions)
        if not paths:
            return SurfaceReport(surface, NOT_FOUND, [never_contained_template % (repo, wanted)])
        for path in paths:
            commit = _git_newest_commit_holding(path, top_level, runner, revisions, parents_outside_every_ref)
            if commit is None:
                continue
            sha, date, subject = commit
            lines.append("%s" % path)
            lines.append("    last held by %s (%s) %s" % (sha[:9], date, subject[:70]))
            recovery.append("%s -C %s show %s:%s" % (PRINTED_GIT_INVOCATION_WITHOUT_REDIRECTING_VARIABLES,
                                                     shlex.quote(repo), sha[:9], shlex.quote(path)))
            dates_held.append(date)
    except _GitCommandFailed as failure:
        return SurfaceReport(surface, UNAVAILABLE, ["git failed while searching %s — %s" % (repo, failure)])

    if not lines:
        return SurfaceReport(surface, NOT_FOUND, [none_held_line])

    report = SurfaceReport(surface, FOUND, lines, recovery)
    report.dates_held = dates_held
    return report


def _repo_relative_form(wanted, repo, runner=run_command):
    """Return (normalized query, repository top level or None)."""
    # git log accepts absolute paths, but cat-file blob addresses require repo-relative paths.
    if not wanted.startswith("/"):
        return wanted, None
    code, out, _ = runner(["git", "-C", repo, "rev-parse", "--show-toplevel"])
    if code != 0 or not out.strip():
        return wanted, None
    toplevel = os.path.realpath(out.strip())
    real = os.path.realpath(wanted)
    if real.startswith(toplevel + "/"):
        return real[len(toplevel) + 1:], toplevel
    return wanted, toplevel


def _git_candidate_paths(wanted, repo, runner, revisions=GIT_REVISIONS_EVERY_REF):
    """Try the exact pathspec, then scan known paths for suffix matches."""
    code, out, _ = runner(["git", "-C", repo, "log"] + list(revisions)
                          + ["--full-history", "-1", "--format=%H", "--", wanted])
    if code == 0 and out.strip():
        return [wanted]

    code, out, stderr = runner(
        ["git", "-C", repo, "log"] + list(revisions) + ["--full-history", "--name-only", "--format="],
        timeout=LONG_TIMEOUT_SECONDS,
    )
    if code != 0:
        # An empty list would falsely report NOT FOUND when git did not complete the search.
        raise _GitCommandFailed(stderr.strip() or "git log --name-only exited %s" % code)
    seen = []
    for line in out.splitlines():
        line = line.strip()
        if not line or line in seen:
            continue
        if path_matches(line, wanted):
            seen.append(line)
    return seen


class _GitCommandFailed(Exception):
    """A required git command failed; the exception text is stderr."""


def _git_newest_commit_holding(path, repo, runner, revisions=GIT_REVISIONS_EVERY_REF,
                               parents_outside_every_ref=False):
    """Return the newest holding commit as (sha, date, subject), or None."""
    # Deleting commits may have multiple parents; test each for the last surviving blob.
    # Reflog-only children can have ref-reachable parents; filter parents separately.
    code, out, stderr = runner(
        ["git", "-C", repo, "log"] + list(revisions)
        + ["--full-history", "--format=%H|%P|%ct|%ad|%s", "--date=short", "--", path],
        timeout=LONG_TIMEOUT_SECONDS,
    )
    if code != 0:
        raise _GitCommandFailed(stderr.strip() or "git log exited %s" % code)
    best = None  # (commit time, sha, date, subject)
    for line in out.splitlines():
        parts = line.split("|", 4)
        if len(parts) != 5:
            continue
        sha, parents, commit_time, date, subject = parts
        commit_time = int(commit_time)
        if best is not None and commit_time <= best[0]:
            break
        if _git_tree_holds(sha, path, repo, runner):
            best = (commit_time, sha, date, subject)
            continue
        for parent in parents.split():
            if not _git_tree_holds(parent, path, repo, runner):
                continue
            if parents_outside_every_ref and _git_some_ref_reaches(parent, repo, runner):
                continue
            code, out, stderr = runner(["git", "-C", repo, "log", "-1", "--format=%ct|%ad|%s", "--date=short", parent])
            if code != 0:
                raise _GitCommandFailed(stderr.strip() or "git log exited %s" % code)
            parent_time, parent_date, parent_subject = out.strip().split("|", 2)
            if best is None or int(parent_time) > best[0]:
                best = (int(parent_time), parent, parent_date, parent_subject)
    if best is None:
        return None
    return best[1], best[2], best[3]


def _git_tree_holds(sha, path, repo, runner):
    code, _, _ = runner(["git", "-C", repo, "cat-file", "-e", "%s:%s" % (sha, path)])
    return code == 0


def _git_some_ref_reaches(sha, repo, runner):
    code, out, stderr = runner(["git", "-C", repo, "rev-list", "-n", "1", sha, "--not", "--all"])
    if code != 0:
        raise _GitCommandFailed(stderr.strip() or "git rev-list exited %s" % code)
    return not out.strip()



def search_git_reflog(wanted, repo, runner=run_command):
    report = _search_git_revisions(
        wanted, repo, runner, "git reflog", GIT_REVISIONS_REFLOG_ONLY,
        "no commit that only a reflog names in %s has ever contained a path matching %r",
        "commits that only a reflog names touched a matching path, but none of them, and no parent of theirs "
        "that a branch or tag does not reach, holds it; history a branch or tag reaches is the git surface's",
        parents_outside_every_ref=True)
    if report.status == FOUND:
        report.lines.append("(no branch or tag reaches these commits, and git prunes reflog entries for "
                            "unreachable commits after 30 days by default — copy the file out now)")
    return report



def search_log_store(wanted, log_store_root, box_ssh_host, runner=run_command, store_is_here=None):
    """Return a report of exact-path copies and possible renamed copies."""
    # Stem matches can be unrelated files; only a component-boundary path match proves FOUND.
    name = _name_to_match_in_the_log_store(wanted)
    if store_is_here is None:
        store_is_here = os.path.isdir(log_store_root)
    probe_arguments = [_LOG_STORE_NAME_PROBE, log_store_root, name]
    if store_is_here:
        where = "this machine"
        code, out, stderr = runner([sys.executable, "-c"] + probe_arguments, timeout=SHORT_TIMEOUT_SECONDS)
    elif box_ssh_host:
        where = "the box (%s)" % box_ssh_host
        code, out, stderr = runner(
            ["ssh", "-o", "ConnectTimeout=%d" % BOX_LOG_STORE_CONNECT_TIMEOUT_SECONDS, "-o", "BatchMode=yes",
             box_ssh_host, "python3 -c " + " ".join(shlex.quote(a) for a in probe_arguments)],
            timeout=SHORT_TIMEOUT_SECONDS,
        )
        if code == 255:
            first_error = stderr.strip().splitlines()[0] if stderr.strip() else ""
            return SurfaceReport(
                "log-store",
                UNAVAILABLE,
                ["the box (%s) is unreachable — %s" % (box_ssh_host, first_error or "ssh failed"),
                 "see why with `ssh %s true`; once it connects, re-run this search" % box_ssh_host],
            )
    else:
        return SurfaceReport(
            "log-store",
            UNAVAILABLE,
            ["not searched — %s is not on this machine and no ssh host was given "
             "(--skip box, or an empty --box-ssh-host)" % log_store_root],
        )

    first_error = stderr.strip().splitlines()[0] if stderr.strip() else ""
    if code != 0:
        # A failed walk cannot count as a searched store.
        return SurfaceReport(
            "log-store",
            UNAVAILABLE,
            ["the search on %s did not complete (exit %s) — %s" % (where, code, first_error or "no error text")],
        )
    if "NOROOT" in out.splitlines():
        return SurfaceReport("log-store", UNAVAILABLE, ["%s does not exist on %s" % (log_store_root, where)])

    hits = []
    unread = []
    for line in out.splitlines():
        if line.startswith("HIT "):
            mtime, _, path = line[4:].partition(" ")
            if mtime.isdigit() and path:
                hits.append((int(mtime), path))
        elif line.startswith("PROBEFAIL "):
            unread.append(line[10:].strip())
    unread_line = ("could not read %d director%s under %s, first: %s — those were not searched"
                   % (len(unread), "y" if len(unread) == 1 else "ies", log_store_root, unread[0])) if unread else ""

    if not hits:
        if unread:
            return SurfaceReport("log-store", UNAVAILABLE, [unread_line, "the rest were searched and do not have it"])
        return SurfaceReport("log-store", NOT_FOUND, ["searched every file name under %s on %s; none has %r in it"
                                                      % (log_store_root, where, name)])

    shown_path = _path_to_find_in_the_log_store(wanted)
    wanted_in_store = shown_path.lower()
    same_name = os.path.basename(wanted_in_store)
    hits.sort(key=lambda hit: -hit[0])
    at_wanted_path = [hit for hit in hits if path_matches(hit[1].lower(), wanted_in_store)]
    list_every_name = _command_listing_every_log_store_name(log_store_root, name, store_is_here, box_ssh_host)

    if not at_wanted_path:
        if unread:
            head = [unread_line, "the rest were searched, and no file there is at a path ending in %r"
                    % shown_path]
            status = UNAVAILABLE
        else:
            head = ["searched every file name under %s on %s; none is at a path ending in %r"
                    % (log_store_root, where, shown_path)]
            status = NOT_FOUND
        lines = head + ["%d file(s) have %r in their name, newest first — candidates only, not counted as found:"
                        % (len(hits), name)] + _log_store_listing(hits, list_every_name)
        elsewhere = sum(1 for hit in hits if os.path.basename(hit[1]).lower() == same_name)
        if elsewhere:
            lines.append("(%d of them %s named %r but in another directory: a different file unless its content says"
                         " otherwise)" % (elsewhere, "is" if elsewhere == 1 else "are", os.path.basename(shown_path)))
        lines.append("(a copy is often renamed on its way into the store: check a candidate's content")
        lines.append(" before calling it recovered, and before saying the file does not exist)")
        report = SurfaceReport("log-store", status, lines)
        report.candidate_copies = len(hits)
        return report

    # List exact-path copies separately so newer candidates cannot push FOUND evidence out of the limit.
    found_copies = set(at_wanted_path)
    newer_candidates = [hit for hit in hits if hit not in found_copies and hit[0] > at_wanted_path[0][0]]
    older_candidates = len(hits) - len(at_wanted_path) - len(newer_candidates)
    lines = ["%d file(s) under %s on %s %s at a path ending in %r, newest first:"
             % (len(at_wanted_path), log_store_root, where, "is" if len(at_wanted_path) == 1 else "are", shown_path)]
    lines += _log_store_listing(at_wanted_path, list_every_name)
    if newer_candidates:
        lines.append("Candidates only, not counted as found: %d other file(s) with %r in their name are newer than"
                     " the newest copy at %r; check their content before settling on that copy:"
                     % (len(newer_candidates), name, shown_path))
        lines += _log_store_listing(newer_candidates, list_every_name)
    if older_candidates:
        lines.append("(%d older file(s) with %r in their name are candidates only and not listed; list every name"
                     " with: %s)" % (older_candidates, name, list_every_name))
    if unread:
        lines.append("(%s)" % unread_line)
    newest_at_wanted_path = shlex.quote(at_wanted_path[0][1])
    recovery = (["cp %s ." % newest_at_wanted_path] if store_is_here
                else ["scp %s:%s ." % (box_ssh_host, newest_at_wanted_path)])
    return SurfaceReport("log-store", FOUND, lines, recovery)


def _log_store_listing(hits, list_every_name):
    """Format a capped hit list with the count and command for omitted matches."""
    listing = ["    %s  %s" % (time.strftime("%Y-%m-%d %H:%M", time.localtime(mtime)), path)
               for mtime, path in hits[:LOG_STORE_HITS_SHOWN]]
    if len(hits) > LOG_STORE_HITS_SHOWN:
        listing.append("    ... and %d more — list them all with: %s"
                       % (len(hits) - LOG_STORE_HITS_SHOWN, list_every_name))
    return listing


def _path_to_find_in_the_log_store(wanted):
    return _strip_dot_slash(wanted).rstrip("/")


def _command_listing_every_log_store_name(log_store_root, name, store_is_here, box_ssh_host):
    pattern = "*%s*" % re.sub(r"([*?\[\\])", r"\\\1", name)
    command = "find %s ! -type d -iname %s -exec ls -lt {} +" % (shlex.quote(log_store_root), shlex.quote(pattern))
    return command if store_is_here else "ssh %s %s" % (box_ssh_host, shlex.quote(command))


def _name_to_match_in_the_log_store(wanted):
    """Return the lower-case filename stem without its last extension."""
    base = os.path.basename(_strip_dot_slash(wanted).rstrip("/"))
    return (os.path.splitext(base)[0] or base).lower()


# Use Python because BSD and GNU find disagree on printing modification times.
_LOG_STORE_NAME_PROBE = "\n".join([
    "import os, sys",
    "root, name = sys.argv[1], sys.argv[2].lower()",
    "if not os.path.isdir(root):",
    "    print('NOROOT')",
    "    sys.exit(0)",
    "unread = []",
    "for directory, _, files in os.walk(root, onerror=unread.append):",
    "    for base in files:",
    "        if name in base.lower():",
    "            path = os.path.join(directory, base)",
    "            try:",
    "                print('HIT %d %s' % (os.stat(path).st_mtime, path))",
    "            except OSError as error:",
    "                unread.append(error)",
    "for error in unread:",
    "    print('PROBEFAIL %s' % (getattr(error, 'filename', None) or error))",
])



def search_transcripts(wanted, transcripts_dir, box_ssh_host, runner=run_command, on_ned_box=False,
                       mac_copy_dir=None):
    lines = []
    recovery = []
    statuses = []
    here = locator.NED_BOX_HOSTNAME if on_ned_box else "this Mac"

    local_dir = Path(os.path.expanduser(transcripts_dir))
    if not local_dir.is_dir():
        lines.append("%s: %s does not exist" % (here, local_dir))
        statuses.append(UNAVAILABLE)
    else:
        code, out, _ = runner(
            ["grep", "-rl", "--include=*.jsonl", "-F", "-e", wanted, str(local_dir)],
            timeout=LONG_TIMEOUT_SECONDS,
        )
        hits = [h for h in out.splitlines() if h.strip()]
        if hits:
            lines.append("%s: %d session transcript(s) mention it" % (here, len(hits)))
            for hit in hits[:5]:
                lines.append("    " + hit)
            if len(hits) > 5:
                lines.append("    ... and %d more" % (len(hits) - 5))
            recovery.append(_transcript_context_print_command(wanted, hits[0]) + " | head")
            statuses.append(FOUND)
        elif code in (0, 1):
            lines.append("%s: searched %s, no transcript mentions it" % (here, local_dir))
            statuses.append(NOT_FOUND)
        else:
            lines.append("%s: grep failed over %s" % (here, local_dir))
            statuses.append(UNAVAILABLE)

    if on_ned_box:
        statuses.append(_search_mac_transcripts_copy(wanted, mac_copy_dir, runner, lines, recovery))
    elif box_ssh_host:
        code, out, stderr = runner(
            ["ssh", "-o", "ConnectTimeout=10", "-o", "BatchMode=yes", box_ssh_host, _box_transcript_grep_script(wanted)],
            timeout=LONG_TIMEOUT_SECONDS,
        )
        hits = [h for h in out.splitlines() if h.strip()]
        first_error = stderr.strip().splitlines()[0] if stderr.strip() else ""
        if code == 255:
            lines.append("the box (%s): unreachable — %s" % (box_ssh_host, first_error or "ssh failed"))
            statuses.append(UNAVAILABLE)
        elif code == BOX_TRANSCRIPTS_DIR_MISSING:
            lines.append("the box (%s): ~/.claude/projects does not exist there" % box_ssh_host)
            statuses.append(UNAVAILABLE)
        elif hits:
            lines.append("the box (%s): %d session transcript(s) mention it" % (box_ssh_host, len(hits)))
            for hit in hits[:5]:
                lines.append("    " + hit)
            if len(hits) > 5:
                lines.append("    ... and %d more" % (len(hits) - 5))
            recovery.append("ssh %s %s | head" % (box_ssh_host, shlex.quote(_transcript_context_print_command(wanted, hits[0]))))
            statuses.append(FOUND)
        elif code == 1:
            lines.append("the box (%s): searched ~/.claude/projects, no transcript mentions it" % box_ssh_host)
            statuses.append(NOT_FOUND)
        else:
            lines.append("the box (%s): grep over ~/.claude/projects failed (exit %s) — %s"
                         % (box_ssh_host, code, first_error or "no error text"))
            statuses.append(UNAVAILABLE)
    else:
        lines.append("the box: not searched — no ssh host given (--skip box, or an empty --box-ssh-host)")

    if FOUND in statuses:
        # The searching session quotes the path too; a lone transcript hit may contain no recovered content.
        lines.append("(a session's own transcript matches merely because the path was typed in it —")
        lines.append(" check that a hit actually contains the CONTENT before calling it recovered)")
    return SurfaceReport("transcripts", _combine(statuses), lines, recovery)


def _search_mac_transcripts_copy(wanted, copy_dir, runner, lines, recovery):
    """Append the Mac copy's search results and return its status."""
    not_searched = "the Mac: not searched — %s" % locator.MAC_NOT_REACHABLE_FROM_NED_BOX
    if copy_dir is None:
        lines.append(not_searched)
        return UNAVAILABLE
    copy_dir = Path(copy_dir)
    if not copy_dir.is_dir():
        lines.append(not_searched)
        lines.append("the Mac's log-store copy, %s, does not exist, so it was not searched either" % copy_dir)
        return UNAVAILABLE
    newest = _newest_transcript_write(copy_dir)
    if newest is None:
        lines.append(not_searched)
        lines.append("the Mac's log-store copy, %s, holds no session transcript, so it was not searched either"
                     % copy_dir)
        return UNAVAILABLE

    here = "the Mac, from its log-store copy"
    code, out, stderr = runner(
        ["grep", "-rl", "--include=*.jsonl", "-F", "-e", wanted, str(copy_dir)],
        timeout=LONG_TIMEOUT_SECONDS,
    )
    hits = [h for h in out.splitlines() if h.strip()]
    if hits:
        lines.append("%s: %d session transcript(s) mention it" % (here, len(hits)))
        for hit in hits[:5]:
            lines.append("    " + hit)
        if len(hits) > 5:
            lines.append("    ... and %d more" % (len(hits) - 5))
        recovery.append(_transcript_context_print_command(wanted, hits[0]) + " | head")
        status = FOUND
    elif code in (0, 1):
        lines.append("%s: searched %s, no transcript mentions it" % (here, copy_dir))
        status = NOT_FOUND
    else:
        first_error = stderr.strip().splitlines()[0] if stderr.strip() else "no error text"
        lines.append(not_searched)
        lines.append("the Mac's log-store copy, %s: grep failed (exit %s) — %s" % (copy_dir, code, first_error))
        return UNAVAILABLE
    lines.append("the copy's newest transcript was last written on the Mac at %s UTC, %s before this search; "
                 "a Mac transcript written after the copy's last mirror pass is not in it"
                 % (time.strftime("%Y-%m-%d %H:%M", time.gmtime(newest)), _age_in_words(time.time() - newest)))
    lines.append(_mac_mirror_pass_line(copy_dir.parent / MAC_MIRROR_PASS_STAMP_FILE_NAME))
    return status


def _mac_mirror_pass_line(stamp_path):
    """Return the line saying when the Mac's mirror last completed a pass, from its stamp."""
    unknown = "so when the Mac's mirror last completed a pass is not known on ned-box"
    try:
        text = stamp_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return "the Mac's mirror has left no pass-time stamp at %s, %s" % (stamp_path, unknown)
    except (OSError, UnicodeDecodeError) as error:
        return "the Mac's mirror pass-time stamp at %s could not be read (%s), %s" % (stamp_path, error, unknown)
    try:
        passed = calendar.timegm(time.strptime(text.strip(), MAC_MIRROR_PASS_STAMP_FORMAT))
    except ValueError:
        return "the Mac's mirror pass-time stamp at %s holds no time (%r), %s" % (stamp_path, text[:80], unknown)
    return ("the Mac's mirror last completed a pass that started at %s UTC, %s before this search, by its stamp at %s"
            % (time.strftime("%Y-%m-%d %H:%M", time.gmtime(passed)), _age_in_words(time.time() - passed), stamp_path))


def _newest_transcript_write(copy_dir):
    """Return the newest JSONL modification time, or None."""
    # rsync -a preserves Mac write times; this does not date the last mirror pass.
    newest = None
    for directory, _, files in os.walk(copy_dir):
        for base in files:
            if not base.endswith(".jsonl"):
                continue
            try:
                written = os.stat(os.path.join(directory, base)).st_mtime
            except OSError:
                continue
            if newest is None or written > newest:
                newest = written
    return newest


def _age_in_words(seconds):
    """Format a duration in minutes, hours or days."""
    seconds = max(0, int(seconds))
    if seconds < 2 * 3600:
        return "%d min" % (seconds // 60)
    if seconds < 2 * 86400:
        return "%d h" % (seconds // 3600)
    return "%d days" % (seconds // 86400)


# perl matches the name as text inside \Q...\E and looks for that text before trying the context, so a transcript
# line megabytes long prints at once. macOS grep refuses a repetition count above 255, and grep -E with the context
# split into smaller repeats runs for minutes on such a line.
TRANSCRIPT_CONTEXT_PERL_PROGRAM = r'print "$1\n" while /(.{0,400}\Q$ENV{N}\E.{0,2000})/g'


def _transcript_context_print_command(wanted, transcript_path):
    """Return the command that prints the text around each occurrence of the searched name in one transcript."""
    return "N=%s perl -ne %s %s" % (shlex.quote(wanted), shlex.quote(TRANSCRIPT_CONTEXT_PERL_PROGRAM),
                                   shlex.quote(transcript_path))


def _box_transcript_grep_script(wanted):
    """Return the box search script, preserving grep's exit status."""
    # Piping through head would replace grep failures with head's success.
    return "\n".join([
        'd="$HOME/.claude/projects"',
        'if [ ! -d "$d" ]; then echo "$d does not exist" >&2; exit %d; fi' % BOX_TRANSCRIPTS_DIR_MISSING,
        "exec grep -rl --include='*.jsonl' -F -e %s \"$d\"" % shlex.quote(wanted),
    ])



def search_timeshift(wanted, box_ssh_host, snapshot_root, search_roots, runner=run_command, on_ned_box=False):
    script = _timeshift_probe_script(wanted, snapshot_root, search_roots)
    if on_ned_box:
        where = locator.NED_BOX_HOSTNAME
        argv = ["bash", "-c", script]
    elif not box_ssh_host:
        return SurfaceReport("timeshift", UNAVAILABLE, ["not searched — no ssh host given (--skip box, or an empty --box-ssh-host)"])
    else:
        where = box_ssh_host
        argv = ["ssh", "-o", "ConnectTimeout=10", "-o", "BatchMode=yes", box_ssh_host, script]

    code, out, stderr = runner(argv, timeout=LONG_TIMEOUT_SECONDS)
    first_error = stderr.strip().splitlines()[0] if stderr.strip() else ""
    if code == 255 and not on_ned_box:
        return SurfaceReport(
            "timeshift",
            UNAVAILABLE,
            ["the box (%s) is unreachable — %s" % (box_ssh_host, first_error or "ssh failed"),
             "the snapshots are fine; this machine just cannot see them right now"],
        )
    if code != 0:
        # A failed probe may leave snapshots unsearched.
        return SurfaceReport(
            "timeshift",
            UNAVAILABLE,
            ["the search on %s did not complete (exit %s) — %s" % (where, code, first_error or "no error text")],
        )
    if "NOROOT" in out:
        return SurfaceReport("timeshift", UNAVAILABLE, ["%s does not exist on %s — is the backup drive mounted?" % (snapshot_root, where)])

    hits = sorted({line[4:].strip() for line in out.splitlines() if line.startswith("HIT ")}, reverse=True)
    unsearched = [line[10:].strip() for line in out.splitlines() if line.startswith("PROBEFAIL ")]
    if not hits:
        if unsearched:
            return SurfaceReport(
                "timeshift",
                UNAVAILABLE,
                ["find failed under %d snapshot director%s on %s, first: %s"
                 % (len(unsearched), "y" if len(unsearched) == 1 else "ies", where, unsearched[0]),
                 "the rest were searched and do not have it; those %d were not searched" % len(unsearched)],
            )
        return SurfaceReport("timeshift", NOT_FOUND, ["searched every snapshot under %s on %s" % (snapshot_root, where)])

    lines = ["%d snapshot(s) on %s still have it, newest first:" % (len(hits), where)]
    for hit in hits[:5]:
        lines.append("    " + hit)
    if len(hits) > 5:
        lines.append("    ... and %d older" % (len(hits) - 5))
    if unsearched:
        lines.append("(find failed under %d snapshot director%s, first: %s — those were not searched)"
                     % (len(unsearched), "y" if len(unsearched) == 1 else "ies", unsearched[0]))
    if on_ned_box:
        recovery = ["cp %s ." % shlex.quote(hits[0])]
    else:
        recovery = ["scp %s:%s ." % (box_ssh_host, shlex.quote(hits[0]))]
    return SurfaceReport("timeshift", FOUND, lines, recovery)


def _timeshift_probe_script(wanted, snapshot_root, search_roots):
    """Return a shell probe emitting HIT, NOROOT and PROBEFAIL records."""
    # Keep root globs expandable, but quote the caller's path and find pattern.
    script = ["set -u", "ROOT=%s" % shlex.quote(snapshot_root)]
    script.append('if [ ! -d "$ROOT" ]; then echo "NOROOT"; exit 0; fi')
    script.append('for snap in "$ROOT"/*; do')
    script.append('  [ -d "$snap" ] || continue')
    if wanted.startswith("/"):
        script.append('  target="$snap/localhost"%s' % shlex.quote(wanted))
        script.append('  if [ -e "$target" ]; then echo "HIT $target"; fi')
    else:
        bases = " ".join('"$snap/localhost"%s' % root for root in search_roots)
        script.append("  for base in %s; do" % bases)
        script.append('    [ -d "$base" ] || continue')
        script.append('    if [ -e "$base"/%s ]; then echo "HIT $base/"%s' % (shlex.quote(wanted), shlex.quote(wanted)))
        script.append("    else find \"$base\" -path %s -exec printf 'HIT %%s\\n' {} \\; || echo \"PROBEFAIL $base\""
                      % shlex.quote("*/" + wanted))
        script.append("    fi")
        script.append("  done")
    script.append("done")
    return "\n".join(script)



def search_time_machine(wanted, newest_date_held=None, snapshot_limit=DEFAULT_TIME_MACHINE_SNAPSHOT_LIMIT,
                        runner=run_command, prompt_for_root=False):
    destination = _time_machine_destination(runner)
    if destination is None:
        return SurfaceReport("time machine", UNAVAILABLE, ["no Time Machine destination is configured on this Mac"])

    name = destination["name"]
    device, mount_point, attached = _time_machine_volume_state(name, runner)

    if not attached:
        return SurfaceReport(
            "time machine",
            UNAVAILABLE,
            ["the backup disk %r is not connected to this Mac" % name,
             "reconnect it and re-run; nothing else here can be answered without it"],
        )

    if not mount_point:
        code, _, stderr = runner(["diskutil", "mount", name])
        device, mount_point, attached = _time_machine_volume_state(name, runner)
        if not mount_point:
            return SurfaceReport(
                "time machine",
                UNAVAILABLE,
                ["the backup disk %r is attached but will not mount" % name,
                 "diskutil said: %s" % (stderr.strip() or "mount failed with code %s" % code)],
                ["diskutil mount %s" % shlex.quote(name)],
            )

    snapshots = _time_machine_snapshots(device, runner)
    if not snapshots:
        return SurfaceReport(
            "time machine",
            UNAVAILABLE,
            ["%r is mounted at %s but lists no snapshots" % (name, mount_point)],
        )

    candidates, dated_by_git = _time_machine_candidates(snapshots, newest_date_held, snapshot_limit)
    can_sudo, _, _ = runner(["sudo", "-n", "true"])

    hits = []
    searched = []
    unsearched = []
    stuck = None
    for snapshot in candidates:
        if stuck is not None:
            # A failed release blocks every later mount on this fixed mount point.
            unsearched.append((snapshot, "not reached: " + stuck))
            continue
        outcome, detail, release_failure = _time_machine_probe(snapshot, device, wanted, runner, prompt_for_root)
        if release_failure is not None:
            stuck = "%s stayed mounted on %s — %s" % (
                snapshot, TIME_MACHINE_READONLY_MOUNT_POINT, release_failure)
        if outcome == "no credential":
            # A missing credential blocks every candidate; another snapshot cannot help.
            return _time_machine_root_wall(snapshots, candidates, dated_by_git, device, detail, unsearched)
        if outcome == "hit":
            hits.append((snapshot, detail))
            searched.append(snapshot)
        elif outcome == "miss":
            searched.append(snapshot)
        else:
            unsearched.append((snapshot, detail))
    if can_sudo == 0:
        how = "with an already-warm sudo"
    elif prompt_for_root:
        how = "with --prompt-for-root, which let sudo ask at the terminal"
    else:
        how = "with no credential cached and nobody asked — the sudoers rule is installed"
    lines = ["%d snapshots present; %d of %d candidates searched %s"
             % (len(snapshots), len(searched), len(candidates), how)]
    for snapshot, reason in unsearched:
        lines.append("could not search %s — %s" % (snapshot, reason))
    if stuck and not unsearched:
        # The last candidate has no later unsearched entry to carry a failed release.
        lines.append(stuck)
    if hits:
        for snapshot, hit in hits:
            lines.append("%s holds %s" % (snapshot, hit))
        return SurfaceReport("time machine", FOUND, lines,
                             _time_machine_manual_recovery(hits[0][0], device, hits[0][1],
                                                           clear_first=bool(stuck)))
    if searched:
        lines.append("searched %s and did not find it" % ", ".join(searched))
    if unsearched:
        return SurfaceReport("time machine", UNAVAILABLE, lines,
                             _time_machine_manual_recovery(unsearched[0][0], device,
                                                           clear_first=bool(stuck)))
    # A failed release does not undo a completed search; provide the clear command for the next run.
    return SurfaceReport("time machine", NOT_FOUND, lines,
                         [_time_machine_clear_mount_point_command()] if stuck else [])


def _time_machine_root_wall(snapshots, candidates, dated_by_git, device, refusal, unsearched):
    """Return an UNAVAILABLE report marked as requiring a root credential."""
    # Only the mount's sudo refusal proves this; sudo -n true does not test the mount's NOPASSWD rule.
    lines = [
        "%d snapshots present, %s .. %s — enumerated fine, but the mount was refused: %s"
        % (len(snapshots), snapshots[-1], snapshots[0], refusal),
        "this is a real wall, not an empty result: the file may well be in there",
        "installing config/sudoers-mount-apfs-readonly-for-backup-recovery removes this wall for "
        "this one read-only mount and nothing else, so an unattended run can cross it",
        "at a terminal, --prompt-for-root runs the mount below from here instead of printing it",
    ]
    for snapshot, reason in unsearched:
        lines.append("could not search %s — %s" % (snapshot, reason))
    lines.append(_candidate_line(candidates[0], dated_by_git))
    lines.append(_alternative_line(snapshots, candidates[0], dated_by_git))
    wall = SurfaceReport("time machine", UNAVAILABLE, lines,
                         _time_machine_manual_recovery(candidates[0], device))
    wall.root_credential_needed = True
    wall.snapshots_enumerated = list(snapshots)
    return wall


def _is_sudo_non_interactive_refusal(stderr):
    """Distinguish sudo's password refusal from a snapshot mount failure."""
    # sudo versions vary the surrounding text but retain "a password is required".
    return "password is required" in (stderr or "").lower()


def _time_machine_clear_mount_point_command():
    return "diskutil unmount %s" % shlex.quote(TIME_MACHINE_READONLY_MOUNT_POINT)


def _time_machine_manual_recovery(snapshot, device, path_inside=None, clear_first=False):
    """Return commands to mount a snapshot, copy the file and unmount."""
    mount = shlex.quote(TIME_MACHINE_READONLY_MOUNT_POINT)
    # Snapshot files live under <stamp>.backup/Data, not directly under the mount point.
    data_root = _time_machine_snapshot_data_root(snapshot, TIME_MACHINE_READONLY_MOUNT_POINT)
    clear = [_time_machine_clear_mount_point_command()] if clear_first else []
    open_it = "mkdir -p %s && sudo mount_apfs -o ro -s %s %s %s" % (mount, snapshot, device, mount)
    if path_inside:
        return clear + [open_it,
                        "cp %s . && diskutil unmount %s"
                        % (shlex.quote(data_root + path_inside), mount)]
    return clear + [open_it + " && ls %s" % shlex.quote(data_root),
                    "# then look for the path under %s, and: diskutil unmount %s"
                    % (data_root, mount)]


def _time_machine_destination(runner):
    code, out, _ = runner(["tmutil", "destinationinfo"])
    if code != 0:
        return None
    destination = {}
    for line in out.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip().lower()
        value = value.strip()
        if key == "name" and value:
            destination["name"] = value
        elif key == "mount point" and value:
            destination["mount_point"] = value
    return destination if destination.get("name") else None


def _time_machine_volume_state(name, runner):
    """Return (device node, mount point, attached) resolved from the volume name."""
    # Device numbers change when disks are replugged.
    code, out, _ = runner(["diskutil", "info", name])
    if code != 0:
        return None, None, False
    device = None
    mount_point = None
    for line in out.splitlines():
        key, _, value = line.partition(":")
        key = key.strip().lower()
        value = value.strip()
        if key == "device node" and value:
            device = value
        elif key == "mount point" and value:
            mount_point = value
    return device, mount_point, True


def _time_machine_snapshots(device, runner):
    if not device:
        return []
    code, out, _ = runner(["diskutil", "apfs", "listSnapshots", device], timeout=LONG_TIMEOUT_SECONDS)
    if code != 0:
        return []
    names = []
    for line in out.splitlines():
        stripped = line.strip().lstrip("|").strip()
        if stripped.startswith("Name:"):
            value = stripped.split(":", 1)[1].strip()
            if value:
                names.append(value)
    # Snapshot timestamps sort lexically.
    return sorted(names, reverse=True)


def _time_machine_candidates(snapshots, newest_date_held, limit):
    """Prefer snapshots near the last date git held the file."""
    if newest_date_held:
        compact = newest_date_held.replace("-", "")
        before = [s for s in snapshots if _snapshot_datestamp(s) <= compact]
        if before:
            return before[:limit], True
    return snapshots[:limit], False


def _candidate_line(candidate, dated_by_git):
    if dated_by_git:
        return "best candidate (newest snapshot git can prove predates the deletion): %s" % candidate
    return ("no date hint — the git surface was skipped or found nothing — so this is simply the "
            "newest snapshot, which may well POSTDATE the deletion: %s" % candidate)


def _alternative_line(snapshots, candidate, dated_by_git):
    """Suggest a newer snapshot with a git bound, otherwise an older one."""
    # A bounded candidate may predate creation; an unbounded newest candidate may postdate deletion.
    try:
        index = snapshots.index(candidate)
    except ValueError:
        return "next to try: (unknown — the candidate is not in the enumerated list)"
    if dated_by_git:
        if index == 0:
            return "next to try if it predates the file: (none — this is the newest on the disk)"
        return "next to try if it predates the file: %s" % snapshots[index - 1]
    if index + 1 >= len(snapshots):
        return "next to try if it postdates the deletion: (none — this is the oldest on the disk)"
    return "next to try if it postdates the deletion: %s" % snapshots[index + 1]


def _snapshot_datestamp(snapshot_name):
    """Return the first eight timestamp digits as YYYYMMDD."""
    digits = "".join(ch for ch in snapshot_name if ch.isdigit())
    return digits[:8]


def _snapshot_timestamp(snapshot_name):
    """Return the snapshot time as YYYYMMDDhhmmss, or None."""
    # Date-only comparisons cannot place a snapshot relative to a same-day deletion.
    digits = "".join(ch for ch in snapshot_name if ch.isdigit())
    return digits[:14] if len(digits) >= 14 else None


def _time_machine_snapshot_data_root(snapshot, mount_point):
    """Return the snapshot's <stamp>.backup/Data directory."""
    # .previous trees are partial and cannot stand in for complete snapshots.
    stamp = snapshot
    if stamp.startswith(TIME_MACHINE_SNAPSHOT_NAME_PREFIX):
        stamp = stamp[len(TIME_MACHINE_SNAPSHOT_NAME_PREFIX):]
    return "%s/%s/Data" % (mount_point, stamp)


def _time_machine_probe(snapshot, device, wanted, runner, prompt_for_root=False):
    """Return (outcome, detail, release failure) for one snapshot."""
    # sudoers matches argument order and the fixed mount point; preserve the mount command's shape.
    mount_point = TIME_MACHINE_READONLY_MOUNT_POINT
    runner(["mkdir", "-p", mount_point])
    sudo = ["sudo"] if prompt_for_root else ["sudo", "-n"]
    release_failure = None
    code, _, stderr = runner(sudo + ["mount_apfs", "-o", "ro", "-s", snapshot, device, mount_point], timeout=LONG_TIMEOUT_SECONDS)
    if code != 0:
        first = stderr.strip().splitlines()[0] if stderr.strip() else "exit %s" % code
        if _is_sudo_non_interactive_refusal(stderr):
            return "no credential", first, None
        return "unmounted", "mount_apfs said: %s" % first, None
    # Return after finally so a release failure reaches the caller.
    try:
        data_root = _time_machine_snapshot_data_root(snapshot, mount_point)
        laid_out, _, _ = runner(["test", "-d", data_root])
        if laid_out != 0:
            # An unreadable data root is unsearched, not evidence that the file is absent.
            outcome = ("unreadable", "mounted, but %s is not there — a snapshot of this backup "
                                     "volume keeps its files under <stamp>.backup/Data" % data_root)
        elif wanted.startswith("/"):
            exists, _, _ = runner(["test", "-e", data_root + wanted])
            outcome = ("hit", wanted) if exists == 0 else ("miss", None)
        else:
            code, out, stderr = runner(
                ["find", data_root + "/Users", "-path", "*/" + wanted, "-maxdepth", "12"],
                timeout=LONG_TIMEOUT_SECONDS,
            )
            found = next((line.strip() for line in out.splitlines() if line.strip()), None)
            if found is not None:
                outcome = ("hit", found[len(data_root):])
            elif code != 0:
                first = stderr.strip().splitlines()[0] if stderr.strip() else "exit %s" % code
                outcome = ("unreadable", "find said: %s" % first)
            else:
                outcome = ("miss", None)
    finally:
        # diskutil unmount needs no sudo; plain umount can leave a freshly mounted snapshot busy.
        released, _, release_error = runner(["diskutil", "unmount", mount_point],
                                            timeout=LONG_TIMEOUT_SECONDS)
    if released != 0:
        first = release_error.strip().splitlines()[0] if release_error.strip() else "exit %s" % released
        release_failure = "diskutil unmount exited %s: %s" % (released, first)
    return outcome[0], outcome[1], release_failure



def announce_root_password_wall_by_speech(wanted, reports, repo, skip, runner):
    """Speak and return the password request, or return None."""
    # Wait for speech to finish so script exit does not orphan the announcement.
    sentence = speech_line_when_root_password_is_needed(wanted, reports, repo, skip, runner)
    if sentence is None:
        return None
    runner(["say", sentence])
    return sentence


def speech_line_when_root_password_is_needed(wanted, reports, repo, skip, runner):
    """Return a password request only when mounting a backup can help recovery."""
    # No deletion timestamp means no proof a backup predates deletion; never-committed paths stay silent.
    wall = next((r for r in reports if getattr(r, "root_credential_needed", False)), None)
    if wall is None:
        return None
    if any(r.status == FOUND for r in reports):
        return None
    stripped = _strip_dot_slash(wanted)
    if "/" not in stripped:
        return None
    if "git" in skip:
        # Do not query git when the caller skipped that surface.
        return None
    deleted_at = _git_deletion_timestamp(stripped, repo, runner)
    if deleted_at is None:
        return None
    stamps = [_snapshot_timestamp(s) for s in getattr(wall, "snapshots_enumerated", [])]
    if not any(stamp is not None and stamp <= deleted_at for stamp in stamps):
        return None
    return "%s needs your password to search Time Machine for %s" % (
        SPOKEN_TOOL_NAME, os.path.basename(stripped))


def _git_deletion_timestamp(wanted, repo, runner):
    """Return the deletion commit's local timestamp as YYYYMMDDhhmmss, or None."""
    # Snapshot names use local time; query from the repo root because wanted is repo-relative.
    code, out, _ = runner(["git", "-C", repo, "rev-parse", "--show-toplevel"])
    top_level = out.strip() if code == 0 and out.strip() else repo
    code, out, _ = runner(["git", "-C", top_level, "log", "--all", "--full-history", "-1",
                           "--diff-filter=D", "--date=format-local:%Y%m%d%H%M%S",
                           "--format=%cd", "--", wanted])
    if code != 0 or not out.strip():
        return None
    stamp = out.strip().splitlines()[0].strip()
    return stamp if len(stamp) == 14 and stamp.isdigit() else None



def _combine(statuses):
    """Return FOUND for any hit, otherwise UNAVAILABLE for any unsearched part."""
    if FOUND in statuses:
        return FOUND
    if UNAVAILABLE in statuses or not statuses:
        return UNAVAILABLE
    return NOT_FOUND


def build_report(wanted, repo, transcripts_dir, box_ssh_host, snapshot_root, search_roots, skip=(),
                 runner=run_command, prompt_for_root=False, log_store_root=DEFAULT_LOG_STORE_ROOT,
                 on_surface_done=None, on_ned_box=None):
    if on_ned_box is None:
        on_ned_box = running_on_ned_box()
    reports = []
    newest_date_held = None

    def finished(report):
        reports.append(report)
        if on_surface_done is not None:
            on_surface_done(report)
        return report

    if "localsnapshots" not in skip:
        # Local snapshots are cheap, unprivileged and can hold files deleted minutes ago.
        finished(search_local_snapshots(wanted, repo, runner))
    if "git" not in skip:
        git_report = finished(search_git(wanted, repo, runner))
        newest_date_held = getattr(git_report, "newest_date_held", None)
    if "reflog" not in skip:
        finished(search_git_reflog(wanted, repo, runner))
    if "box" in skip:
        # --skip box must also avoid transcript ssh waits when the box is asleep.
        box_ssh_host = ""
    if "logstore" not in skip and ("box" not in skip or os.path.isdir(log_store_root)):
        # Search the fast log-store before slower surfaces so interrupted runs retain its result.
        finished(search_log_store(wanted, log_store_root, box_ssh_host, runner))
    if "transcripts" not in skip:
        mac_copy_dir = os.path.join(log_store_root, *MAC_TRANSCRIPTS_COPY_UNDER_LOG_STORE) if on_ned_box else None
        finished(search_transcripts(wanted, transcripts_dir, box_ssh_host, runner, on_ned_box=on_ned_box,
                                    mac_copy_dir=mac_copy_dir))
    if "box" not in skip and "timeshift" not in skip:
        finished(search_timeshift(wanted, box_ssh_host, snapshot_root, search_roots, runner, on_ned_box=on_ned_box))
    if "timemachine" not in skip:
        finished(search_time_machine(wanted, newest_date_held, runner=runner,
                                     prompt_for_root=prompt_for_root))
    # Assemble the speech decision here so callers that bypass main receive it too.
    announce_root_password_wall_by_speech(wanted, reports, repo, skip, runner)
    return reports


def render_header(wanted):
    return "Searching every history this fleet keeps for: %s" % wanted


def render_summary(reports):
    out = []
    found = [r for r in reports if r.status == FOUND]
    blocked = [r for r in reports if r.status == UNAVAILABLE]
    candidates = [r for r in reports if r.status != FOUND and getattr(r, "candidate_copies", 0)]
    if found:
        out.append("Recoverable from: %s." % ", ".join(r.surface for r in found))
    else:
        out.append("No surface that could be searched has it.")
    if candidates:
        out.append("Candidates only, not counted as found: %s — check their content before saying it does not exist."
                   % ", ".join(r.surface for r in candidates))
    if blocked:
        out.append("Could NOT search: %s — see each one's line above; those are not 'not found'."
                   % ", ".join(r.surface for r in blocked))
    return "\n".join(out)


def render(wanted, reports):
    """Return the complete report as text."""
    out = [render_header(wanted), ""]
    for report in reports:
        out.append(report.render())
        out.append("")
    out.append(render_summary(reports))
    return "\n".join(out)


def print_surface_as_it_finishes(report):
    # Flush pipe buffers so a timeout cannot erase results from completed surfaces.
    print(report.render() + "\n", flush=True)


def main(argv=None, runner=run_command):
    parser = argparse.ArgumentParser(
        description="Find a deleted path across this Mac's local snapshots, git and its reflog, the log-store, "
                    "agent transcripts, Timeshift on the box, and Time Machine.",
    )
    parser.add_argument("path", help="repo-relative, absolute, or any trailing fragment of the path; "
                                     "the scp form nedlern@ned-box:<path>, ../<path> and ~/<path> are read too")
    parser.add_argument("--repo", default=os.environ.get("FIND_DELETED_PATH_REPO", "."),
                        help="git repository to search (default: current directory)")
    parser.add_argument("--transcripts-dir", default=os.environ.get("FIND_DELETED_PATH_TRANSCRIPTS_DIR", DEFAULT_TRANSCRIPTS_DIR))
    parser.add_argument("--box-ssh-host", default=os.environ.get("FIND_DELETED_PATH_BOX_SSH_HOST", DEFAULT_BOX_SSH_HOST))
    parser.add_argument("--timeshift-snapshot-root", default=os.environ.get("FIND_DELETED_PATH_TIMESHIFT_SNAPSHOT_ROOT", DEFAULT_TIMESHIFT_SNAPSHOT_ROOT))
    parser.add_argument("--log-store-root", default=os.environ.get("FIND_DELETED_PATH_LOG_STORE_ROOT", DEFAULT_LOG_STORE_ROOT),
                        help="the log-store's directory: read in place when it exists on this machine, "
                             "otherwise on the box over ssh")
    parser.add_argument("--skip", action="append", default=[],
                        choices=["localsnapshots", "git", "reflog", "logstore", "transcripts", "box", "timeshift",
                                 "timemachine"],
                        help="skip a surface (repeatable); 'box' skips everything on the box — "
                             "its transcripts, Timeshift, and the log-store unless it is on this machine — "
                             "so nothing is sent over ssh")
    parser.add_argument("--prompt-for-root", action="store_true",
                        help="mount the Time Machine snapshot from here, letting sudo ask for your "
                             "password in this terminal, instead of printing the command. Only ever "
                             "pass this by hand: a hook has no terminal to answer a prompt in")
    args = parser.parse_args(argv)

    try:
        named = _plain_path_from_cited_query(args.path)
    except CitedQueryCannotBePlaced as refusal:
        parser.error(str(refusal))
    wanted, _ = _repo_relative_form(named, args.repo, runner)
    shown = wanted if wanted == args.path else "%s (given as %s)" % (wanted, args.path)

    print(render_header(shown) + "\n", flush=True)
    reports = build_report(
        wanted,
        args.repo,
        args.transcripts_dir,
        args.box_ssh_host,
        args.timeshift_snapshot_root,
        DEFAULT_BOX_SEARCH_ROOTS,
        skip=set(args.skip),
        runner=runner,
        prompt_for_root=args.prompt_for_root,
        log_store_root=args.log_store_root,
        on_surface_done=print_surface_as_it_finishes,
    )
    print(render_summary(reports), flush=True)
    return exit_status(reports)


def exit_status(reports):
    """Return 0 for a hit, 1 for an exhaustive miss, or 3 for an incomplete search."""
    if any(r.status == FOUND for r in reports):
        return EXIT_FOUND
    if not reports or any(r.status == UNAVAILABLE for r in reports):
        return EXIT_INCOMPLETE
    return EXIT_NOT_FOUND_EVERYWHERE


if __name__ == "__main__":
    sys.exit(main())
