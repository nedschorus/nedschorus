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

THE FIVE SURFACES, in the order they are searched:

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
  3. transcripts  — agent session JSONL under ~/.claude/projects, on this Mac
                    AND on the box. A file's content often survives in the
                    transcript of the session that wrote or read it, even when
                    every copy on disk is gone.
  4. Timeshift    — snapshots on ned-box at /mnt/backup/timeshift/snapshots.
                    Ordinary world-readable directories: no privilege needed.
  5. Time Machine — snapshots on the Mac's EXTERNAL backup disk. Enumerating
                    them needs no privilege; READING INSIDE ONE NEEDS ROOT
                    (measured 2026-08-23: `sudo mount_apfs -o ro` refused
                    without a password). The difference from surface 1 is the
                    VOLUME, not the command: the same mount_apfs runs
                    unprivileged against this Mac's internal Data volume and
                    needs a password against the external backup volume. A
                    reader who generalises either way gets it wrong. It is ONE
                    operation, which is what makes that wall crossable at all —
                    see CROSSING THE ROOT WALL below.

WHY SURFACE 1 IS NOT REDUNDANT WITH SURFACE 5, measured 2026-08-31.
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

CROSSING THE ROOT WALL, WITH NOBODY IN THE ROOM. The whole of surface 5's
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

Usage:
  python3 scripts/find-deleted-path-across-backups.py <path>
  python3 scripts/find-deleted-path-across-backups.py <path> --skip box
  python3 scripts/find-deleted-path-across-backups.py <path> --skip localsnapshots
  python3 scripts/find-deleted-path-across-backups.py <path> --repo ~/Projects/nedschorus
  python3 scripts/find-deleted-path-across-backups.py <path> --prompt-for-root

There is no recovery flag: each FOUND line is followed by the exact command
that recovers the content, for you to run.

<path> may be repo-relative ("docs/issues/46-x.md"), absolute, or any trailing
fragment of a path ("dispositions.md"). Fragments match by path suffix.

ONE FORM THE LOCAL-SNAPSHOT SURFACE CANNOT TAKE. A mounted snapshot is tested
with a single `test -e`, which needs a known path; locating a trailing fragment
inside one would need a `find` over the whole volume, and this version does not
run that fan-out on either snapshot surface. So a bare filename makes surface 1
UNAVAILABLE naming that reason, and a relative path with a directory component
is read as repo-relative — if it was meant as a fragment of some other path,
surface 1 tested the wrong place and says which place it tested. git,
transcripts and Timeshift answer the fragment forms.

Exit code: 0 when at least one surface FOUND it. 1 when every surface that ran
was searched and none has it — the only exit that means "stop looking". 3 when
nothing was found and at least one surface could NOT be searched: the same
thing the summary's "Could NOT search" line says, and the usual result of an
unattended run, because reading inside Time Machine needs root — unless the
sudoers rule described above is installed, which is exactly what makes that
surface answerable with nobody in the room. 2 on a usage error. The first
version returned 1 for the third case too, so a wrapper branching on $? was
told "not found" by a run that had searched nothing.
"""

# Deferred annotations keep this runnable on the Mac's system python3, which is
# still 3.9 — the same constraint backup-health-check.py carries.
from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
from pathlib import Path

FOUND = "FOUND"
NOT_FOUND = "NOT FOUND"
UNAVAILABLE = "UNAVAILABLE"

# The run's exit status, in the same three-outcome vocabulary (2 is argparse's).
EXIT_FOUND = 0
EXIT_NOT_FOUND_EVERYWHERE = 1
EXIT_USAGE = 2
EXIT_INCOMPLETE = 3

DEFAULT_BOX_SSH_HOST = "nedlern@ned-box"
DEFAULT_TIMESHIFT_SNAPSHOT_ROOT = "/mnt/backup/timeshift/snapshots"
# Roots on the box under which a repo-relative path is worth testing. The box
# runs one seat per directory, so the same relative path can live under several.
DEFAULT_BOX_SEARCH_ROOTS = (
    "/home/nedlern/Projects/nedschorus",
    "/home/nedlern/agents/*",
)
DEFAULT_TRANSCRIPTS_DIR = "~/.claude/projects"

# How many Time Machine snapshots to open when a password IS available. Each
# mount costs seconds, and the git surface usually narrows the date first.
DEFAULT_TIME_MACHINE_SNAPSHOT_LIMIT = 4

# The ONE directory a Time Machine snapshot is ever mounted on — by this script
# and by every recovery command it prints. It is fixed because
# config/sudoers-mount-apfs-readonly-for-backup-recovery pins this exact path:
# the rule permits /sbin/mount_apfs, the read-only flag, and this mount point,
# so a mount anywhere else does not match it and is asked for a password even
# where the rule is installed. Changing this string without changing that file
# silently puts the password wall back; the test suite fails the pair apart.
TIME_MACHINE_READONLY_MOUNT_POINT = "/private/tmp/nedschorus-backup-readonly-mount"

# What the spoken line calls this tool. `say` reads it aloud, so it is the
# script's name in words rather than its filename — long enough to be
# unmistakable across a room, short enough to finish before he stops listening.
SPOKEN_TOOL_NAME = "find deleted path across backups"

# This Mac's Data volume, which is the one that carries the user-file local
# snapshots: `diskutil apfs listSnapshots /` shows only com.apple.os.update-*
# entries for the ROOT volume, so a builder who queries `/` finds nothing useful
# (re-measured 2026-08-31). mount_apfs takes this mount point directly as its
# source, so this surface resolves no device node and has none to go stale.
MAC_DATA_VOLUME = "/System/Volumes/Data"

# Local snapshots are com.apple.TimeMachine.<stamp>.local. The snapshots on the
# EXTERNAL backup disk end .backup instead, and com.apple.os.update-* entries
# are macOS system-update snapshots of the System volume, which could never hold
# a working file. The suffix is the whole discriminator.
LOCAL_SNAPSHOT_NAME_SUFFIX = ".local"

# A mount point of this surface's own, so that a local-snapshot search and a
# Time Machine search in one run cannot collide on a single directory.
#
# SPELLED /private/tmp, NOT /tmp, AND THE SPELLING IS LOAD-BEARING. /tmp is a
# symlink to /private/tmp on macOS and `mount` reports only the resolved form,
# observed on this Mac as `... on /private/tmp/nedschorus-backup-readonly-mount
# (apfs, ...)`. Under the /tmp spelling this script's own leftover mount never
# compared equal to its own mount point: a mount point left occupied by a killed
# run was filed as one macOS holds, the report said "nothing to mount, nothing
# to release", and every later run searched 1 snapshot of 17 (PR #222 review,
# finding 1). search_local_snapshots normalises its parameter the same way, so a
# caller passing the /tmp spelling gets the same answer.
LOCAL_SNAPSHOT_MOUNT_POINT = "/private/tmp/find-deleted-path-across-backups-local-snapshot-ro"

# Command timeouts. ssh to a sleeping box must not hang a recovery.
SHORT_TIMEOUT_SECONDS = 20
LONG_TIMEOUT_SECONDS = 120

# The box transcript grep's own exit status comes back through ssh: 0 hits,
# 1 no hits, 2 grep failed. This one is ours: ~/.claude/projects is not there.
BOX_TRANSCRIPTS_DIR_MISSING = 3


class SurfaceReport:
    """One surface's answer, in the three-outcome vocabulary above."""

    def __init__(self, surface, status, lines=None, recovery=None):
        self.surface = surface
        self.status = status
        self.lines = list(lines or [])
        self.recovery = list(recovery or [])

    def render(self):
        # Wide enough for the longest surface name, "local snapshots", so the
        # status column stays aligned down the whole report.
        out = ["%-15s %s" % (self.surface, self.status)]
        for line in self.lines:
            out.append("    " + line)
        for command in self.recovery:
            out.append("    $ " + command)
        return "\n".join(out)


def run_command(argv, timeout=SHORT_TIMEOUT_SECONDS, cwd=None):
    """Run a command and return (returncode, stdout, stderr).

    Every external call in this file goes through here, so the tests can replace
    one function instead of stubbing four programs.
    """
    try:
        completed = subprocess.run(
            argv,
            cwd=cwd,
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
    """Drop a literal leading './' — and only that.

    `str.lstrip("./")` strips every leading '.' and '/' CHARACTER, so '.env'
    became 'env' and a request for a dotfile then matched any 'scripts/env'
    in history — a FOUND with a recovery command for the wrong file.
    """
    path = path.strip()
    while path.startswith("./"):
        path = path[2:]
    return path


def path_matches(candidate, wanted):
    """True when `candidate` ends at a path-component boundary with `wanted`."""
    candidate = _strip_dot_slash(candidate)
    wanted = _strip_dot_slash(wanted)
    if candidate == wanted:
        return True
    return candidate.endswith("/" + wanted)


# --------------------------------------------------------------------------
# Surface 1 — local APFS snapshots, on this Mac's own internal disk
# --------------------------------------------------------------------------

def search_local_snapshots(wanted, repo, runner=run_command, mount_point=LOCAL_SNAPSHOT_MOUNT_POINT):
    """Open each of this Mac's local snapshots read-only and test one path in it.

    Searched first because it is the cheapest surface there is and the only
    unprivileged one holding a point-in-time copy of the working tree: no
    network, no external disk, and NO PASSWORD. It answers the case the archive
    surfaces cannot — a file deleted minutes ago that was never committed, and
    anything under a directory Time Machine is configured to exclude.

    Every retained snapshot is searched rather than a chosen few, because NOT
    FOUND here has to mean every one of them was tested, and macOS's own
    retention bounds the walk: roughly a day, two dozen snapshots, ~20 ms each.

    `mount_point` is a parameter so the tests can drive the whole surface
    against a fake volume instead of this machine's real snapshots.
    """
    # /tmp and /private/tmp name one directory and `mount` prints only the
    # second, so the mount point is resolved to the mount table's spelling
    # before anything compares against it. The same normalisation the probe path
    # already gets, for the same reason — see LOCAL_SNAPSHOT_MOUNT_POINT and
    # _below_data_volume.
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
    # A mount point left occupied by an earlier run is the one state that
    # degrades this whole surface: mount_apfs onto an occupied directory exits
    # 77, "Operation not permitted", for every snapshot the walk has to mount
    # for itself. It is detected HERE rather than inferred from the walk,
    # because `stuck` below only ever learns about a release THIS run attempted
    # — a leftover from a killed run contributed no clear command to the
    # recovery at all (PR #222 review, finding 1, second layer).
    #
    # DETECTED AND REPORTED, NEVER CLEARED. This mount point is one fixed path
    # for the whole fleet, so a second seat's live mount is indistinguishable
    # from a dead run's leftover, and unmounting it would break a run in
    # progress. Handing the operator the command is the honest half.
    occupying = sorted(name for name, where in already_mounted.items() if where == mount_point)
    hits = []
    searched = []
    in_place = []
    unsearched = []
    stuck = None
    for snapshot in snapshots:
        if stuck is not None:
            # The walk stops at the first snapshot that will not release. Every
            # later mount onto an occupied mount point fails with exit 77,
            # "Operation not permitted", and letting the walk run on would file
            # every remaining snapshot under that message instead of the real
            # reason. Measured twice on 2026-08-31: an unchecked release left a
            # snapshot mounted and the rest of the run was reported as though
            # each one had refused on its own account.
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
            # Stored as the bare fact. "not reached: " is prepended at the one
            # site that means it — a LATER snapshot the walk stopped short of.
            # Prefixing it here mislabelled the final-return line added below,
            # which is about a snapshot that WAS searched (PR #222, finding 2).
            stuck = "%s stayed mounted on %s — %s" % (snapshot, mount_point, release_failure)

    lines = ["%d local snapshot(s) retained, %d searched — no password needed for any of it"
             % (len(snapshots), len(searched)),
             "tested %s inside each" % probe_path]
    if occupying:
        # Named on EVERY outcome, not only the UNAVAILABLE one. A run whose only
        # readable snapshot is the occupier itself returns FOUND or NOT FOUND
        # with nothing in `unsearched`, and before this line those two paths
        # said nothing at all about the mount point that was wedging the tool.
        lines.append("the mount point %s already had %s on it when this run started, so every snapshot "
                     "this run had to mount for itself was refused — mount_apfs exits 77, \"Operation "
                     "not permitted\", on an occupied mount point"
                     % (mount_point, ", ".join(occupying)))
    if in_place:
        lines.append("%d of them were read where macOS already had them mounted, mounting nothing: %s"
                     % (len(in_place), ", ".join(in_place[:3]) + (", ..." if len(in_place) > 3 else "")))
    for snapshot, reason, repeats in _grouped_by_reason(unsearched):
        # Reported, never classified: a snapshot that would not open was not
        # searched, and the failures reachable from mount_apfs were never
        # enumerated, so its own words go through verbatim.
        lines.append("could not search %s — %s" % (snapshot, reason))
        if repeats:
            lines.append("    ... and %d more snapshot(s) with the same message" % repeats)

    if stuck and not unsearched:
        # The LAST snapshot in the walk is the one case where a failed release
        # reaches no `unsearched` entry to carry it: the loop ends, the guard at
        # the top never runs again, and the run returned a bare NOT FOUND naming
        # neither the snapshot still mounted nor the mount point it sits on —
        # exit 1, which this file's docstring makes the only status meaning
        # "stop looking", from a run that had just wedged its own mount point
        # (PR #222 review, finding 2). The search itself WAS complete, so the
        # status stays NOT FOUND; what was missing was saying this out loud.
        lines.append(stuck)

    # A mount point needing a clear before any command below it can work, from
    # either cause: this run failed to release one, or an earlier run's leftover
    # was already there.
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
        # The one interpretation this surface cannot check. A `test -e` needs a
        # known path, so a relative one is read as repo-relative; if it was
        # meant as a trailing fragment of some other path, the place tested was
        # the wrong one, and naming it is what keeps this an honest NOT FOUND.
        lines.append("(%s was read as a path relative to the repository; a trailing fragment of some "
                     "other path would need a find over the volume, which this surface does not run)" % wanted)
    if unsearched:
        # The command handed back has to be one that can work. A snapshot macOS
        # already holds cannot be mounted a second time — that is what put it in
        # this list — so offering `mount_apfs` for it would be handing over the
        # very command whose refusal is quoted two lines above.
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
    # NOT FOUND, and it stays NOT FOUND even when a mount was left behind: every
    # snapshot WAS searched, and UNAVAILABLE means the surface could not be. The
    # clear command rides along so the operator can undo what this run left.
    return SurfaceReport("local snapshots", NOT_FOUND, lines,
                         [_local_snapshot_clear_mount_point_command(mount_point)] if clear_first else [])


def _local_snapshot_clear_mount_point_command(mount_point):
    """The one command that frees this surface's mount point.

    `diskutil unmount`, not `umount`: see _local_snapshot_probe for the run that
    proved the difference. Named as a function because three call sites and the
    recovery builder all have to emit the identical string.
    """
    return "diskutil unmount %s" % shlex.quote(mount_point)


def _local_snapshot_recovery(snapshot, probe_path, mount_point, clear_first=False, already_at=None):
    """The exact commands that open a snapshot, take the file out, and close it.

    No `sudo`, deliberately and in full: this is the surface whose entire value
    is that reading it costs no password, and a recovery line that asked for one
    anyway would send the reader after a credential nothing here needs.

    A snapshot macOS already has mounted needs no mount and no unmount at all —
    and must not be handed one, because mount_apfs against an already-mounted
    snapshot exits 75, "Resource busy". So the copy comes straight out of where
    it sits. Verified 2026-08-31 by reading a file out of one such mount: 43391
    bytes, byte-identical to the live file.

    When the mount point needs clearing — this run failed to release it, or an
    earlier run's leftover was already on it — the clear comes first, or every
    command below fails on the mount point rather than on the snapshot. The one
    exception is a snapshot sitting on that mount point itself: see below.
    """
    if already_at == mount_point:
        # The snapshot is sitting on this script's OWN mount point, left there by
        # an earlier run — so one line both takes the file out and clears the
        # occupation. A separate clear ahead of it would unmount the very tree
        # the copy reads from (PR #222 review, finding 1).
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
    """[(first snapshot with this reason, the reason, how many more had it)].

    A mount point left occupied by a killed run fails every snapshot with one
    identical message, and two dozen copies of it would bury the rest of the
    report. Grouping collapses the repetition without dropping the count.
    """
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
    """([snapshot names, newest first], failure reason or None).

    `tmutil listlocalsnapshots <volume>` prints a header line and then one name
    per line, unprivileged. Only the .local names are ours — see
    LOCAL_SNAPSHOT_NAME_SUFFIX for what the others are.

    The failure comes back separately rather than as an empty list because
    "tmutil is not on this machine" and "this Mac is keeping no local snapshots"
    are different answers, and only the second of them describes a volume that
    was actually looked at.
    """
    code, out, stderr = runner(["tmutil", "listlocalsnapshots", MAC_DATA_VOLUME])
    if code != 0:
        first = stderr.strip().splitlines()[0] if stderr.strip() else "tmutil exited %s" % code
        return [], first
    names = {line.strip() for line in out.splitlines()
             if line.strip().endswith(LOCAL_SNAPSHOT_NAME_SUFFIX)}
    # The names embed an ISO-ish timestamp, so lexical order is time order.
    return sorted(names, reverse=True), None


def _local_snapshots_already_mounted(runner):
    """{snapshot name: the mount point macOS already has it on}.

    macOS mounts local snapshots for its own use, under
    /Volumes/com.apple.TimeMachine.localsnapshots, and a snapshot that is
    already mounted cannot be mounted a second time: mount_apfs exits 75,
    "Resource busy" (measured 2026-08-31). The snapshot most likely to be in
    that state is the NEWEST one — exactly the one the "I deleted it minutes
    ago" case needs — so reading it where it already sits is not a nicety. On
    2026-08-31 the two newest snapshots were both in that state within the hour.

    Such a mount point IS the Data volume's root, so a path inside it has the
    same shape as one inside a mount of this script's own, and reading it costs
    nothing: verified that day by copying a 43391-byte file out of one,
    byte-identical to the live original.

    Some of these mounts are stale. Four on 2026-08-31 were listed by `mount`
    while their mount points did not resolve at all, so the caller tests the
    mount point before trusting it and falls back to mounting for itself; those
    four then report Resource busy verbatim, which is the honest answer for a
    snapshot nothing here can reach. They are macOS's own state and this script
    does not try to clear them.

    `mount` prints `<what>@<device> on <mount point> (<options>)`. The options
    parenthesis is last, so splitting the tail off is safe for a mount point
    that itself contains " (".
    """
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
    """The absolute path to test inside a mounted snapshot: (path, why-not lines).

    A mounted snapshot of the Data volume exposes this machine's own absolute
    layout at the mount point — /Users, /private and the rest — so testing a
    known path is one `test -e` against <mount point><absolute path> (verified
    2026-08-31 by mounting one and listing it).

    Three normalisations, each of which is a false NOT FOUND when it is skipped:

      * /tmp, /etc and /var are symlinks that live on the SYSTEM volume. The
        Data volume's snapshot root has no such entries at all — checked, its
        top level is Applications, cores, home, Library, mnt, ... private,
        System, Users, usr — so an unnormalised /tmp/x can never match a file
        that is genuinely in there. realpath rewrites them to /private/...
      * /System/Volumes/Data/Users/... is the firmlink spelling of /Users/...,
        and realpath does NOT collapse it (checked 2026-08-31), so the prefix
        comes off here instead.
      * A repo-relative path — the form the usage block documents first — is
        absolute only once the repository's top level is prepended.

    A bare filename has no path to test, and finding it would need a `find`
    across the whole volume rather than one `test -e`; this version runs that
    fan-out on neither snapshot surface, so it returns None with the reason.
    """
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
    """An absolute path as a snapshot of the Data volume spells it."""
    path = os.path.realpath(path)
    if path == MAC_DATA_VOLUME:
        return "/"
    if path.startswith(MAC_DATA_VOLUME + "/"):
        return path[len(MAC_DATA_VOLUME):]
    return path


def _local_snapshot_probe(snapshot, probe_path, mount_point, runner, already_mounted=None):
    """Read one local snapshot and test one path in it.

    Returns (outcome, where, release failure or None, read in place):
      ("hit", mount point, ...)   — the path is in this snapshot, read there
      ("miss", mount point, ...)  — read and tested; the path is not in it
      ("unmounted", reason, ...)  — mount_apfs refused; this was NOT searched

    The fourth value says whether the snapshot was read WHERE IT ALREADY SAT
    rather than mounted here. The caller cannot infer it from `where`: a
    leftover on this script's own mount point and a snapshot this run mounted
    itself both report `where == mount_point`, and only the first is still
    mounted when the report is written (PR #222 review, finding 1).

    `already_mounted` is where macOS itself has this snapshot, when it has it.
    That mount is read in place — no mount, no release — both because it is
    free and because mounting an already-mounted snapshot cannot work. A stale
    entry (the mount point does not resolve) falls through to mounting for
    ourselves, which then reports its own refusal verbatim.

    No sudo anywhere, which is this surface's whole point: mount_apfs against
    this Mac's INTERNAL Data volume succeeds as the ordinary user, and so does
    releasing it (measured 2026-08-31: about 7 ms to mount, 10 ms to release).
    The external backup volume is the opposite case and Time Machine's probe
    below still needs a password for it — the difference is the volume, not the
    command.

    Any nonzero exit from mount_apfs is reported verbatim and never classified.
    The failures reachable here were not enumerated: an already-occupied mount
    point gives exit 77 "Operation not permitted" and a snapshot macOS itself
    already has mounted gives exit 75 "Resource busy" (both measured
    2026-08-31), and others exist. A snapshot that never opened was not
    searched, and rendering that as "not there" is the conflation this file
    exists to refuse.

    THE RELEASE IS `diskutil unmount`, NOT `umount`, AND ITS EXIT CODE IS
    CHECKED. Plain `umount` intermittently fails on a freshly mounted snapshot
    with "Resource busy -- try 'diskutil unmount'" — macOS's own words, seen
    twice on 2026-08-31 partway through a walk of 18 snapshots. The first
    version ignored that exit code, so the snapshot stayed mounted, every later
    mount hit the occupied mount point, and a run that had searched six
    snapshots reported the other twelve as though each had refused on its own
    account. `diskutil unmount` cleared the same mount immediately. The release
    is in a `finally` for the same reason the check exists: a snapshot this
    script leaves mounted makes its own mount point refuse every later run.
    """
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


# --------------------------------------------------------------------------
# Surface 2 — git
# --------------------------------------------------------------------------

def search_git(wanted, repo, runner=run_command):
    """Search every ref's full history, including paths deleted long ago.

    `git log --all --full-history` is the load-bearing pair: --all reaches refs
    that HEAD cannot, and --full-history stops history simplification from
    pruning the very commits that touched a since-deleted path.
    """
    code, _, stderr = runner(["git", "-C", repo, "rev-parse", "--git-dir"])
    if code != 0:
        return SurfaceReport("git", UNAVAILABLE, ["%s is not a git repository (%s)" % (repo, stderr.strip())])

    wanted, toplevel = _repo_relative_form(wanted, repo, runner)
    if wanted.startswith("/"):
        # git can only be asked about paths inside its own work tree, and an
        # absolute path that is not under it was not converted above.
        return SurfaceReport(
            "git",
            UNAVAILABLE,
            ["%s is outside %s, so git was not asked for it" % (wanted, toplevel or repo),
             "re-run with the path relative to the repository, or a trailing fragment of it"],
        )

    lines = []
    recovery = []
    dates_held = []
    try:
        paths = _git_candidate_paths(wanted, repo, runner)
        if not paths:
            return SurfaceReport("git", NOT_FOUND, ["no ref in %s has ever contained a path matching %r" % (repo, wanted)])
        for path in paths:
            commit = _git_newest_commit_holding(path, repo, runner)
            if commit is None:
                continue
            sha, date, subject = commit
            lines.append("%s" % path)
            lines.append("    last held by %s (%s) %s" % (sha[:9], date, subject[:70]))
            recovery.append("git -C %s show %s:%s" % (shlex.quote(repo), sha[:9], shlex.quote(path)))
            dates_held.append(date)
    except _GitCommandFailed as failure:
        return SurfaceReport("git", UNAVAILABLE, ["git failed while searching %s — %s" % (repo, failure)])

    if not lines:
        return SurfaceReport("git", NOT_FOUND, ["matching paths appear in history, but neither the commits that "
                                                "touched them nor those commits' parents hold the content"])

    report = SurfaceReport("git", FOUND, lines, recovery)
    # The newest date on which git still had the file bounds where to look in
    # the filesystem backups: any snapshot after it is unlikely to help.
    report.newest_date_held = max(dates_held) if dates_held else None
    return report


def _repo_relative_form(wanted, repo, runner=run_command):
    """(path to search for, the repository's top level or None).

    An absolute path inside `repo` comes back repo-relative. That is the only
    form git can address a blob by — `git log -- /abs/path` succeeds, but
    `cat-file -e <sha>:/abs/path` fails for every commit, so the first version
    answered NOT FOUND, "no commit still holds their content", for a file git
    had the whole time. It is also the form the other surfaces search most
    widely: the box roots for Timeshift, a suffix match for Time Machine.
    A relative path, an absolute path outside the repository, and any path
    when `repo` is not a repository all come back as given.
    """
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


def _git_candidate_paths(wanted, repo, runner):
    """Exact pathspec first; fall back to a suffix scan of every path git knows."""
    code, out, _ = runner(["git", "-C", repo, "log", "--all", "--full-history", "-1", "--format=%H", "--", wanted])
    if code == 0 and out.strip():
        return [wanted]

    code, out, stderr = runner(
        ["git", "-C", repo, "log", "--all", "--full-history", "--name-only", "--format="],
        timeout=LONG_TIMEOUT_SECONDS,
    )
    if code != 0:
        # An empty list here would render as "no ref has ever contained a
        # path matching", which is a NOT FOUND for a search that did not run.
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
    """A git call the surface depends on returned non-zero; the text is its stderr."""


def _git_newest_commit_holding(path, repo, runner):
    """The newest commit whose tree actually contains `path`: (sha, date, subject), or None.

    `git log -- <path>` lists the commits that TOUCHED the path, newest first,
    and the newest of those is usually the one that deleted it. The first
    version walked that list back to the first commit whose tree still had
    the blob — which is the last MODIFICATION, not the last commit that held
    the file. For the file this tool was built for that gave 2026-08-12; the
    deletion was 2026-08-14 and the merge just before it still held the blob,
    so the Time Machine candidate chosen from the date was one snapshot too
    old, on the unprivileged path too, under a confident label.

    A commit that deleted the path has a parent whose tree still holds it, on
    the side the file came from — testing each parent rather than `<sha>^` is
    what survives merges. The candidates are therefore every touching commit
    that holds the blob and every holding parent of a touching commit that
    does not; the newest by commit time wins. The list is newest-first and a
    parent is never newer than its child, so the walk stops at the first line
    older than the best candidate so far.

    Raises _GitCommandFailed when git itself fails, so the caller reports
    UNAVAILABLE rather than a NOT FOUND for a search that did not run.
    """
    code, out, stderr = runner(
        ["git", "-C", repo, "log", "--all", "--full-history", "--format=%H|%P|%ct|%ad|%s", "--date=short", "--", path],
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


# --------------------------------------------------------------------------
# Surface 3 — agent transcripts, on this Mac and on the box
# --------------------------------------------------------------------------

def search_transcripts(wanted, transcripts_dir, box_ssh_host, runner=run_command):
    """Grep session JSONL for the path string, locally and on the box.

    A transcript holds what a tool call returned, so a file read by any agent
    survives there verbatim — the recovery route the user pointed out on
    2026-08-23 ("you almost always can find missing stuff by looking in the
    agents jsonl"), and the only one of the four that survives a repo history
    rewrite.
    """
    lines = []
    recovery = []
    statuses = []

    local_dir = Path(os.path.expanduser(transcripts_dir))
    if not local_dir.is_dir():
        lines.append("this Mac: %s does not exist" % local_dir)
        statuses.append(UNAVAILABLE)
    else:
        code, out, _ = runner(
            ["grep", "-rl", "--include=*.jsonl", "-F", wanted, str(local_dir)],
            timeout=LONG_TIMEOUT_SECONDS,
        )
        hits = [h for h in out.splitlines() if h.strip()]
        if hits:
            lines.append("this Mac: %d session transcript(s) mention it" % len(hits))
            for hit in hits[:5]:
                lines.append("    " + hit)
            if len(hits) > 5:
                lines.append("    ... and %d more" % (len(hits) - 5))
            recovery.append("grep -o '.\\{0,400\\}%s.\\{0,2000\\}' %s | head" % (wanted, shlex.quote(hits[0])))
            statuses.append(FOUND)
        elif code in (0, 1):
            lines.append("this Mac: searched %s, no transcript mentions it" % local_dir)
            statuses.append(NOT_FOUND)
        else:
            lines.append("this Mac: grep failed over %s" % local_dir)
            statuses.append(UNAVAILABLE)

    if box_ssh_host:
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
            recovery.append("ssh %s \"grep -o '.\\{0,400\\}%s.\\{0,2000\\}' %s\" | head" % (box_ssh_host, wanted, shlex.quote(hits[0])))
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
        # The searching agent's own transcript matches as soon as it types the
        # path, so a lone hit is often this session quoting itself rather than a
        # surviving copy of the content. True of a box hit as much as a Mac one.
        lines.append("(a session's own transcript matches merely because the path was typed in it —")
        lines.append(" check that a hit actually contains the CONTENT before calling it recovered)")
    return SurfaceReport("transcripts", _combine(statuses), lines, recovery)


def _box_transcript_grep_script(wanted):
    """The shell that runs on the box; its exit status is the grep's own.

    The first version was `grep ... 2>/dev/null | head -20`, and a pipeline's
    status is its LAST command's: `head` succeeding replaced `grep` failing, so
    a missing or unreadable ~/.claude/projects came back as exit 0 with empty
    output and the caller said it had searched it. Never pipe a command whose
    failure is supposed to be detected. The directory is tested explicitly,
    grep's stderr is kept, and the hit list is capped by the caller instead.
    """
    return "\n".join([
        'd="$HOME/.claude/projects"',
        'if [ ! -d "$d" ]; then echo "$d does not exist" >&2; exit %d; fi' % BOX_TRANSCRIPTS_DIR_MISSING,
        "exec grep -rl --include='*.jsonl' -F %s \"$d\"" % shlex.quote(wanted),
    ])


# --------------------------------------------------------------------------
# Surface 4 — Timeshift on the box
# --------------------------------------------------------------------------

def search_timeshift(wanted, box_ssh_host, snapshot_root, search_roots, runner=run_command):
    """Test the path under every Timeshift snapshot on the box.

    Timeshift stores a snapshot as an ordinary directory tree rooted at
    <snapshot>/localhost/<the absolute path it had>, world-readable (verified
    2026-08-23: drwxr-xr-x, and passwordless sudo exists there anyway). So this
    surface needs no privilege at all — the opposite of Time Machine.

    A repo-relative path is tested under each configured root because the same
    relative path exists under several seats on the box. It is tested exactly
    first, and when that misses the root is searched by path suffix, the way
    git's suffix scan and Time Machine's `find -path` already treat a trailing
    fragment. The first version only ever tested <root>/<wanted>, so the
    documented fragment form ("dispositions.md") could not hit, and the
    surface said "searched every snapshot" for a file in every snapshot.
    """
    if not box_ssh_host:
        return SurfaceReport("timeshift", UNAVAILABLE, ["not searched — no ssh host given (--skip box, or an empty --box-ssh-host)"])

    code, out, stderr = runner(
        ["ssh", "-o", "ConnectTimeout=10", "-o", "BatchMode=yes", box_ssh_host,
         _timeshift_probe_script(wanted, snapshot_root, search_roots)],
        timeout=LONG_TIMEOUT_SECONDS,
    )
    first_error = stderr.strip().splitlines()[0] if stderr.strip() else ""
    if code == 255:
        return SurfaceReport(
            "timeshift",
            UNAVAILABLE,
            ["the box (%s) is unreachable — %s" % (box_ssh_host, first_error or "ssh failed"),
             "the snapshots are fine; this machine just cannot see them right now"],
        )
    if code != 0:
        # The runner's 124 on timeout, or the script itself failing. Falling
        # through would count the snapshots it never reached as searched.
        return SurfaceReport(
            "timeshift",
            UNAVAILABLE,
            ["the search on %s did not complete (exit %s) — %s" % (box_ssh_host, code, first_error or "no error text")],
        )
    if "NOROOT" in out:
        return SurfaceReport("timeshift", UNAVAILABLE, ["%s does not exist on %s — is the backup drive mounted?" % (snapshot_root, box_ssh_host)])

    hits = sorted({line[4:].strip() for line in out.splitlines() if line.startswith("HIT ")}, reverse=True)
    unsearched = [line[10:].strip() for line in out.splitlines() if line.startswith("PROBEFAIL ")]
    if not hits:
        if unsearched:
            return SurfaceReport(
                "timeshift",
                UNAVAILABLE,
                ["find failed under %d snapshot director%s on %s, first: %s"
                 % (len(unsearched), "y" if len(unsearched) == 1 else "ies", box_ssh_host, unsearched[0]),
                 "the rest were searched and do not have it; those %d were not searched" % len(unsearched)],
            )
        return SurfaceReport("timeshift", NOT_FOUND, ["searched every snapshot under %s on %s" % (snapshot_root, box_ssh_host)])

    lines = ["%d snapshot(s) on %s still have it, newest first:" % (len(hits), box_ssh_host)]
    for hit in hits[:5]:
        lines.append("    " + hit)
    if len(hits) > 5:
        lines.append("    ... and %d older" % (len(hits) - 5))
    if unsearched:
        lines.append("(find failed under %d snapshot director%s, first: %s — those were not searched)"
                     % (len(unsearched), "y" if len(unsearched) == 1 else "ies", unsearched[0]))
    recovery = ["scp %s:%s ." % (box_ssh_host, shlex.quote(hits[0]))]
    return SurfaceReport("timeshift", FOUND, lines, recovery)


def _timeshift_probe_script(wanted, snapshot_root, search_roots):
    """The shell that runs on the box. Prints HIT <path> per match, NOROOT if
    the snapshot root is absent, PROBEFAIL <dir> when a find could not finish.

    Quote the CALLER's path, never the roots. The roots are constants that
    deliberately carry a `*` (one seat per directory on the box), and
    shlex.quote would wrap that glob in single quotes, making it a literal
    asterisk that matches nothing — a surface reporting "searched every
    snapshot" while never having looked at the seat directories. An unquoted
    `*` still expands when the rest of the word is quoted. The find pattern
    is the opposite case: `*/<wanted>` must reach find as ONE quoted word, or
    the shell expands the `*` against its own cwd first.
    """
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


# --------------------------------------------------------------------------
# Surface 5 — Time Machine on the Mac's EXTERNAL backup disk
# --------------------------------------------------------------------------

def search_time_machine(wanted, newest_date_held=None, snapshot_limit=DEFAULT_TIME_MACHINE_SNAPSHOT_LIMIT,
                        runner=run_command, prompt_for_root=False):
    """Enumerate Time Machine snapshots, and read inside them when root is reachable.

    The measured split (2026-08-23): `tmutil` and `diskutil apfs listSnapshots`
    both answer unprivileged, but `sudo mount_apfs -o ro -s <snapshot>` refuses
    without a password, so the CONTENT of a snapshot is unreachable to an
    unattended agent. This function therefore always enumerates, tries a
    non-interactive `sudo -n` (which succeeds when the user has recently
    authenticated), and otherwise hands back the exact command to run rather
    than reporting an empty search.

    THREE WAYS ROOT CAN BE REACHABLE, and the code takes whichever it is given:

      * the sudoers rule beside this script is installed, in which case the
        `sudo -n` probe below succeeds outright for this one mount and the
        wall is never met at all — the unattended case this whole thing exists
        for;
      * a credential is already cached from something the person ran a moment
        ago, which is what the probe originally tested for;
      * `prompt_for_root` is set, meaning a person is at the terminal and has
        asked to be prompted. Then the wall is not a stopping point: the mount
        runs as plain `sudo`, which prompts on the tty, and the snapshots are
        searched. The flag drops `-n` rather than warming the credential with
        `sudo -v` first, because `-v` validates for EVERY command the user may
        run and so prompts even where the sudoers rule would have made this
        one mount free.

    When none of the three holds the surface is UNAVAILABLE, carrying the
    resolved command — and the report is marked `root_credential_needed` so
    the assembly step can decide whether this is worth waking a human for.
    """
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
        # Attached but not mounted — the state the user hits when the disk sleeps
        # or is replugged. Mounting a disk he already attached is how you read a
        # backup; it does not modify one.
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
    if can_sudo != 0 and not prompt_for_root:
        wall = SurfaceReport(
            "time machine",
            UNAVAILABLE,
            ["%d snapshots present, %s .. %s — enumerated fine, but reading INSIDE one needs root, "
             "and no credential is cached, so it needs your password"
             % (len(snapshots), snapshots[-1], snapshots[0]),
             "this is a real wall, not an empty result: the file may well be in there",
             "installing config/sudoers-mount-apfs-readonly-for-backup-recovery removes this wall for "
             "this one read-only mount and nothing else, so an unattended run can cross it",
             "at a terminal, --prompt-for-root runs the mount below from here instead of printing it",
             _candidate_line(candidates[0], dated_by_git),
             _alternative_line(snapshots, candidates[0], dated_by_git)],
            _time_machine_manual_recovery(candidates[0], device),
        )
        # Read by the assembly step, which is the only place that can see
        # whether the free surfaces missed. Nothing else in the run knows that
        # this surface stopped at a credential rather than at a missing disk.
        wall.root_credential_needed = True
        wall.snapshots_enumerated = list(snapshots)
        return wall

    hits = []
    searched = []
    unsearched = []
    for snapshot in candidates:
        outcome, detail = _time_machine_probe(snapshot, device, wanted, runner, prompt_for_root)
        if outcome == "hit":
            hits.append((snapshot, detail))
            searched.append(snapshot)
        elif outcome == "miss":
            searched.append(snapshot)
        else:
            unsearched.append((snapshot, detail))
    how = "with an already-warm sudo" if can_sudo == 0 else "after --prompt-for-root asked at the terminal"
    lines = ["%d snapshots present; %d of %d candidates searched %s"
             % (len(snapshots), len(searched), len(candidates), how)]
    for snapshot, reason in unsearched:
        lines.append("could not search %s — %s" % (snapshot, reason))
    if hits:
        for snapshot, hit in hits:
            lines.append("%s holds %s" % (snapshot, hit))
        return SurfaceReport("time machine", FOUND, lines,
                             _time_machine_manual_recovery(hits[0][0], device, hits[0][1]))
    if searched:
        lines.append("searched %s and did not find it" % ", ".join(searched))
    if unsearched:
        # A snapshot that would not open was not searched; saying "did not
        # find it" about it is the conflation this file's contract forbids.
        return SurfaceReport("time machine", UNAVAILABLE, lines,
                             _time_machine_manual_recovery(unsearched[0][0], device))
    return SurfaceReport("time machine", NOT_FOUND, lines)


def _time_machine_manual_recovery(snapshot, device, path_inside=None):
    """The exact commands that open one Time Machine snapshot and close it again.

    TIME_MACHINE_READONLY_MOUNT_POINT in every line, and the same directory the
    probe below mounts on, because the sudoers rule beside this script pins that
    one path: a printed command naming anywhere else asks for a password on a
    machine where the rule would have made it free, and a reader who follows a
    printed command that differs from what the script itself runs is debugging
    two things at once.

    THE RELEASE IS `diskutil unmount` AND CARRIES NO SUDO. Unmounting needs no
    privilege at all, so `sudo umount` asked for a password to undo something
    that never needed one; and plain `umount` does not reliably release a
    freshly mounted snapshot — it fails with "Resource busy — try 'diskutil
    unmount'", macOS's own words, measured twice on 2026-08-31 on the
    local-snapshot surface, where an ignored release left the mount point
    occupied and every later snapshot failed against it.
    """
    mount = shlex.quote(TIME_MACHINE_READONLY_MOUNT_POINT)
    open_it = "mkdir -p %s && sudo mount_apfs -o ro -s %s %s %s" % (mount, snapshot, device, mount)
    if path_inside:
        return [open_it,
                "cp %s . && diskutil unmount %s"
                % (shlex.quote(TIME_MACHINE_READONLY_MOUNT_POINT + path_inside), mount)]
    return [open_it + " && ls %s" % mount,
            "# then look for the path under %s, and: diskutil unmount %s"
            % (TIME_MACHINE_READONLY_MOUNT_POINT, mount)]


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
    """Resolve (device node, mount point, attached) from the volume NAME.

    Never from a remembered device node: /dev/disk5s2 was the backup volume on
    2026-08-23 and a replug can renumber it.
    """
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
    # Snapshot names embed an ISO-ish timestamp, so lexical order is time order.
    return sorted(names, reverse=True)


def _time_machine_candidates(snapshots, newest_date_held, limit):
    """Prefer snapshots from around the last date git still had the file.

    When the git surface reports "last held on 2026-08-13", the snapshot that
    matters is the newest one at or before that date — not the newest overall,
    which is from after the deletion and will not have it.

    This is deliberately the newest snapshot git can PROVE predates the
    deletion, which is a safe bet rather than the optimal one: the file
    normally survived on disk for a while after that commit, so a slightly
    newer snapshot often holds it too. The report names that next-newer
    snapshot as the alternative rather than silently narrowing the search.
    """
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
    """Point at the next snapshot worth trying, in the direction that can help.

    With a git date the risk is that the candidate predates the file's creation,
    so the next NEWER one is the alternative. Without a git date the candidate is
    the newest on the disk and the risk is the opposite — it postdates the
    deletion — so the alternative has to be OLDER, and walking newer is useless.
    """
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
    """'com.apple.TimeMachine.2026-08-13-183101.backup' -> '20260813'."""
    digits = "".join(ch for ch in snapshot_name if ch.isdigit())
    return digits[:8]


def _snapshot_timestamp(snapshot_name):
    """'com.apple.TimeMachine.2026-08-13-183101.backup' -> '20260813183101', or None.

    The FULL stamp, to the second, and never the date above. A date cannot
    order a snapshot against a deletion that happened the same day, and
    same-day is the ordinary case rather than an edge: 7 of the 62 backups on
    the measured volume share 2026-08-23. The speech gate compares against a
    git commit timestamp rendered in the same 14 digits, so the comparison is
    a plain string comparison between two fixed-width local-time stamps.

    None when the name carries no such stamp, so a snapshot this cannot place
    in time is never counted as predating anything.
    """
    digits = "".join(ch for ch in snapshot_name if ch.isdigit())
    return digits[:14] if len(digits) >= 14 else None


def _time_machine_probe(snapshot, device, wanted, runner, prompt_for_root=False):
    """Open one snapshot read-only and look for `wanted` in it.

    Returns (outcome, detail):
      ("hit", path inside the snapshot)   — the file is there
      ("miss", None)                      — mounted and searched, not there
      ("unmounted", reason)               — mount_apfs refused; NOT searched
      ("unreadable", reason)              — mounted, but find failed; NOT searched

    The first version returned a bare None for both a mount failure and an
    absent file, and the caller rendered both as "searched ... and did not
    find it". A snapshot that never opened was not searched.

    THE MOUNT POINT IS THE FIXED ONE, and the argv is exactly the shape the
    sudoers rule permits — `mount_apfs -o ro -s <snapshot> <device>
    <TIME_MACHINE_READONLY_MOUNT_POINT>`. sudoers matches argument for
    argument, so reordering the flags or mounting elsewhere puts the password
    prompt back on a machine where the rule is installed.

    `prompt_for_root` drops sudo's `-n`, which is the whole of what the flag
    does here: with `-n` sudo fails rather than ask, which is right for an
    unattended run; without it sudo prompts on the tty — and on a machine with
    the sudoers rule installed it does not have to ask at all, because the
    command matches a NOPASSWD entry either way.
    """
    mount_point = TIME_MACHINE_READONLY_MOUNT_POINT
    runner(["mkdir", "-p", mount_point])
    sudo = ["sudo"] if prompt_for_root else ["sudo", "-n"]
    code, _, stderr = runner(sudo + ["mount_apfs", "-o", "ro", "-s", snapshot, device, mount_point], timeout=LONG_TIMEOUT_SECONDS)
    if code != 0:
        first = stderr.strip().splitlines()[0] if stderr.strip() else "exit %s" % code
        return "unmounted", "mount_apfs said: %s" % first
    try:
        if wanted.startswith("/"):
            probe = mount_point + wanted
            exists, _, _ = runner(["test", "-e", probe])
            return ("hit", wanted) if exists == 0 else ("miss", None)
        # Assumes a mounted Time Machine snapshot exposes /Users at its root.
        # That is the documented layout, but it is UNVERIFIED here: confirming it
        # needs the password this whole branch exists because we do not have.
        code, out, stderr = runner(
            ["find", mount_point + "/Users", "-path", "*/" + wanted, "-maxdepth", "12"],
            timeout=LONG_TIMEOUT_SECONDS,
        )
        for line in out.splitlines():
            if line.strip():
                return "hit", line.strip()[len(mount_point):]
        if code != 0:
            first = stderr.strip().splitlines()[0] if stderr.strip() else "exit %s" % code
            return "unreadable", "find said: %s" % first
        return "miss", None
    finally:
        # `diskutil unmount`, unprivileged, for the reason spelled out in
        # _time_machine_manual_recovery: plain `umount` does not reliably
        # release a freshly mounted snapshot, and this mount point is fixed, so
        # one snapshot left mounted breaks every later run of this script.
        runner(["diskutil", "unmount", mount_point], timeout=LONG_TIMEOUT_SECONDS)


# --------------------------------------------------------------------------
# The one channel to the user that does not run through an agent
# --------------------------------------------------------------------------

def announce_root_password_wall_by_speech(wanted, reports, repo, skip, runner):
    """Speak one sentence when a person is genuinely needed. Return it, or None.

    WHY SPEECH AT ALL. On 2026-08-31 this script's Time Machine surface said
    "needs your password" and the agent reading it put that four paragraphs
    into a long message; the user never saw it. Printing louder cannot fix
    that, because the failure was in the relay and not in the wording. `say`
    reaches the room directly. It is the user's own convention for the same
    reason: he works in other seats' terminals and does not read transcripts.

    It is spoken before the report is printed, and blocks for the few seconds
    the sentence takes. That is deliberate rather than backgrounded: a spoken
    line whose process is orphaned when the script exits is a line nobody
    hears, and this path is rare enough that a few seconds cost nothing.

    NO PLATFORM GUARD, and that is not an oversight. Nothing can reach this
    call except through a report that `tmutil destinationinfo` and `diskutil
    info` both answered, which is macOS by construction; ned-box has no Time
    Machine destination and never gets a wall report to speak about.
    """
    sentence = speech_line_when_root_password_is_needed(wanted, reports, repo, skip, runner)
    if sentence is None:
        return None
    runner(["say", sentence])
    return sentence


def speech_line_when_root_password_is_needed(wanted, reports, repo, skip, runner):
    """The sentence to speak, or None when he must not be disturbed.

    FOUR CONDITIONS, ALL REQUIRED, because a channel that reaches the room is
    only worth having while it stays rare. Any one of them failing is silence.

      1. Nothing else found it. A run whose git or transcripts surface came
         back FOUND needs no password and no person: the file is already
         recoverable and the report says how. UNAVAILABLE elsewhere does NOT
         excuse the wall — a Timeshift surface that could not be reached
         because the box is asleep leaves him just as needed, so the test is
         "did any surface FIND it", not "was every surface searched".
      2. The Time Machine surface stopped at the credential rather than at
         anything else. That is the `root_credential_needed` mark, which the
         surface sets only after it has enumerated snapshots on an attached,
         mounted disk and `sudo -n true` came back non-zero. It carries
         conditions 3 and "there is something in there to search" in one flag:
         a missing disk, an unconfigured destination or a warm credential all
         leave it unset, and `sudo -n` exits non-zero WITHOUT prompting, so
         probing for it costs nothing and can never summon a password window
         by accident.
      3. A backup exists whose timestamp predates the deletion. Without one,
         the password cannot help and sending him after it would waste his
         walk. The bound is the DELETION commit's timestamp, not the newest
         commit whose tree still holds the blob — that one is usually older
         than the deletion and would rule out backups that do have the file.
         A PATH GIT NEVER TRACKED CANNOT SATISFY THIS, and a builder reading
         only the list above will not derive it: no deletion commit means no
         bound, no bound means no backup can be shown to predate anything, so
         the line never speaks for a never-committed file. That is the right
         answer rather than a gap — a never-committed file is what local
         snapshots and transcripts are there to answer, and Time Machine
         excludes the scratchpad those files mostly live in anyway.
      4. The search is for a known path, not a bare filename. A fragment
         cannot be tested with one `stat` inside a snapshot; it needs a `find`
         across the whole tree, which no snapshot surface here runs. Waking
         him for a search that could not use the mount is the worst of both.

    Condition 2 is also why `--prompt-for-root` is silent: with the flag the
    surface walks past the wall and never sets the mark, which is correct —
    the person is already at the terminal, and sudo is about to ask him there.
    """
    wall = next((r for r in reports if getattr(r, "root_credential_needed", False)), None)
    if wall is None:
        return None
    if any(r.status == FOUND for r in reports):
        return None
    stripped = _strip_dot_slash(wanted)
    if "/" not in stripped:
        return None
    if "git" in skip:
        # No git surface ran, so there is no deletion commit to bound with, and
        # asking git anyway would contradict the flag the caller typed.
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
    """When the deletion of `wanted` was committed, as '20260813183101', or None.

    `--diff-filter=D` is the whole point: it selects the commit that REMOVED
    the path, which is the moment after which a backup can no longer hold it.
    `--all --full-history` gives it the same reach the git surface has, so a
    path deleted on a branch HEAD cannot see is still bounded.

    The date is asked for as local-time digits rather than %cI, so the
    comparison against a snapshot name is between two fixed-width strings in
    one coordinate system — snapshot names carry local time — with no
    timezone-offset parsing on the system python this file has to run under.
    """
    code, out, _ = runner(["git", "-C", repo, "log", "--all", "--full-history", "-1",
                           "--diff-filter=D", "--date=format-local:%Y%m%d%H%M%S",
                           "--format=%cd", "--", wanted])
    if code != 0 or not out.strip():
        return None
    stamp = out.strip().splitlines()[0].strip()
    return stamp if len(stamp) == 14 and stamp.isdigit() else None


# --------------------------------------------------------------------------
# Assembly
# --------------------------------------------------------------------------

def _combine(statuses):
    """One status for a surface made of several parts, in the contract's terms.

    FOUND anywhere is FOUND. Otherwise, one part that could not be searched
    makes the whole surface UNAVAILABLE: NOT FOUND means "genuinely searched
    and does not have it", and a surface half of which was never looked at
    cannot claim that. The first version ranked NOT FOUND above UNAVAILABLE,
    so a transcripts search with the Mac directory missing and the box grep
    empty rendered NOT FOUND and dropped out of the "Could NOT search" line.
    """
    if FOUND in statuses:
        return FOUND
    if UNAVAILABLE in statuses or not statuses:
        return UNAVAILABLE
    return NOT_FOUND


def build_report(wanted, repo, transcripts_dir, box_ssh_host, snapshot_root, search_roots, skip=(),
                 runner=run_command, prompt_for_root=False):
    reports = []
    newest_date_held = None

    if "localsnapshots" not in skip:
        # First, on the design's ruling: no network, no privilege, and it is the
        # surface that answers "I deleted it minutes ago" outright. It takes no
        # date hint from git — every retained snapshot is cheap enough to search,
        # so there is nothing for a bound to narrow.
        reports.append(search_local_snapshots(wanted, repo, runner))
    if "git" not in skip:
        git_report = search_git(wanted, repo, runner)
        newest_date_held = getattr(git_report, "newest_date_held", None)
        reports.append(git_report)
    if "box" in skip:
        # Nothing on the box is contacted: the transcripts surface's box half
        # as well as Timeshift. The reason to type --skip box is that the box
        # is asleep, and an ssh with ConnectTimeout=10 inside a 120-second
        # window is exactly the wait the flag exists to avoid.
        box_ssh_host = ""
    if "transcripts" not in skip:
        reports.append(search_transcripts(wanted, transcripts_dir, box_ssh_host, runner))
    if "box" not in skip and "timeshift" not in skip:
        reports.append(search_timeshift(wanted, box_ssh_host, snapshot_root, search_roots, runner))
    if "timemachine" not in skip:
        reports.append(search_time_machine(wanted, newest_date_held, runner=runner,
                                           prompt_for_root=prompt_for_root))
    # Here rather than in main(), because this is the first point at which every
    # surface's answer exists, and it is what the designed recovery hook will
    # call: the hook assembles a report, it does not run the command line.
    announce_root_password_wall_by_speech(wanted, reports, repo, skip, runner)
    return reports


def render(wanted, reports):
    out = ["Searching every history this fleet keeps for: %s" % wanted, ""]
    for report in reports:
        out.append(report.render())
        out.append("")
    found = [r for r in reports if r.status == FOUND]
    blocked = [r for r in reports if r.status == UNAVAILABLE]
    if found:
        out.append("Recoverable from: %s." % ", ".join(r.surface for r in found))
    else:
        out.append("No surface that could be searched has it.")
    if blocked:
        out.append("Could NOT search: %s — see each one's line above; those are not 'not found'."
                   % ", ".join(r.surface for r in blocked))
    return "\n".join(out)


def main(argv=None, runner=run_command):
    parser = argparse.ArgumentParser(
        description="Find a deleted path across this Mac's local snapshots, git, agent transcripts, "
                    "Timeshift on the box, and Time Machine.",
    )
    parser.add_argument("path", help="repo-relative, absolute, or any trailing fragment of the path")
    parser.add_argument("--repo", default=os.environ.get("FIND_DELETED_PATH_REPO", "."),
                        help="git repository to search (default: current directory)")
    parser.add_argument("--transcripts-dir", default=os.environ.get("FIND_DELETED_PATH_TRANSCRIPTS_DIR", DEFAULT_TRANSCRIPTS_DIR))
    parser.add_argument("--box-ssh-host", default=os.environ.get("FIND_DELETED_PATH_BOX_SSH_HOST", DEFAULT_BOX_SSH_HOST))
    parser.add_argument("--timeshift-snapshot-root", default=os.environ.get("FIND_DELETED_PATH_TIMESHIFT_SNAPSHOT_ROOT", DEFAULT_TIMESHIFT_SNAPSHOT_ROOT))
    parser.add_argument("--skip", action="append", default=[],
                        choices=["localsnapshots", "git", "transcripts", "box", "timeshift", "timemachine"],
                        help="skip a surface (repeatable); 'box' skips everything on the box — "
                             "its transcripts as well as Timeshift — so nothing is sent over ssh")
    parser.add_argument("--prompt-for-root", action="store_true",
                        help="mount the Time Machine snapshot from here, letting sudo ask for your "
                             "password in this terminal, instead of printing the command. Only ever "
                             "pass this by hand: a hook has no terminal to answer a prompt in")
    args = parser.parse_args(argv)

    # One form for every surface: an absolute path inside the repository is
    # searched for by its repo-relative name, and the header says so.
    wanted, _ = _repo_relative_form(args.path, args.repo, runner)
    shown = wanted if wanted == args.path else "%s (given as %s)" % (wanted, args.path)

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
    )
    print(render(shown, reports))
    return exit_status(reports)


def exit_status(reports):
    """The exit code the docstring promises, from the surfaces' statuses.

    FOUND anywhere is 0. Otherwise 1 only when at least one surface ran and
    every one of them was searched; if any surface was UNAVAILABLE — or no
    surface ran at all — the run was not exhaustive, and 3 says so.
    """
    if any(r.status == FOUND for r in reports):
        return EXIT_FOUND
    if not reports or any(r.status == UNAVAILABLE for r in reports):
        return EXIT_INCOMPLETE
    return EXIT_NOT_FOUND_EVERYWHERE


if __name__ == "__main__":
    sys.exit(main())
