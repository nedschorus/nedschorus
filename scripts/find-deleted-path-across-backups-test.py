#!/usr/bin/env python3
"""Tests for find-deleted-path-across-backups.py.

Run: python3 scripts/find-deleted-path-across-backups-test.py
Prints one line per case and exits non-zero if any case fails.

Nothing here touches a real backup. Every case replaces the module's single
`run_command` seam with a fake that answers from a table, so the four surfaces
are exercised without ssh, without the backup drive, and without sudo.

The cases that matter most are the UNAVAILABLE ones. A surface that cannot be
read must never render as "not found", because an agent told "not found" stops
looking. Each blocked surface therefore has a case asserting both the status
AND that the output says what to do about it.
"""

import contextlib
import importlib.util
import io
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("find-deleted-path-across-backups.py")
spec = importlib.util.spec_from_file_location("find_deleted_path_across_backups", MODULE_PATH)
finder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(finder)

FOUND = finder.FOUND
NOT_FOUND = finder.NOT_FOUND
UNAVAILABLE = finder.UNAVAILABLE

failures = []


def check(name, condition, detail=""):
    if condition:
        print("PASS  %s" % name)
    else:
        print("FAIL  %s%s" % (name, (" — " + detail) if detail else ""))
        failures.append(name)


class FakeRunner:
    """Answers commands from a table of (match-substring -> (code, out, err))."""

    def __init__(self, table, default=(1, "", "")):
        self.table = table
        self.default = default
        self.calls = []

    def __call__(self, argv, timeout=None, cwd=None):
        joined = " ".join(argv)
        self.calls.append(joined)
        for needle, answer in self.table:
            if needle in joined:
                return answer
        return self.default


class LocalShellRunner(FakeRunner):
    """Answers `ssh <host> <script>` by running <script> through a local bash.

    The two box surfaces are shell scripts this tool generates and ships over
    ssh; a table can only check their text. Running them for real against a
    fake tree under `home` is what catches a script that reports "searched"
    while it looked nowhere. HOME is pointed at the fake tree so `~` and
    `$HOME` land there; cwd is the tree too, so a stray unquoted glob cannot
    match files in this repository and hide a quoting bug. Every other command
    still answers from the table.
    """

    def __init__(self, table, home):
        FakeRunner.__init__(self, table)
        self.home = str(home)

    def __call__(self, argv, timeout=None, cwd=None):
        if argv[0] != "ssh":
            return FakeRunner.__call__(self, argv, timeout, cwd)
        self.calls.append(" ".join(argv))
        completed = subprocess.run(
            ["bash", "-c", argv[-1]],
            cwd=self.home,
            env=dict(os.environ, HOME=self.home),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return completed.returncode, completed.stdout.decode(), completed.stderr.decode()


# --------------------------------------------------------------------------
# path matching
# --------------------------------------------------------------------------

check("suffix match on a full path", finder.path_matches("a/b/c.md", "a/b/c.md"))
check("suffix match on a trailing fragment", finder.path_matches("docs/a/b/c.md", "b/c.md"))
check("suffix match on a bare basename", finder.path_matches("docs/a/b/c.md", "c.md"))
check("no match on a partial component",
      not finder.path_matches("docs/notes.md", "otes.md"),
      "matching mid-component would make 'notes.md' find 'my-notes.md'")
check("a leading './' is ignored on either side",
      finder.path_matches("./a/b.md", "a/b.md") and finder.path_matches("a/b.md", "./a/b.md"))
check("a dotfile keeps its dot: '.env' does not match 'scripts/env'",
      not finder.path_matches("scripts/env", ".env"),
      "lstrip('./') strips every leading dot, so '.env' became 'env' and matched the wrong file")
check("a dotfile still matches itself by suffix",
      finder.path_matches("config/.env", ".env"))

# The narrow trigger for the dotfile defect: no exact pathspec match (so the
# suffix scan runs) and some non-dot path ends with the same remainder.
git_dotfile = FakeRunner([
    ("rev-parse --git-dir", (0, ".git\n", "")),
    ("log --all --full-history -1 --format=%H", (0, "\n", "")),
    ("--name-only", (0, "scripts/env\nREADME.md\n", "")),
    # scripts/env is alive and well in history; the fixture must let the
    # wrong match go all the way to a FOUND, or the case proves nothing.
    ("log --all --full-history --format=%H|%ad|%s", (0, "ba432e8e5|2026-08-20|add env\n", "")),
    ("log --all --full-history --format=%H|%P|%ct|%ad|%s", (0, "ba432e8e5|0a0a0a0a0|1787000000|2026-08-20|add env\n", "")),
    ("cat-file -e", (0, "", "")),
])
report = finder.search_git(".env", "/repo", git_dotfile)
check("a request for '.env' is NOT FOUND when history only has 'scripts/env'",
      report.status == NOT_FOUND,
      "was FOUND with a recovery command for scripts/env: %s" % report.recovery)

# --------------------------------------------------------------------------
# local snapshots — the surface that needs no password
# --------------------------------------------------------------------------

# `tmutil listlocalsnapshots /System/Volumes/Data` as this Mac printed it on
# 2026-08-31: a header line, the .local snapshots, and com.apple.os.update-*
# entries that belong to the System volume and could never hold a working file.
LOCAL_SNAPSHOT_LIST = (0,
                       "Snapshots for volume group containing disk /System/Volumes/Data:\n"
                       "com.apple.TimeMachine.2026-08-30-124711.local\n"
                       "com.apple.TimeMachine.2026-08-31-105031.local\n"
                       "com.apple.TimeMachine.2026-08-31-115113.local\n"
                       "com.apple.os.update-MSUPrepareUpdate\n", "")
MOUNTS_FINE = ("mount_apfs", (0, "", ""))
RELEASES_FINE = ("diskutil unmount", (0, "", ""))
LISTS_SNAPSHOTS = ("tmutil listlocalsnapshots", LOCAL_SNAPSHOT_LIST)

# The case that proves this surface earns its place: /private/tmp/claude-501 is
# [Excluded] from Time Machine, so the external disk holds nothing under the
# scratchpad every agent is told to write intermediate work to, but it IS in the
# whole-volume local snapshots. Ten files were recovered out of the 11:51
# snapshot on 2026-08-31 with no password typed.
REAPED = "/private/tmp/claude-501/w/scratchpad/reaped.md"
# /private/tmp, not /tmp: `mount` reports the resolved spelling, and the script
# compares its own mount point against that table. See the constant's own
# comment for what the /tmp spelling cost.
MOUNT_POINT = "/private/tmp/find-deleted-path-across-backups-local-snapshot-ro"
MOUNT_POINT_TMP_SPELLING = "/tmp/find-deleted-path-across-backups-local-snapshot-ro"

local_hit = FakeRunner([LISTS_SNAPSHOTS, MOUNTS_FINE, RELEASES_FINE, ("test -e", (0, "", ""))])
report = finder.search_local_snapshots(REAPED, "/repo", local_hit)
check("a path in every local snapshot is FOUND, newest first",
      report.status == FOUND and any(l.strip() == "com.apple.TimeMachine.2026-08-31-115113.local"
                                     for l in report.lines),
      "%s %s" % (report.status, report.lines))
check("the recovery command mounts the newest snapshot holding it and copies the file out",
      report.recovery == [
          "mkdir -p %s && mount_apfs -o ro -s com.apple.TimeMachine.2026-08-31-115113.local "
          "/System/Volumes/Data %s" % (MOUNT_POINT, MOUNT_POINT),
          "cp %s%s . && diskutil unmount %s" % (MOUNT_POINT, REAPED, MOUNT_POINT),
      ],
      str(report.recovery))
check("no sudo is asked for anywhere on this surface — that is its entire point",
      not any("sudo" in c for c in local_hit.calls) and not any("sudo" in c for c in report.recovery),
      "%s %s" % (local_hit.calls, report.recovery))
check("the report says plainly that no password was needed",
      any("no password needed" in l for l in report.lines), str(report.lines))
check("a com.apple.os.update-* snapshot is never mounted: it is the System volume's, not the Data volume's",
      not any("os.update" in c for c in local_hit.calls), str(local_hit.calls))
check("every snapshot that was mounted is released again",
      sum(1 for c in local_hit.calls if c.startswith("mount_apfs")) == 3
      and sum(1 for c in local_hit.calls if c.startswith("diskutil unmount")) == 3,
      str(local_hit.calls))
check("mount_apfs is given the Data volume's mount point, so there is no device node to go stale",
      all("/System/Volumes/Data" in c for c in local_hit.calls if c.startswith("mount_apfs")),
      str(local_hit.calls))

local_miss = FakeRunner([LISTS_SNAPSHOTS, MOUNTS_FINE, RELEASES_FINE, ("test -e", (1, "", ""))])
report = finder.search_local_snapshots(REAPED, "/repo", local_miss)
check("a path in none of the snapshots is NOT FOUND, naming the range actually searched",
      report.status == NOT_FOUND
      and any(l == "searched com.apple.TimeMachine.2026-08-30-124711.local .. "
                   "com.apple.TimeMachine.2026-08-31-115113.local and none of them has it"
              for l in report.lines),
      "%s %s" % (report.status, report.lines))
check("an absolute path carries no repo-relative caveat, because nothing was guessed at",
      not any("read as a path relative" in l for l in report.lines), str(report.lines))

# Every failure of mount_apfs is reported verbatim and never classified: a
# snapshot that would not open was NOT searched, and calling that "not there" is
# the conflation this file exists to refuse. Exit 77 "Operation not permitted"
# is what an already-occupied mount point gave on 2026-08-31.
local_wont_mount = FakeRunner([
    LISTS_SNAPSHOTS, RELEASES_FINE,
    ("mount_apfs", (77, "", "mount_apfs: volume could not be mounted: Operation not permitted\n")),
])
report = finder.search_local_snapshots(REAPED, "/repo", local_wont_mount)
check("a local snapshot that will not mount is UNAVAILABLE, never 'none of them has it'",
      report.status == UNAVAILABLE and not any("none of them has it" in l for l in report.lines),
      "%s %s" % (report.status, report.lines))
check("... quoting mount_apfs verbatim and naming the snapshot",
      any(l.startswith("could not search com.apple.TimeMachine.2026-08-31-115113.local")
          and "Operation not permitted" in l for l in report.lines),
      str(report.lines))
check("... collapsing the identical message from the other snapshots instead of repeating it",
      sum(1 for l in report.lines if l.startswith("could not search")) == 1
      and any(l.strip() == "... and 2 more snapshot(s) with the same message" for l in report.lines),
      str(report.lines))
check("a refused mount is not followed by a release of it",
      not any(c.startswith("diskutil unmount") for c in local_wont_mount.calls),
      str(local_wont_mount.calls))
check("... and the mount command handed back for it still asks for no sudo",
      report.recovery and "mount_apfs -o ro -s" in report.recovery[0]
      and not any("sudo" in c for c in report.recovery),
      str(report.recovery))


class OneSnapshotRefusesRunner(FakeRunner):
    """Every snapshot mounts except the newest, which refuses."""

    def __call__(self, argv, timeout=None, cwd=None):
        joined = " ".join(argv)
        if joined.startswith("mount_apfs") and "2026-08-31-115113" in joined:
            self.calls.append(joined)
            return (66, "", "mount_apfs: volume could not be mounted: No such file or directory\n")
        return FakeRunner.__call__(self, argv, timeout, cwd)


local_mixed = OneSnapshotRefusesRunner([LISTS_SNAPSHOTS, MOUNTS_FINE, RELEASES_FINE, ("test -e", (1, "", ""))])
report = finder.search_local_snapshots(REAPED, "/repo", local_mixed)
check("one refused snapshot among searched-and-empty ones is UNAVAILABLE, listing both",
      report.status == UNAVAILABLE
      and any(l.startswith("could not search com.apple.TimeMachine.2026-08-31-115113.local") for l in report.lines)
      and any("2026-08-31-105031.local and none of them has it" in l for l in report.lines),
      "%s %s" % (report.status, report.lines))


# A mount point left occupied poisons the whole rest of the walk: every later
# mount_apfs fails with exit 77 on the MOUNT POINT, not on the snapshot. Seen
# twice on 2026-08-31 running this surface against this Mac's real snapshots —
# plain `umount` returned "Resource busy -- try 'diskutil unmount'", the first
# version ignored that exit code, and a run that had searched six snapshots
# reported the other twelve as though each had refused on its own account.
class ReleaseFailsRunner(FakeRunner):
    """Every snapshot mounts and tests fine; the first one will not release."""

    def __init__(self, table):
        FakeRunner.__init__(self, table)
        self.releases = 0

    def __call__(self, argv, timeout=None, cwd=None):
        joined = " ".join(argv)
        if joined.startswith("diskutil unmount"):
            self.calls.append(joined)
            self.releases += 1
            return (1, "", "umount(%s): Resource busy -- try 'diskutil unmount'\n" % MOUNT_POINT)
        return FakeRunner.__call__(self, argv, timeout, cwd)


stuck_miss = ReleaseFailsRunner([LISTS_SNAPSHOTS, MOUNTS_FINE, ("test -e", (1, "", ""))])
report = finder.search_local_snapshots(REAPED, "/repo", stuck_miss)
check("a snapshot that will not release stops the walk instead of poisoning it",
      sum(1 for c in stuck_miss.calls if c.startswith("mount_apfs")) == 1,
      str(stuck_miss.calls))
check("the snapshots the walk never reached say so, naming the one still mounted",
      report.status == UNAVAILABLE
      and any(l.startswith("could not search com.apple.TimeMachine.2026-08-31-105031.local — not reached: "
                           "com.apple.TimeMachine.2026-08-31-115113.local stayed mounted on")
              and "Resource busy" in l for l in report.lines),
      "%s %s" % (report.status, report.lines))
check("... and the first command handed back clears the mount point, before anything that needs it",
      report.recovery[0] == "diskutil unmount " + MOUNT_POINT, str(report.recovery))

stuck_hit = ReleaseFailsRunner([LISTS_SNAPSHOTS, MOUNTS_FINE, ("test -e", (0, "", ""))])
report = finder.search_local_snapshots(REAPED, "/repo", stuck_hit)
check("a hit in a snapshot that then will not release is still FOUND",
      report.status == FOUND and any(l.startswith("1 snapshot(s) still have it") for l in report.lines),
      "%s %s" % (report.status, report.lines))
check("... and its recovery clears the mount point first, or every command below would fail on it",
      report.recovery[0] == "diskutil unmount " + MOUNT_POINT
      and "mount_apfs -o ro -s" in report.recovery[1],
      str(report.recovery))

# The LAST snapshot in the walk is the one that reaches no `unsearched` entry to
# carry its failed release: the loop ends, the skip guard never runs again, and
# the run fell through to a bare NOT FOUND — exit 1, the docstring's only status
# meaning "stop looking" — from a run that had just wedged its own mount point,
# naming neither the snapshot nor the mount point (PR #222 review, finding 2).
# One snapshot in the list makes the first snapshot the last one.
LISTS_ONE_SNAPSHOT = ("tmutil listlocalsnapshots",
                      (0, "Snapshots for volume group containing disk /System/Volumes/Data:\n"
                          "com.apple.TimeMachine.2026-08-31-115113.local\n", ""))
stuck_last = ReleaseFailsRunner([LISTS_ONE_SNAPSHOT, MOUNTS_FINE, ("test -e", (1, "", ""))])
report = finder.search_local_snapshots(REAPED, "/repo", stuck_last)
check("a failed release on the LAST snapshot is still reported, naming it and the mount point",
      any("com.apple.TimeMachine.2026-08-31-115113.local stayed mounted on " + MOUNT_POINT in l
          and "Resource busy" in l for l in report.lines),
      "%s %s" % (report.status, report.lines))
check("... and the mount point it left behind comes back as a command that clears it",
      report.recovery == ["diskutil unmount " + MOUNT_POINT], str(report.recovery))
# Every snapshot WAS opened and tested, and UNAVAILABLE means the surface could
# not be searched. The defect was the silence, not the status.
check("... and the status stays NOT FOUND, because the search itself was complete",
      report.status == NOT_FOUND, "%s %s" % (report.status, report.lines))
check("... and it is not labelled 'not reached', which belongs to snapshots the walk stopped short of",
      not any("not reached" in l for l in report.lines), str(report.lines))


# macOS mounts local snapshots for its own use, and one that is already mounted
# cannot be mounted again — mount_apfs exits 75, "Resource busy". Measured
# 2026-08-31: the two NEWEST snapshots were both in that state within the hour,
# which is precisely the pair the "deleted it minutes ago" case needs, so
# reading them where they sit is what keeps the headline case working. A file
# copied out of one that day was 43391 bytes, byte-identical to the live one.
# The mount point below deliberately contains " (" so the parse is pinned.
LIVE_OS_MOUNT = ("/Volumes/com.apple.TimeMachine.localsnapshots/Backups.backupdb/"
                 "Ed (air)/2026-08-31-115113/Data")
STALE_OS_MOUNT = "/Volumes/stale/2026-08-30-124711/Data"
MOUNT_LISTING = (
    "/dev/disk3s1s1 on / (apfs, sealed, local, read-only, journaled)\n"
    "com.apple.TimeMachine.2026-08-31-115113.local@/dev/disk3s5 on %s "
    "(apfs, local, read-only, journaled, nobrowse, protect)\n"
    "com.apple.TimeMachine.2026-08-30-124711.local@/dev/disk3s5 on %s "
    "(apfs, local, read-only, journaled, nobrowse, protect)\n" % (LIVE_OS_MOUNT, STALE_OS_MOUNT))


class MountTableRunner(FakeRunner):
    """Answers the bare `mount` command from a listing; everything else from the table."""

    def __init__(self, table, mount_output):
        FakeRunner.__init__(self, table)
        self.mount_output = mount_output

    def __call__(self, argv, timeout=None, cwd=None):
        if argv == ["mount"]:
            self.calls.append("mount")
            return (0, self.mount_output, "")
        return FakeRunner.__call__(self, argv, timeout, cwd)


read_in_place = MountTableRunner([
    ("test -d " + LIVE_OS_MOUNT, (0, "", "")),
    ("test -d", (1, "", "")),          # the stale entry does not resolve
    ("test -e " + LIVE_OS_MOUNT, (0, "", "")),
    ("test -e", (1, "", "")),
    LISTS_SNAPSHOTS, MOUNTS_FINE, RELEASES_FINE,
], MOUNT_LISTING)
report = finder.search_local_snapshots(REAPED, "/repo", read_in_place)
check("a snapshot macOS already has mounted is read where it sits, not mounted again",
      report.status == FOUND
      and not any("mount_apfs" in c and "2026-08-31-115113" in c for c in read_in_place.calls),
      "%s %s" % (report.status, read_in_place.calls))
check("... and the report says so, since it is the difference between searched and not",
      any(l == "1 of them were read where macOS already had them mounted, mounting nothing: "
               "com.apple.TimeMachine.2026-08-31-115113.local" for l in report.lines),
      str(report.lines))
check("... and the recovery copies straight out of that mount, with nothing to mount or release",
      report.recovery[0].startswith("cp ") and (LIVE_OS_MOUNT + REAPED) in report.recovery[0]
      and not any("mount_apfs" in c for c in report.recovery),
      str(report.recovery))
check("a mount point containing ' (' survives the parse, since the options paren is the last one",
      any(c == "test -d " + LIVE_OS_MOUNT for c in read_in_place.calls),
      str([c for c in read_in_place.calls if c.startswith("test -d")]))
check("a stale entry whose mount point does not resolve falls through to mounting it here",
      any("mount_apfs" in c and "2026-08-30-124711" in c for c in read_in_place.calls),
      str(read_in_place.calls))

# The four ghosts on 2026-08-31: listed by `mount`, mount points that do not
# resolve, and unmountable because the snapshot is already attached. They are
# macOS's own state; this script reports them and does not try to clear them.
os_mount_ghost = MountTableRunner([
    ("test -d", (1, "", "")),
    ("mount_apfs -o ro -s com.apple.TimeMachine.2026-08-30-124711",
     (75, "", "mount_apfs: volume could not be mounted: Resource busy\n")),
    LISTS_SNAPSHOTS, MOUNTS_FINE, RELEASES_FINE, ("test -e", (1, "", "")),
], MOUNT_LISTING)
report = finder.search_local_snapshots(REAPED, "/repo", os_mount_ghost)
check("a snapshot that is neither readable in place nor mountable is UNAVAILABLE, quoting mount_apfs",
      report.status == UNAVAILABLE
      and any(l == "could not search com.apple.TimeMachine.2026-08-30-124711.local — mount_apfs exited 75: "
                   "mount_apfs: volume could not be mounted: Resource busy" for l in report.lines),
      "%s %s" % (report.status, report.lines))
check("... and nothing is done to clear macOS's own mount of it",
      not any(c.startswith("diskutil unmount " + STALE_OS_MOUNT) for c in os_mount_ghost.calls),
      str(os_mount_ghost.calls))
# It is the only unsearchable one here, and macOS holds it, so no command can
# work — saying that beats handing over a mount_apfs whose refusal is quoted two
# lines above it.
check("... and no unrunnable command is offered for a snapshot that cannot be mounted twice",
      report.recovery == [] and any("mount_apfs cannot open a snapshot twice" in l for l in report.lines),
      "%s %s" % (report.lines, report.recovery))

# A MOUNT POINT THIS SCRIPT ITSELF LEFT OCCUPIED, which is the state finding 2
# above creates and a killed run creates just as easily. It is not macOS's
# mount and must not be reported as one. Under the old /tmp spelling of the
# constant the two never compared equal — `mount` prints the resolved
# /private/tmp form, observed on this Mac as
# `com.apple.TimeMachine.2026-08-12-202035.backup@/dev/disk5s2 on
# /private/tmp/nedschorus-backup-readonly-mount (apfs, ...)` — so the leftover
# was filed as one macOS holds, the report said "nothing to mount, nothing to
# release", and every later run searched 1 snapshot of 17 (PR #222, finding 1).
OCCUPIED_LISTING = (
    "/dev/disk3s1s1 on / (apfs, sealed, local, read-only, journaled)\n"
    "com.apple.TimeMachine.2026-08-30-124711.local@/dev/disk3s5 on %s "
    "(apfs, local, read-only, journaled, nobrowse, protect)\n" % MOUNT_POINT)

def occupied_runner(occupier_has_it):
    """The two snapshots not on the mount point are refused with the real 77."""
    return MountTableRunner([
        ("test -d " + MOUNT_POINT, (0, "", "")),
        ("test -e " + MOUNT_POINT, (0, "", "") if occupier_has_it else (1, "", "")),
        ("mount_apfs", (77, "", "mount_apfs: volume could not be mounted: Operation not permitted\n")),
        LISTS_SNAPSHOTS,
    ], OCCUPIED_LISTING)

occupied = occupied_runner(occupier_has_it=False)
report = finder.search_local_snapshots(REAPED, "/repo", occupied)
check("a mount point occupied before the walk started is named, with what is on it",
      any(l.startswith("the mount point " + MOUNT_POINT + " already had "
                       "com.apple.TimeMachine.2026-08-30-124711.local on it when this run started")
          for l in report.lines),
      str(report.lines))
check("... and the first command handed back is the one that frees it",
      report.recovery and report.recovery[0] == "diskutil unmount " + MOUNT_POINT, str(report.recovery))
# The whole misreport: this script's own leftover called macOS's, with "nothing
# to mount, nothing to release" — the sentence that keeps the tool wedged.
check("... and it is NOT counted as one macOS already had mounted, because it is this script's",
      not any("read where macOS already had them mounted" in l for l in report.lines)
      and not any("nothing to mount, nothing to release" in c for c in report.recovery),
      "%s %s" % (report.lines, report.recovery))
check("... and the snapshots that could not be mounted past it are still UNAVAILABLE, not 'not found'",
      report.status == UNAVAILABLE, "%s %s" % (report.status, report.lines))

# The occupier is a perfectly good read-only mount of a real snapshot, so when
# the file is in it the answer is FOUND — and one command both takes the file
# out and clears the occupation. Clearing FIRST would unmount the tree the copy
# reads from.
occupied_hit = occupied_runner(occupier_has_it=True)
report = finder.search_local_snapshots(REAPED, "/repo", occupied_hit)
check("a hit inside the leftover mount is FOUND and copied straight out of it",
      report.status == FOUND
      and report.recovery == ["cp %s%s . && diskutil unmount %s" % (MOUNT_POINT, REAPED, MOUNT_POINT)],
      "%s %s" % (report.status, report.recovery))

# The parameter gets the same normalisation as the constant, so a caller that
# spells it /tmp is not silently given the broken comparison back.
if os.path.realpath("/tmp") == "/private/tmp":
    tmp_spelled = occupied_runner(occupier_has_it=False)
    report = finder.search_local_snapshots(REAPED, "/repo", tmp_spelled,
                                           mount_point=MOUNT_POINT_TMP_SPELLING)
    check("a caller passing the /tmp spelling of the mount point gets the same answer",
          report.status == UNAVAILABLE
          and any(l.startswith("the mount point " + MOUNT_POINT + " already had ") for l in report.lines),
          "%s %s" % (report.status, report.lines))


# But when something unsearchable IS still mountable, that is the one to offer.
mixed_unreachable = MountTableRunner([
    ("test -d", (1, "", "")),
    ("mount_apfs -o ro -s com.apple.TimeMachine.2026-08-30-124711",
     (75, "", "mount_apfs: volume could not be mounted: Resource busy\n")),
    ("mount_apfs -o ro -s com.apple.TimeMachine.2026-08-31-105031",
     (77, "", "mount_apfs: volume could not be mounted: Operation not permitted\n")),
    LISTS_SNAPSHOTS, MOUNTS_FINE, RELEASES_FINE, ("test -e", (1, "", "")),
], MOUNT_LISTING)
report = finder.search_local_snapshots(REAPED, "/repo", mixed_unreachable)
check("the command handed back names a snapshot that can still be mounted, not one macOS holds",
      report.status == UNAVAILABLE and report.recovery
      and "com.apple.TimeMachine.2026-08-31-105031.local" in report.recovery[0]
      and "com.apple.TimeMachine.2026-08-30-124711" not in report.recovery[0],
      "%s %s" % (report.lines, report.recovery))

mount_unreadable = FakeRunner([LISTS_SNAPSHOTS, MOUNTS_FINE, RELEASES_FINE, ("test -e", (1, "", ""))])
report = finder.search_local_snapshots(REAPED, "/repo", mount_unreadable)
check("a `mount` that cannot be read costs nothing: every snapshot is opened by this script instead",
      report.status == NOT_FOUND
      and sum(1 for c in mount_unreadable.calls if c.startswith("mount_apfs")) == 3
      and not any("read where macOS already had them mounted" in l for l in report.lines),
      "%s %s" % (report.status, report.lines))

local_no_tmutil = FakeRunner([("tmutil listlocalsnapshots", (127, "", "tmutil: not found on this machine"))])
report = finder.search_local_snapshots(REAPED, "/repo", local_no_tmutil)
check("a machine without tmutil is UNAVAILABLE carrying its words, not NOT FOUND",
      report.status == UNAVAILABLE and any("not found on this machine" in l for l in report.lines),
      "%s %s" % (report.status, report.lines))
check("... and nothing was mounted on it",
      not any(c.startswith("mount_apfs") for c in local_no_tmutil.calls), str(local_no_tmutil.calls))

local_none_kept = FakeRunner([
    ("tmutil listlocalsnapshots", (0, "Snapshots for volume group containing disk /System/Volumes/Data:\n"
                                      "com.apple.os.update-MSUPrepareUpdate\n", "")),
])
report = finder.search_local_snapshots(REAPED, "/repo", local_none_kept)
check("a Mac keeping no local snapshots is UNAVAILABLE and says the retention is about a day",
      report.status == UNAVAILABLE and any("retains no local snapshots" in l for l in report.lines)
      and any("roughly a day" in l for l in report.lines),
      "%s %s" % (report.status, report.lines))

# A `test -e` needs a known path. Locating a bare filename inside a snapshot
# needs a find over the whole volume, which this version runs on neither
# snapshot surface, so the surface says so rather than searching nothing.
local_fragment = FakeRunner([LISTS_SNAPSHOTS, MOUNTS_FINE, RELEASES_FINE, ("test -e", (0, "", ""))])
report = finder.search_local_snapshots("dispositions.md", "/repo", local_fragment)
check("a bare filename is UNAVAILABLE naming the fan-out this version does not run",
      report.status == UNAVAILABLE and any("bare filename" in l and "fan-out" in l for l in report.lines),
      "%s %s" % (report.status, report.lines))
check("... and it points at the surfaces that do answer a bare filename",
      any("git, transcripts and Timeshift" in l for l in report.lines), str(report.lines))
check("... and no snapshot was mounted to answer it",
      not any(c.startswith("mount_apfs") for c in local_fragment.calls), str(local_fragment.calls))

local_no_repo = FakeRunner([LISTS_SNAPSHOTS, ("rev-parse --show-toplevel", (128, "", "not a git repository"))])
report = finder.search_local_snapshots("docs/a/b.md", "/not-a-repo", local_no_repo)
check("a relative path with no repository to resolve it against is UNAVAILABLE, not NOT FOUND",
      report.status == UNAVAILABLE and any("no top level to resolve it against" in l for l in report.lines),
      "%s %s" % (report.status, report.lines))

local_relative = FakeRunner([
    LISTS_SNAPSHOTS, MOUNTS_FINE, RELEASES_FINE,
    ("rev-parse --show-toplevel", (0, "/private/repos/nedschorus\n", "")),
    ("test -e", (1, "", "")),
])
report = finder.search_local_snapshots("docs/a/b.md", "/private/repos/nedschorus", local_relative)
check("a repo-relative path is resolved against the repository's top level before it is tested",
      any(l == "tested /private/repos/nedschorus/docs/a/b.md inside each" for l in report.lines),
      str(report.lines))
check("... and a miss on it names the place tested, since a fragment would have meant another",
      report.status == NOT_FOUND and any("read as a path relative to the repository" in l for l in report.lines),
      "%s %s" % (report.status, report.lines))

# /tmp, /etc and /var are symlinks living on the SYSTEM volume, and a snapshot
# of the DATA volume has no such entries at its root, so an unnormalised /tmp/x
# can never match a file that really is in there — a false NOT FOUND for exactly
# the scratchpad files this surface exists to recover. A symlink built here pins
# the normalisation without depending on any machine's own layout.
with tempfile.TemporaryDirectory() as tmp:
    Path(tmp, "real", "claude-501").mkdir(parents=True)
    os.symlink(str(Path(tmp, "real")), str(Path(tmp, "link")))
    symlinked = FakeRunner([LISTS_SNAPSHOTS, MOUNTS_FINE, RELEASES_FINE, ("test -e", (1, "", ""))])
    finder.search_local_snapshots(str(Path(tmp, "link", "claude-501", "gone.md")), "/repo", symlinked)
    expected = os.path.realpath(str(Path(tmp, "real", "claude-501", "gone.md")))
    check("a symlinked path is normalised before it is tested, the way /tmp must become /private/tmp",
          any(c == "test -e " + MOUNT_POINT + expected for c in symlinked.calls),
          "expected %s; got %s" % (expected, [c for c in symlinked.calls if c.startswith("test")]))

data_prefixed = FakeRunner([LISTS_SNAPSHOTS, MOUNTS_FINE, RELEASES_FINE, ("test -e", (1, "", ""))])
finder.search_local_snapshots("/System/Volumes/Data/Users/el/a/b.md", "/repo", data_prefixed)
check("the firmlink spelling /System/Volumes/Data/Users/... is tested as /Users/..., which is how a snapshot spells it",
      any(c == "test -e " + MOUNT_POINT + "/Users/el/a/b.md" for c in data_prefixed.calls),
      str([c for c in data_prefixed.calls if c.startswith("test")]))


class FakeVolumeRunner(FakeRunner):
    """Answers mount_apfs by pointing the mount point at a real directory tree.

    A table can only check the strings this surface builds. Running the mount,
    the test and the unmount against real trees is what catches a probe path
    assembled wrongly: a mounted snapshot carries the machine's own absolute
    layout at its root, so /private/tmp/x inside it is <mount point>/private/tmp/x,
    and an off-by-one there reports a file that is present as absent.
    """

    def __init__(self, table, volumes, mount_point):
        FakeRunner.__init__(self, table)
        self.volumes = volumes
        self.mount_point = mount_point

    def __call__(self, argv, timeout=None, cwd=None):
        joined = " ".join(argv)
        if argv[0] in ("mkdir", "mount_apfs", "diskutil", "test"):
            self.calls.append(joined)
        if argv[0] == "mkdir":
            return (0, "", "")  # here the mount point is the symlink itself
        if argv[0] == "mount_apfs":
            snapshot = argv[argv.index("-s") + 1]
            if snapshot not in self.volumes:
                return (66, "", "mount_apfs: volume could not be mounted: No such file or directory\n")
            os.symlink(self.volumes[snapshot], self.mount_point)
            return (0, "", "")
        if argv[0] == "diskutil":
            os.unlink(self.mount_point)
            return (0, "", "")
        if argv[0] == "test":
            return (0 if os.path.exists(argv[2]) else 1, "", "")
        return FakeRunner.__call__(self, argv, timeout, cwd)


with tempfile.TemporaryDirectory() as tmp:
    NEWEST = "com.apple.TimeMachine.2026-08-31-115113.local"
    MIDDLE = "com.apple.TimeMachine.2026-08-31-105031.local"
    OLDEST = "com.apple.TimeMachine.2026-08-30-124711.local"
    volumes = {}
    for name in (NEWEST, MIDDLE, OLDEST):
        Path(tmp, name, "Users", "el").mkdir(parents=True)
        volumes[name] = str(Path(tmp, name))
    # The file was written after the oldest snapshot was taken, so only the two
    # newer trees hold it — the shape of "reaped an hour ago".
    for name in (NEWEST, MIDDLE):
        inside = Path(tmp, name, "private", "tmp", "claude-501", "w")
        inside.mkdir(parents=True)
        Path(inside, "reaped.md").write_text("the content that was reaped\n")
    mount_point = str(Path(tmp, "mount-point"))

    def local_snapshots(wanted, only=None):
        kept = volumes if only is None else {name: volumes[name] for name in only}
        runner = FakeVolumeRunner([LISTS_SNAPSHOTS], kept, mount_point)
        return finder.search_local_snapshots(wanted, "/repo", runner, mount_point=mount_point), runner

    report, runner = local_snapshots("/private/tmp/claude-501/w/reaped.md")
    check("local snapshots, real trees: a scratchpad file is FOUND in the snapshots that have it",
          report.status == FOUND and any(l.startswith("2 snapshot(s) still have it") for l in report.lines)
          and any(l.strip() == NEWEST for l in report.lines),
          "%s %s" % (report.status, report.lines))
    check("local snapshots, real trees: the snapshot taken before it was written is searched, not skipped",
          any(l.startswith("3 local snapshot(s) retained, 3 searched") for l in report.lines), str(report.lines))
    check("local snapshots, real trees: the mount point is released after a hit",
          not os.path.lexists(mount_point), mount_point)

    report, runner = local_snapshots("/private/tmp/claude-501/w/never-written.md")
    check("local snapshots, real trees: a file in none of them is NOT FOUND after every one was opened",
          report.status == NOT_FOUND and sum(1 for c in runner.calls if c.startswith("mount_apfs")) == 3,
          "%s %s" % (report.status, report.lines))
    check("local snapshots, real trees: the mount point is released after a miss too",
          not os.path.lexists(mount_point), mount_point)

    report, runner = local_snapshots("/private/tmp/claude-501/w/reaped.md", only=[NEWEST])
    check("local snapshots, real trees: snapshots that would not open are reported even beside a hit",
          report.status == FOUND and any(l.startswith("could not search") for l in report.lines),
          "%s %s" % (report.status, report.lines))
    check("local snapshots, real trees: a refused mount leaves nothing mounted behind",
          not os.path.lexists(mount_point), mount_point)

# Order and the skip flag. The design ruled local snapshots first: no network,
# no privilege, and they answer "I deleted it minutes ago" outright.
skip_local = FakeRunner([("rev-parse --git-dir", (128, "", "not a git repository"))])
reports = finder.build_report("a/b.md", "/not-a-repo", "/nonexistent-transcripts", "",
                              "/mnt/backup/timeshift/snapshots", finder.DEFAULT_BOX_SEARCH_ROOTS,
                              skip={"localsnapshots", "box", "timemachine"}, runner=skip_local)
check("--skip localsnapshots drops the surface and lists no snapshots",
      not any(r.surface == "local snapshots" for r in reports)
      and not any("listlocalsnapshots" in c for c in skip_local.calls),
      "%s %s" % ([r.surface for r in reports], skip_local.calls))

order_probe = FakeRunner([LISTS_SNAPSHOTS, MOUNTS_FINE, RELEASES_FINE, ("test -e", (1, "", "")),
                          ("rev-parse --git-dir", (128, "", "not a git repository"))])
reports = finder.build_report("/private/tmp/x/b.md", "/not-a-repo", "/nonexistent-transcripts", "",
                              "/mnt/backup/timeshift/snapshots", finder.DEFAULT_BOX_SEARCH_ROOTS,
                              skip={"box", "timemachine"}, runner=order_probe)
check("local snapshots are searched first, before git",
      [r.surface for r in reports][:2] == ["local snapshots", "git"], str([r.surface for r in reports]))
check("... and without waiting on a date hint from git, which they take none of",
      order_probe.calls.index("tmutil listlocalsnapshots /System/Volumes/Data")
      < order_probe.calls.index("git -C /not-a-repo rev-parse --git-dir"),
      str(order_probe.calls))

check("the report column is wide enough for 'local snapshots' to keep the statuses aligned",
      finder.SurfaceReport("local snapshots", FOUND).render().index(FOUND)
      == finder.SurfaceReport("git", FOUND).render().index(FOUND),
      finder.SurfaceReport("local snapshots", FOUND).render())

# --------------------------------------------------------------------------
# git
# --------------------------------------------------------------------------

# The shape of the motivating deletion. The commits that TOUCHED the path:
#   abc123def  2026-08-14  retire review records   (the deletion; tree lacks it)
#   feedface   2026-08-12  write it                (the last modification)
# The deletion's first parent, merge0123 (2026-08-14), touched nothing under
# the path and still holds it. "Last held" is that merge, not the modification.
# Both log formats are answered so an older walk gets real data too.
git_found = FakeRunner([
    ("rev-parse --git-dir", (0, ".git\n", "")),
    ("log --all --full-history -1 --format=%H", (0, "abc123def\n", "")),
    ("log --all --full-history --format=%H|%ad|%s",
     (0, "abc123def|2026-08-14|retire review records\nfeedface|2026-08-12|write it\n", "")),
    ("log --all --full-history --format=%H|%P|%ct|%ad|%s",
     (0, "abc123def|merge0123|1786708800|2026-08-14|retire review records\n"
         "feedface|00000000|1786536000|2026-08-12|write it\n", "")),
    ("--date=short merge0123", (0, "1786701600|2026-08-14|merge seat branch\n", "")),
    ("cat-file -e abc123def:", (128, "", "does not exist")),
    ("cat-file -e merge0123:", (0, "", "")),
    ("cat-file -e feedface:", (0, "", "")),
])
report = finder.search_git("md-review-records/x/dispositions.md", "/repo", git_found)
check("git reports FOUND for a deleted path still in history", report.status == FOUND)
check("git hands back a runnable recovery command",
      any(c.startswith("git -C") and " show " in c for c in report.recovery),
      str(report.recovery))
check("git cites the deletion's parent, which held the file, not the last commit that modified it",
      report.recovery == ["git -C /repo show merge0123:md-review-records/x/dispositions.md"],
      str(report.recovery))
check("git records the last date it HELD the file, not the last date it modified it",
      getattr(report, "newest_date_held", None) == "2026-08-14",
      "got %r; 2026-08-12 is the modification date, and a backup candidate chosen from it is one snapshot too old"
      % getattr(report, "newest_date_held", None))

git_log_fails = FakeRunner([
    ("rev-parse --git-dir", (0, ".git\n", "")),
    ("log --all --full-history -1 --format=%H", (0, "abc123def\n", "")),
    ("log --all --full-history --format=%H|", (128, "", "fatal: bad object HEAD")),
])
report = finder.search_git("a/b.md", "/repo", git_log_fails)
check("a git log that fails mid-search is UNAVAILABLE with git's words, not NOT FOUND",
      report.status == UNAVAILABLE and any("bad object" in l for l in report.lines),
      "%s %s" % (report.status, report.lines))

git_absent = FakeRunner([
    ("rev-parse --git-dir", (0, ".git\n", "")),
    ("log --all --full-history -1 --format=%H", (0, "\n", "")),
    ("--name-only", (0, "docs/other.md\nREADME.md\n", "")),
])
report = finder.search_git("nowhere.md", "/repo", git_absent)
check("git reports NOT FOUND when no ref ever had the path", report.status == NOT_FOUND)

git_missing = FakeRunner([("rev-parse --git-dir", (128, "", "not a git repository"))])
report = finder.search_git("x.md", "/tmp", git_missing)
check("a non-repo is UNAVAILABLE, not NOT FOUND", report.status == UNAVAILABLE)

# The deletion commit's own tree no longer holds the content; the walk must
# keep going back to a commit that does.
git_walks_back = FakeRunner([
    ("rev-parse --git-dir", (0, ".git\n", "")),
    ("log --all --full-history -1 --format=%H", (0, "deadbeef\n", "")),
    ("log --all --full-history --format=%H|%ad|%s",
     (0, "deadbeef|2026-08-14|delete it\nfeedface|2026-08-13|write it\n", "")),
    ("log --all --full-history --format=%H|%P|%ct|%ad|%s",
     (0, "deadbeef|feedface|1786708800|2026-08-14|delete it\nfeedface|00000000|1786622400|2026-08-13|write it\n", "")),
    ("--date=short feedface", (0, "1786622400|2026-08-13|write it\n", "")),
    ("cat-file -e deadbeef:", (128, "", "does not exist")),
    ("cat-file -e feedface:", (0, "", "")),
])
report = finder.search_git("a/b.md", "/repo", git_walks_back)
check("git skips the deleting commit and cites one whose tree has the blob",
      report.status == FOUND and any("feedface" in c for c in report.recovery),
      str(report.recovery))
check("... and the date it records is that commit's, not the deletion's",
      getattr(report, "newest_date_held", None) == "2026-08-13",
      repr(getattr(report, "newest_date_held", None)))

# The documented absolute-path form. `git log` accepts an absolute pathspec,
# so the fast path succeeded and returned the absolute string; `cat-file`
# cannot address a blob that way, so every commit failed the tree check and
# git said NOT FOUND for a file it had the whole time.
git_absolute = FakeRunner([
    ("rev-parse --git-dir", (0, ".git\n", "")),
    ("rev-parse --show-toplevel", (0, "/repo\n", "")),
    ("log --all --full-history -1 --format=%H", (0, "abc123def\n", "")),
    ("log --all --full-history --format=%H|%ad|%s", (0, "abc123def|2026-08-14|retire review records\n", "")),
    ("log --all --full-history --format=%H|%P|%ct|%ad|%s", (0, "abc123def|00000000|1786708800|2026-08-14|retire review records\n", "")),
    # Only the repo-relative form can be addressed in a tree.
    ("cat-file -e abc123def:md-review-records/x/dispositions.md", (0, "", "")),
])
report = finder.search_git("/repo/md-review-records/x/dispositions.md", "/repo", git_absolute)
check("an absolute path inside the repository is searched by its repo-relative form",
      report.status == FOUND and report.recovery == ["git -C /repo show abc123def:md-review-records/x/dispositions.md"],
      "%s %s %s" % (report.status, report.lines, report.recovery))

git_outside = FakeRunner([
    ("rev-parse --git-dir", (0, ".git\n", "")),
    ("rev-parse --show-toplevel", (0, "/repo\n", "")),
])
report = finder.search_git("/elsewhere/a/b.md", "/repo", git_outside)
check("an absolute path outside the repository is UNAVAILABLE with the re-run instruction, not NOT FOUND",
      report.status == UNAVAILABLE and any("outside /repo" in l for l in report.lines)
      and any("re-run with the path relative" in l for l in report.lines),
      "%s %s" % (report.status, report.lines))
check("... and git was not asked to search for it",
      not any(" log " in c for c in git_outside.calls), str(git_outside.calls))


def git_fixture_repo(tmp):
    """A throwaway repository with a file that was modified, then merged past, then deleted.

        2026-08-10  A  add a/b.md
        2026-08-12  M  modify a/b.md            <- last commit that TOUCHED it
        2026-08-13  S  (side branch) add other.md
        2026-08-14  P  merge side into main     <- last commit whose TREE holds it
        2026-08-14  D  delete a/b.md
    """
    repo = Path(tmp, "repo")
    repo.mkdir()

    def git(*args, date=None):
        env = dict(os.environ)
        env.pop("GIT_DIR", None)
        if date:
            env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = date
        subprocess.run(["git", "-C", str(repo), "-c", "commit.gpgsign=false", "-c", "user.name=fixture",
                        "-c", "user.email=fixture@example.com"] + list(args),
                       check=True, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    git("init", "-q", "-b", "main")
    Path(repo, "a").mkdir()
    Path(repo, "a", "b.md").write_text("v1\n")
    git("add", "a/b.md")
    git("commit", "-q", "-m", "add a/b.md", date="2026-08-10T10:00:00")
    Path(repo, "a", "b.md").write_text("v2\n")
    git("commit", "-q", "-am", "modify a/b.md", date="2026-08-12T10:00:00")
    git("checkout", "-q", "-b", "side")
    Path(repo, "other.md").write_text("side\n")
    git("add", "other.md")
    git("commit", "-q", "-m", "add other.md", date="2026-08-13T10:00:00")
    git("checkout", "-q", "main")
    git("merge", "-q", "--no-ff", "-m", "merge side", "side", date="2026-08-14T10:00:00")
    git("rm", "-q", "a/b.md")
    git("commit", "-q", "-m", "delete a/b.md", date="2026-08-14T12:00:00")
    return repo


with tempfile.TemporaryDirectory() as tmp:
    repo = git_fixture_repo(tmp)
    merge_sha = subprocess.run(["git", "-C", str(repo), "rev-parse", "main^"],
                               check=True, stdout=subprocess.PIPE).stdout.decode().strip()
    report = finder.search_git("a/b.md", str(repo))
    check("real git: the commit cited is the merge whose tree last held the file",
          report.status == FOUND and report.recovery == ["git -C %s show %s:a/b.md" % (repo, merge_sha[:9])],
          "%s %s %s (merge is %s)" % (report.status, report.lines, report.recovery, merge_sha[:9]))
    check("real git: the date recorded is the merge's, 2026-08-14, not the modification's 2026-08-12",
          getattr(report, "newest_date_held", None) == "2026-08-14",
          repr(getattr(report, "newest_date_held", None)))
    report = finder.search_git(str(Path(repo, "a", "b.md")), str(repo))
    check("real git: the absolute form of a deleted in-repo file is FOUND",
          report.status == FOUND and report.recovery and report.recovery[0].endswith(":a/b.md"),
          "%s %s %s" % (report.status, report.lines, report.recovery))
    report = finder.search_git("/definitely/elsewhere/a/b.md", str(repo))
    check("real git: an absolute path outside the repository is UNAVAILABLE",
          report.status == UNAVAILABLE, "%s %s" % (report.status, report.lines))

# --------------------------------------------------------------------------
# transcripts
# --------------------------------------------------------------------------

transcripts_hit = FakeRunner([
    ("grep -rl", (0, "/home/x/.claude/projects/p/session.jsonl\n", "")),
    ("ssh", (0, "/home/nedlern/.claude/projects/p/box-session.jsonl\n", "")),
])
report = finder.search_transcripts("dispositions.md", "/nonexistent-dir", "nedlern@ned-box", transcripts_hit)
check("transcripts report FOUND on a box hit even when the Mac dir is absent",
      report.status == FOUND)
check("a transcript hit warns that the searcher's own session matches trivially",
      any("typed in it" in l for l in report.lines), str(report.lines))
check("an absent local transcripts dir is named, not silently skipped",
      any("does not exist" in line for line in report.lines), str(report.lines))

transcripts_box_down = FakeRunner([("ssh", (255, "", "ssh: connect to host ned-box port 22: No route to host\n"))])
report = finder.search_transcripts("x.md", "/nonexistent-dir", "nedlern@ned-box", transcripts_box_down)
check("an unreachable box is UNAVAILABLE, not NOT FOUND", report.status == UNAVAILABLE)

# The box grep runs for real, through a local bash, against a fake HOME. The
# first version was `grep ... 2>/dev/null | head -20`: a pipeline's status is
# its LAST command's, so a missing ~/.claude/projects came back as exit 0 and
# the report said it had searched it.
with tempfile.TemporaryDirectory() as tmp:
    mac_dir = Path(tmp, "mac-transcripts")
    mac_dir.mkdir()
    box_home = Path(tmp, "box-home")
    box_home.mkdir()

    box_no_dir = LocalShellRunner([], box_home)
    report = finder.search_transcripts("a/b.md", str(mac_dir), "nedlern@ned-box", box_no_dir)
    box_lines = [l for l in report.lines if l.startswith("the box")]
    check("a box with no ~/.claude/projects says so, never 'searched ..., no transcript mentions it'",
          box_lines == ["the box (nedlern@ned-box): ~/.claude/projects does not exist there"],
          str(box_lines))
    box_script = [c for c in box_no_dir.calls if c.startswith("ssh")][0]
    check("the box grep is not piped, so its own exit status reaches the caller",
          "|" not in box_script, box_script)

    box_projects = Path(box_home, ".claude", "projects", "p")
    box_projects.mkdir(parents=True)
    Path(box_projects, "quiet.jsonl").write_text('{"text": "nothing relevant"}\n')
    box_empty = LocalShellRunner([], box_home)
    report = finder.search_transcripts("a/b.md", str(mac_dir), "nedlern@ned-box", box_empty)
    check("a box whose transcripts do not mention the path is searched and says so",
          any(l.startswith("the box") and "no transcript mentions it" in l for l in report.lines),
          str(report.lines))

    Path(box_projects, "session.jsonl").write_text('{"text": "read a/b.md today"}\n')
    box_hit = LocalShellRunner([], box_home)
    report = finder.search_transcripts("a/b.md", str(mac_dir), "nedlern@ned-box", box_hit)
    check("a box transcript that mentions the path is FOUND with the file named",
          report.status == FOUND and any("session.jsonl" in l for l in report.lines),
          str(report.lines))

    # One half searched and empty, the other half unsearchable. NOT FOUND means
    # "genuinely searched and does not have it", which this surface cannot
    # claim; the summary must list it under "Could NOT search".
    box_quiet_mac_absent = LocalShellRunner([], box_home)
    Path(box_projects, "session.jsonl").unlink()
    report = finder.search_transcripts("a/b.md", "/nonexistent-transcripts", "nedlern@ned-box", box_quiet_mac_absent)
    check("Mac dir absent + box searched and empty is UNAVAILABLE, not NOT FOUND",
          report.status == UNAVAILABLE, "%s %s" % (report.status, report.lines))
    summary = finder.render("a/b.md", [report])
    check("... and the summary lists transcripts under 'Could NOT search'",
          "Could NOT search: transcripts" in summary, summary)

check("_combine: a mix of NOT FOUND and UNAVAILABLE is UNAVAILABLE",
      finder._combine([NOT_FOUND, UNAVAILABLE]) == UNAVAILABLE and finder._combine([UNAVAILABLE, NOT_FOUND]) == UNAVAILABLE)
check("_combine: all parts searched and empty is NOT FOUND",
      finder._combine([NOT_FOUND, NOT_FOUND]) == NOT_FOUND)
check("_combine: FOUND wins over everything",
      finder._combine([UNAVAILABLE, FOUND, NOT_FOUND]) == FOUND)

transcripts_box_grep_fails = FakeRunner([("ssh", (2, "", "grep: /home/nedlern/.claude/projects/p: Permission denied\n"))])
report = finder.search_transcripts("a/b.md", "/nonexistent-dir", "nedlern@ned-box", transcripts_box_grep_fails)
check("a box grep that fails is UNAVAILABLE and quotes grep",
      report.status == UNAVAILABLE and any("grep over ~/.claude/projects failed" in l and "Permission denied" in l
                                           for l in report.lines),
      str(report.lines))

# --skip box exists because the box is asleep; the first version still sent
# the transcripts grep over ssh (only the Timeshift call honoured the skip),
# so the flag bought nothing but a ConnectTimeout wait.
skip_box = FakeRunner([("rev-parse --git-dir", (128, "", "not a git repository"))])
reports = finder.build_report("a/b.md", "/not-a-repo", "/nonexistent-transcripts", "nedlern@ned-box",
                              "/mnt/backup/timeshift/snapshots", finder.DEFAULT_BOX_SEARCH_ROOTS,
                              skip={"box", "timemachine"}, runner=skip_box)
check("--skip box sends nothing over ssh",
      not any(c.startswith("ssh") for c in skip_box.calls), str(skip_box.calls))
transcripts_report = [r for r in reports if r.surface == "transcripts"][0]
check("--skip box: the transcripts surface says its box half was not searched",
      any(l.startswith("the box: not searched") for l in transcripts_report.lines), str(transcripts_report.lines))
check("--skip box drops the Timeshift surface", not any(r.surface == "timeshift" for r in reports))

skip_timeshift = FakeRunner([
    ("rev-parse --git-dir", (128, "", "not a git repository")),
    ("ssh", (1, "", "")),
])
reports = finder.build_report("a/b.md", "/not-a-repo", "/nonexistent-transcripts", "nedlern@ned-box",
                              "/mnt/backup/timeshift/snapshots", finder.DEFAULT_BOX_SEARCH_ROOTS,
                              skip={"timeshift", "timemachine"}, runner=skip_timeshift)
check("--skip timeshift still greps the box's transcripts",
      sum(1 for c in skip_timeshift.calls if c.startswith("ssh")) == 1 and
      not any(r.surface == "timeshift" for r in reports),
      str(skip_timeshift.calls))

# --------------------------------------------------------------------------
# timeshift on the box
# --------------------------------------------------------------------------

timeshift_hit = FakeRunner([
    ("ssh", (0, "HIT /mnt/backup/timeshift/snapshots/2026-08-13_10-00-00/localhost/home/nedlern/Projects/nedschorus/a/b.md\n"
               "HIT /mnt/backup/timeshift/snapshots/2026-08-14_11-35-50/localhost/home/nedlern/Projects/nedschorus/a/b.md\n", "")),
])
report = finder.search_timeshift("a/b.md", "nedlern@ned-box", "/mnt/backup/timeshift/snapshots",
                                 finder.DEFAULT_BOX_SEARCH_ROOTS, timeshift_hit)
check("timeshift reports FOUND with the newest snapshot first",
      report.status == FOUND and "2026-08-14" in report.recovery[0], str(report.recovery))

# A fake runner cannot execute the shell this builds, so the one thing it CAN
# check is the text: a seat-directory root must reach the box with its glob
# unquoted. It shipped quoted once (found by inspecting the generated script,
# not by any passing test), which silently searched none of the seat dirs while
# the report still said "searched every snapshot under ...".
glob_probe = FakeRunner([("ssh", (0, "", ""))])
finder.search_timeshift("a/b.md", "nedlern@ned-box", "/root",
                        finder.DEFAULT_BOX_SEARCH_ROOTS, glob_probe)
generated = glob_probe.calls[0]
check("a seat-directory root keeps its glob unquoted so the shell expands it",
      "/home/nedlern/agents/*" in generated and "'/home/nedlern/agents/*" not in generated
      and "agents/*'" not in generated,
      generated)
check("the suffix pattern reaches find as one quoted word, so the shell cannot expand its '*'",
      "-path '*/a/b.md'" in generated, generated)
check("the suffix search's find is not piped, so a find that fails is reported",
      "|" not in generated.replace("||", ""), generated)

# The generated script runs for real against a fake snapshot tree. The first
# version tested only <root>/<wanted>, so the documented fragment form
# ("dispositions.md") could never hit, and the surface said "searched every
# snapshot under ..." for a file that was in every snapshot.
with tempfile.TemporaryDirectory() as tmp:
    box = Path(tmp, "box")
    snapshots = Path(box, "mnt", "backup", "timeshift", "snapshots")
    for snap in ("2026-08-13_10-00-00", "2026-08-14_11-35-50"):
        for seat in ("seat-a", "seats/s1"):
            records = Path(snapshots, snap, "localhost", seat, "md-review-records", "x")
            records.mkdir(parents=True)
            Path(records, "dispositions.md").write_text("eleven deferred findings\n")
    roots = ("/seat-a", "/seats/*")

    def timeshift(wanted, root=str(snapshots)):
        runner = LocalShellRunner([], box)
        return finder.search_timeshift(wanted, "nedlern@ned-box", root, roots, runner)

    report = timeshift("md-review-records/x/dispositions.md")
    check("timeshift, real shell: the repo-relative form is FOUND, newest snapshot first",
          report.status == FOUND and "2026-08-14" in report.recovery[0], "%s %s" % (report.status, report.lines))
    report = timeshift("dispositions.md")
    check("timeshift, real shell: the documented fragment form is FOUND in the same snapshots",
          report.status == FOUND and any("2026-08-13" in l for l in report.lines) and "2026-08-14" in report.recovery[0],
          "%s %s" % (report.status, report.lines))
    check("timeshift, real shell: a seat-glob root is searched by suffix too",
          any("/seats/s1/" in l for l in report.lines), str(report.lines))
    report = timeshift("x/dispositions.md")
    check("timeshift, real shell: a two-component fragment is FOUND", report.status == FOUND, str(report.lines))
    report = timeshift("ispositions.md")
    check("timeshift, real shell: a partial component is NOT FOUND (suffix means whole components)",
          report.status == NOT_FOUND, "%s %s" % (report.status, report.lines))
    report = timeshift("nowhere.md")
    check("timeshift, real shell: an absent file is NOT FOUND after a real search",
          report.status == NOT_FOUND and any("searched every snapshot under" in l for l in report.lines),
          "%s %s" % (report.status, report.lines))
    report = timeshift("/seat-a/md-review-records/x/dispositions.md")
    check("timeshift, real shell: an absolute box path is tested exactly under each snapshot",
          report.status == FOUND, "%s %s" % (report.status, report.lines))
    report = timeshift("dispositions.md", root=str(Path(box, "no-such-root")))
    check("timeshift, real shell: a missing snapshot root is UNAVAILABLE",
          report.status == UNAVAILABLE and any("is the backup drive mounted" in l for l in report.lines),
          "%s %s" % (report.status, report.lines))

timeshift_timeout = FakeRunner([("ssh", (124, "", "timed out after 120s: ssh ..."))])
report = finder.search_timeshift("a/b.md", "nedlern@ned-box", "/mnt/backup/timeshift/snapshots",
                                 finder.DEFAULT_BOX_SEARCH_ROOTS, timeshift_timeout)
check("a Timeshift search that times out is UNAVAILABLE, not 'searched every snapshot'",
      report.status == UNAVAILABLE and any("did not complete" in l for l in report.lines),
      "%s %s" % (report.status, report.lines))

timeshift_probefail = FakeRunner([("ssh", (0, "PROBEFAIL /mnt/backup/timeshift/snapshots/2026-08-13_10-00-00/localhost/home/nedlern/Projects/nedschorus\n", ""))])
report = finder.search_timeshift("a/b.md", "nedlern@ned-box", "/mnt/backup/timeshift/snapshots",
                                 finder.DEFAULT_BOX_SEARCH_ROOTS, timeshift_probefail)
check("a find that failed under a snapshot directory makes the surface UNAVAILABLE",
      report.status == UNAVAILABLE and any("find failed under 1 snapshot directory" in l for l in report.lines),
      "%s %s" % (report.status, report.lines))

timeshift_empty = FakeRunner([("ssh", (0, "", ""))])
report = finder.search_timeshift("a/b.md", "nedlern@ned-box", "/mnt/backup/timeshift/snapshots",
                                 finder.DEFAULT_BOX_SEARCH_ROOTS, timeshift_empty)
check("timeshift reports NOT FOUND only after a real search", report.status == NOT_FOUND)

timeshift_no_root = FakeRunner([("ssh", (0, "NOROOT\n", ""))])
report = finder.search_timeshift("a/b.md", "nedlern@ned-box", "/mnt/backup/timeshift/snapshots",
                                 finder.DEFAULT_BOX_SEARCH_ROOTS, timeshift_no_root)
check("an unmounted backup drive on the box is UNAVAILABLE", report.status == UNAVAILABLE)

timeshift_down = FakeRunner([("ssh", (255, "", "ssh: connect to host ned-box port 22: No route to host\n"))])
report = finder.search_timeshift("a/b.md", "nedlern@ned-box", "/mnt/backup/timeshift/snapshots",
                                 finder.DEFAULT_BOX_SEARCH_ROOTS, timeshift_down)
check("an unreachable box is UNAVAILABLE and says the snapshots are fine",
      report.status == UNAVAILABLE and any("cannot see them" in l for l in report.lines), str(report.lines))

# --------------------------------------------------------------------------
# Time Machine — the surface with the password wall
# --------------------------------------------------------------------------

DESTINATION_INFO = (0, "Name          : My Passport for Mac\nKind          : Local\n"
                       "Mount Point   : /Volumes/My Passport for Mac\nID            : 8A26\n", "")
DISKUTIL_MOUNTED = (0, "   Device Node:               /dev/disk5s2\n"
                       "   Volume Name:               My Passport for Mac\n"
                       "   Mount Point:               /Volumes/My Passport for Mac\n", "")
SNAPSHOT_LIST = (0, "|   Name:        com.apple.TimeMachine.2026-08-12-202035.backup\n"
                    "|   Name:        com.apple.TimeMachine.2026-08-13-183101.backup\n"
                    "|   Name:        com.apple.TimeMachine.2026-08-15-152236.backup\n", "")

tm_no_password = FakeRunner([
    ("tmutil destinationinfo", DESTINATION_INFO),
    ("diskutil info", DISKUTIL_MOUNTED),
    ("diskutil apfs listSnapshots", SNAPSHOT_LIST),
    ("sudo -n true", (1, "", "sudo: a password is required\n")),
])
report = finder.search_time_machine("a/b.md", newest_date_held="2026-08-14", runner=tm_no_password)
check("Time Machine without a password is UNAVAILABLE, never NOT FOUND",
      report.status == UNAVAILABLE,
      "an agent told 'not found' stops looking; the file may well be in there")
check("it says plainly that this is a wall and not an empty result",
      any("not an empty result" in l for l in report.lines), str(report.lines))
check("it hands over the exact sudo command to run",
      any("mount_apfs" in c and "-o ro" in c for c in report.recovery), str(report.recovery))
# The range line legitimately names the newest snapshot on the disk; it is the
# CANDIDATE that must be the newest one at or before the date git last held the
# file, since anything after the deletion will not have it.
candidate_lines = [l for l in report.lines if l.startswith("best candidate")]
check("the candidate snapshot is the newest one at or before the deletion date",
      len(candidate_lines) == 1 and "2026-08-13" in candidate_lines[0],
      str(report.lines))
check("with a git date, the alternative offered is the next NEWER snapshot",
      any(l.startswith("next to try if it predates the file") and "2026-08-15" in l for l in report.lines),
      str(report.lines))

# Without a git date the newest snapshot is all we have, and it may postdate the
# deletion — the failure mode found by running the real script with --skip git.
tm_no_date = FakeRunner([
    ("tmutil destinationinfo", DESTINATION_INFO),
    ("diskutil info", DISKUTIL_MOUNTED),
    ("diskutil apfs listSnapshots", SNAPSHOT_LIST),
    ("sudo -n true", (1, "", "sudo: a password is required\n")),
])
undated = finder.search_time_machine("a/b.md", newest_date_held=None, runner=tm_no_date)
check("with no git date, the report admits the candidate may postdate the deletion",
      any("POSTDATE" in l for l in undated.lines), str(undated.lines))
check("with no git date, the alternative offered is the next OLDER snapshot",
      any(l.startswith("next to try if it postdates the deletion") and "2026-08-13" in l
          for l in undated.lines),
      str(undated.lines))
check("the device node comes from the volume name at runtime, never a remembered one",
      any("diskutil info" in c for c in tm_no_password.calls))

tm_absent = FakeRunner([
    ("tmutil destinationinfo", DESTINATION_INFO),
    ("diskutil info", (1, "", "Could not find disk: My Passport for Mac")),
])
report = finder.search_time_machine("a/b.md", runner=tm_absent)
check("a disconnected backup disk is UNAVAILABLE and says to reconnect it",
      report.status == UNAVAILABLE and any("reconnect" in l.lower() for l in report.lines),
      str(report.lines))

DISKUTIL_UNMOUNTED = (0, "   Device Node:               /dev/disk5s2\n"
                         "   Volume Name:               My Passport for Mac\n", "")
mount_attempts = {"n": 0}


class RemountRunner(FakeRunner):
    """Attached but unmounted; `diskutil mount` succeeds on the second look."""

    def __call__(self, argv, timeout=None, cwd=None):
        joined = " ".join(argv)
        self.calls.append(joined)
        if "diskutil mount" in joined:
            mount_attempts["n"] += 1
            return (0, "Volume mounted\n", "")
        if "diskutil info" in joined:
            return DISKUTIL_MOUNTED if mount_attempts["n"] else DISKUTIL_UNMOUNTED
        return FakeRunner.__call__(self, argv, timeout, cwd)


tm_remount = RemountRunner([
    ("tmutil destinationinfo", DESTINATION_INFO),
    ("diskutil apfs listSnapshots", SNAPSHOT_LIST),
    ("sudo -n true", (1, "", "sudo: a password is required\n")),
])
report = finder.search_time_machine("a/b.md", runner=tm_remount)
check("an attached-but-unmounted disk is mounted rather than given up on",
      mount_attempts["n"] == 1 and report.status == UNAVAILABLE and
      any("password" in l for l in report.lines),
      "should get past the mount and stop at the password wall, not at the mount")

mount_attempts["n"] = 0


class RefusesToMountRunner(RemountRunner):
    def __call__(self, argv, timeout=None, cwd=None):
        joined = " ".join(argv)
        if "diskutil mount" in joined:
            self.calls.append(joined)
            return (1, "", "Volume on disk5s2 failed to mount\n")
        if "diskutil info" in joined:
            self.calls.append(joined)
            return DISKUTIL_UNMOUNTED
        return FakeRunner.__call__(self, argv, timeout, cwd)


tm_wont_mount = RefusesToMountRunner([("tmutil destinationinfo", DESTINATION_INFO)])
report = finder.search_time_machine("a/b.md", runner=tm_wont_mount)
check("a disk that refuses to mount reports diskutil's own words",
      report.status == UNAVAILABLE and any("failed to mount" in l for l in report.lines),
      str(report.lines))

# Warm sudo: the branch that actually opens snapshots. The first version's
# probe returned None for a mount that failed AND for a file that was absent,
# so a mount_apfs refusal rendered as "searched ... and did not find it".
TM_MOUNT = finder.TIME_MACHINE_READONLY_MOUNT_POINT
TM_FIND = "find %s/Users" % TM_MOUNT

WARM = [
    ("tmutil destinationinfo", DESTINATION_INFO),
    ("diskutil info", DISKUTIL_MOUNTED),
    ("diskutil apfs listSnapshots", SNAPSHOT_LIST),
    ("sudo -n true", (0, "", "")),
    # The release is unprivileged and is `diskutil unmount`, not `umount`:
    # the fixture must not answer a command the script no longer runs.
    ("diskutil unmount", (0, "", "")),
]
tm_mount_refused = FakeRunner(WARM + [
    ("sudo -n mount_apfs", (1, "", "mount_apfs: volume could not be mounted: Resource busy\n")),
])
report = finder.search_time_machine("a/b.md", newest_date_held="2026-08-14", runner=tm_mount_refused)
check("a snapshot that will not mount is UNAVAILABLE, never 'searched ... and did not find it'",
      report.status == UNAVAILABLE and not any("did not find it" in l for l in report.lines),
      "%s %s" % (report.status, report.lines))
check("... naming the snapshot and quoting mount_apfs",
      any(l.startswith("could not search com.apple.TimeMachine.2026-08-13-183101.backup") and "Resource busy" in l
          for l in report.lines),
      str(report.lines))
check("... and handing over the manual mount command for it",
      any("mount_apfs -o ro -s com.apple.TimeMachine.2026-08-13-183101.backup" in c for c in report.recovery),
      str(report.recovery))
check("a refused mount is not followed by an umount of it",
      not any("umount" in c for c in tm_mount_refused.calls), str(tm_mount_refused.calls))

tm_warm_miss = FakeRunner(WARM + [
    ("sudo -n mount_apfs", (0, "", "")),
    (TM_FIND, (0, "", "")),
])
report = finder.search_time_machine("a/b.md", newest_date_held="2026-08-14", runner=tm_warm_miss)
check("with warm sudo, a snapshot that mounts and lacks the file is NOT FOUND, naming what was searched",
      report.status == NOT_FOUND and any(l.startswith("searched com.apple.TimeMachine.2026-08-13-183101.backup, "
                                                       "com.apple.TimeMachine.2026-08-12-202035.backup and did not find it")
                                         for l in report.lines),
      "%s %s" % (report.status, report.lines))
check("every mounted snapshot is released afterwards, with diskutil unmount and no sudo",
      sum(1 for c in tm_warm_miss.calls if c == "diskutil unmount " + TM_MOUNT) == 2
      and not any(c.startswith("sudo") and "umount" in c for c in tm_warm_miss.calls),
      str(tm_warm_miss.calls))

tm_warm_hit = FakeRunner(WARM + [
    ("sudo -n mount_apfs", (0, "", "")),
    (TM_FIND, (0, TM_MOUNT + "/Users/el/Projects/nedschorus/a/b.md\n", "")),
])
report = finder.search_time_machine("a/b.md", newest_date_held="2026-08-14", runner=tm_warm_hit)
check("with warm sudo, a hit is FOUND with the path inside the snapshot and a cp command",
      report.status == FOUND and any("holds /Users/el/Projects/nedschorus/a/b.md" in l for l in report.lines)
      and any(c.startswith("cp " + TM_MOUNT + "/Users/el/Projects/nedschorus/a/b.md") for c in report.recovery),
      "%s %s %s" % (report.status, report.lines, report.recovery))

tm_find_fails = FakeRunner(WARM + [
    ("sudo -n mount_apfs", (0, "", "")),
    (TM_FIND, (1, "", "find: " + TM_MOUNT + "/Users: No such file or directory\n")),
])
report = finder.search_time_machine("a/b.md", newest_date_held="2026-08-14", runner=tm_find_fails)
check("a mounted snapshot whose find fails is UNAVAILABLE quoting find (the /Users layout is unverified)",
      report.status == UNAVAILABLE and any("find said" in l and "No such file" in l for l in report.lines),
      "%s %s" % (report.status, report.lines))

tm_one_refused = FakeRunner(WARM + [
    ("mount_apfs -o ro -s com.apple.TimeMachine.2026-08-13-183101.backup", (1, "", "mount_apfs: Resource busy\n")),
    ("sudo -n mount_apfs", (0, "", "")),
    (TM_FIND, (0, "", "")),
])
report = finder.search_time_machine("a/b.md", newest_date_held="2026-08-14", runner=tm_one_refused)
check("one refused mount among searched-and-empty snapshots is UNAVAILABLE, listing both",
      report.status == UNAVAILABLE
      and any(l.startswith("could not search com.apple.TimeMachine.2026-08-13") for l in report.lines)
      and any(l == "searched com.apple.TimeMachine.2026-08-12-202035.backup and did not find it" for l in report.lines),
      "%s %s" % (report.status, report.lines))

tm_none = FakeRunner([("tmutil destinationinfo", (1, "", "tmutil: no destination configured"))])
report = finder.search_time_machine("a/b.md", runner=tm_none)
check("no configured destination is UNAVAILABLE", report.status == UNAVAILABLE)

# --------------------------------------------------------------------------
# the assembled report
# --------------------------------------------------------------------------

reports = [
    finder.SurfaceReport("git", FOUND, ["x"], ["git show abc:x"]),
    finder.SurfaceReport("timeshift", NOT_FOUND, ["searched"]),
    finder.SurfaceReport("time machine", UNAVAILABLE, ["needs your password"]),
]
text = finder.render("a/b.md", reports)
check("the summary names what was recoverable", "Recoverable from: git" in text, text)
check("the summary separates 'could not search' from 'not found'",
      "Could NOT search: time machine" in text and "not 'not found'" in text, text)

reports_all_blocked = [finder.SurfaceReport("git", NOT_FOUND, ["searched"])]
text = finder.render("a/b.md", reports_all_blocked)
check("a wholly empty search says so without claiming the file never existed",
      "No surface that could be searched has it." in text, text)

# --------------------------------------------------------------------------
# main(): the exit code is the same three-outcome contract, for wrappers
# that branch on $?. The first version returned 1 — "every surface that could
# be searched came back empty" — for a run in which no surface could be
# searched at all.
# --------------------------------------------------------------------------


def run_main(argv, runner):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = finder.main(argv, runner=runner)
    return code, out.getvalue()


NOT_A_REPO = ("rev-parse --git-dir", (128, "", "fatal: not a git repository"))
code, text = run_main(["a/b.md", "--repo", "/nonexistent-not-a-repo", "--transcripts-dir", "/nonexistent",
                       "--box-ssh-host", "", "--skip", "timemachine", "--skip", "localsnapshots"],
                      FakeRunner([NOT_A_REPO]))
check("exit 3 when no surface could be searched (git, transcripts, timeshift all UNAVAILABLE)",
      code == 3 and "Could NOT search: git, transcripts, timeshift" in text, "exit=%s\n%s" % (code, text))
check("... and the docstring's exit-code block promises exactly that",
      "3 when" in finder.__doc__ and "could NOT be searched" in finder.__doc__)

code, text = run_main(["a/b.md", "--repo", "/repo", "--skip", "transcripts", "--skip", "box",
                       "--skip", "timemachine", "--skip", "localsnapshots"],
                      git_absent)
check("exit 1 only when every surface that ran was searched and none has it",
      code == 1 and "Could NOT search" not in text, "exit=%s\n%s" % (code, text))

code, text = run_main(["md-review-records/x/dispositions.md", "--repo", "/repo", "--skip", "transcripts",
                       "--skip", "box", "--skip", "timemachine", "--skip", "localsnapshots"], git_found)
check("exit 0 when a surface FOUND it", code == 0 and "Recoverable from: git." in text, "exit=%s\n%s" % (code, text))

mixed = FakeRunner([
    ("rev-parse --git-dir", (0, ".git\n", "")),
    ("log --all --full-history -1 --format=%H", (0, "\n", "")),
    ("--name-only", (0, "docs/other.md\n", "")),
    ("ssh", (255, "", "ssh: connect to host ned-box port 22: No route to host\n")),
])
code, text = run_main(["a/b.md", "--repo", "/repo", "--skip", "transcripts", "--skip", "timemachine",
                       "--skip", "localsnapshots"], mixed)
check("exit 3 when git was searched and empty but the box could not be reached (not exhaustive)",
      code == 3 and "Could NOT search: timeshift" in text, "exit=%s\n%s" % (code, text))

check("exit_status: no surface at all is 3, not 1", finder.exit_status([]) == 3)

# The file's own Usage block once advertised --recover-to, which argparse
# rejected with exit 2. Every flag the docstring names must be one it takes.
documented_flags = sorted(set(re.findall(r"--[a-z][a-z-]+", finder.__doc__)))
help_out = io.StringIO()
with contextlib.redirect_stdout(help_out):
    try:
        finder.main(["--help"])
    except SystemExit:
        pass
accepted = set(re.findall(r"--[a-z][a-z-]+", help_out.getvalue()))
check("every flag the docstring names is one the parser accepts",
      documented_flags and all(flag in accepted for flag in documented_flags),
      "documented %s, accepted %s" % (documented_flags, sorted(accepted)))

code, text = run_main(["/repo/md-review-records/x/dispositions.md", "--repo", "/repo", "--skip", "transcripts",
                       "--skip", "box", "--skip", "timemachine", "--skip", "localsnapshots"], git_absolute)
check("the header shows the repo-relative form an absolute path was searched as",
      text.startswith("Searching every history this fleet keeps for: md-review-records/x/dispositions.md "
                      "(given as /repo/md-review-records/x/dispositions.md)"),
      text.splitlines()[0])


# --------------------------------------------------------------------------
# The fixed mount point, and the sudoers rule that fits it and nothing else
# --------------------------------------------------------------------------

SUDOERS_RULE_PATH = (MODULE_PATH.resolve().parent.parent / "config"
                     / "sudoers-mount-apfs-readonly-for-backup-recovery")
sudoers_text = SUDOERS_RULE_PATH.read_text() if SUDOERS_RULE_PATH.exists() else ""
alias_lines = [l for l in sudoers_text.splitlines() if l.startswith("Cmnd_Alias")]

check("the sudoers rule ships beside the code that depends on it", SUDOERS_RULE_PATH.exists(),
      "%s is missing, so the mount point below is pinned by a file nobody can read" % SUDOERS_RULE_PATH)
check("the rule permits exactly one command, and it is a read-only mount_apfs",
      len(alias_lines) == 1 and "/sbin/mount_apfs -o ro -s" in alias_lines[0],
      str(alias_lines))
check("the mount point the code uses is the one and only path the rule permits",
      len(alias_lines) == 1 and alias_lines[0].split()[-1] == TM_MOUNT,
      "rule ends %r, code uses %r — a mount anywhere else still asks for a password"
      % (alias_lines[0].split()[-1] if alias_lines else None, TM_MOUNT))
check("the fixed mount point is the /private/tmp path the rule was validated against",
      TM_MOUNT == "/private/tmp/nedschorus-backup-readonly-mount", TM_MOUNT)

# sudoers matches argument for argument, so the argv this script builds has to be
# the argv the rule spells: same flags, same order, that mount point last.
mount_calls = [c for c in tm_warm_miss.calls if "mount_apfs" in c]
check("the mount argv is exactly the shape the sudoers rule permits",
      mount_calls and mount_calls[0] ==
      "sudo -n mount_apfs -o ro -s com.apple.TimeMachine.2026-08-13-183101.backup "
      "/dev/disk5s2 " + TM_MOUNT,
      str(mount_calls[:1]))
check("the script mounts on the fixed path rather than only printing it",
      ("mkdir -p " + TM_MOUNT) in tm_warm_miss.calls, str(tm_warm_miss.calls))

tm_wall_paths = FakeRunner([
    ("tmutil destinationinfo", DESTINATION_INFO),
    ("diskutil info", DISKUTIL_MOUNTED),
    ("diskutil apfs listSnapshots", SNAPSHOT_LIST),
    ("sudo -n true", (1, "", "sudo: a password is required\n")),
])
wall_report = finder.search_time_machine("a/b.md", newest_date_held="2026-08-14", runner=tm_wall_paths)
hit_report = finder.search_time_machine("a/b.md", newest_date_held="2026-08-14",
                                        runner=FakeRunner(WARM + [
                                            ("sudo -n mount_apfs", (0, "", "")),
                                            (TM_FIND, (0, TM_MOUNT + "/Users/el/a/b.md\n", "")),
                                        ]))
every_tm_command = wall_report.recovery + hit_report.recovery
check("no printed Time Machine command names any other mount point",
      every_tm_command and all(TM_MOUNT in c for c in every_tm_command)
      and not any("/tmp/tm-ro" in c for c in every_tm_command),
      str(every_tm_command))
check("the printed release is diskutil unmount and carries no sudo",
      not any("sudo umount" in c or "sudo -n umount" in c for c in every_tm_command)
      and any("diskutil unmount " + TM_MOUNT in c for c in every_tm_command),
      str(every_tm_command))
check("the wall report names the sudoers rule as what removes the wall unattended",
      any("config/sudoers-mount-apfs-readonly-for-backup-recovery" in l for l in wall_report.lines),
      str(wall_report.lines))

# --------------------------------------------------------------------------
# --prompt-for-root: off by default, and the only thing that drops sudo's -n
# --------------------------------------------------------------------------

COLD_THEN_PROMPTED = [
    ("tmutil destinationinfo", DESTINATION_INFO),
    ("diskutil info", DISKUTIL_MOUNTED),
    ("diskutil apfs listSnapshots", SNAPSHOT_LIST),
    ("sudo -n true", (1, "", "sudo: a password is required\n")),
    # "sudo mount_apfs" is not a substring of "sudo -n mount_apfs", so this
    # entry answers the prompting form of the mount and only that form.
    ("sudo mount_apfs", (0, "", "")),
    ("diskutil unmount", (0, "", "")),
    (TM_FIND, (0, TM_MOUNT + "/Users/el/Projects/nedschorus/a/b.md\n", "")),
]

tm_cold_default = FakeRunner(COLD_THEN_PROMPTED)
report = finder.search_time_machine("a/b.md", newest_date_held="2026-08-14", runner=tm_cold_default)
check("without --prompt-for-root a cold sudo stops at the wall, as an unattended run must",
      report.status == UNAVAILABLE and any("needs your password" in l for l in report.lines),
      "%s %s" % (report.status, report.lines))
check("... and no sudo without -n is ever run, so an unattended run cannot hang on a prompt",
      not any(c.startswith("sudo ") and not c.startswith("sudo -n ") for c in tm_cold_default.calls),
      str(tm_cold_default.calls))

tm_cold_prompted = FakeRunner(COLD_THEN_PROMPTED)
report = finder.search_time_machine("a/b.md", newest_date_held="2026-08-14",
                                    runner=tm_cold_prompted, prompt_for_root=True)
check("with --prompt-for-root a cold sudo is crossed and the snapshot is searched",
      report.status == FOUND
      and any("holds /Users/el/Projects/nedschorus/a/b.md" in l for l in report.lines),
      "%s %s" % (report.status, report.lines))
check("... by running the mount itself, without -n, so sudo can ask at the terminal",
      any(c == "sudo mount_apfs -o ro -s com.apple.TimeMachine.2026-08-13-183101.backup "
               "/dev/disk5s2 " + TM_MOUNT for c in tm_cold_prompted.calls)
      and not any("sudo -n mount_apfs" in c for c in tm_cold_prompted.calls),
      str(tm_cold_prompted.calls))
check("... and the report says the password was asked for, not that sudo was already warm",
      any("--prompt-for-root asked at the terminal" in l for l in report.lines)
      and not any("already-warm" in l for l in report.lines),
      str(report.lines))
check("... and what it mounted is still released with diskutil unmount",
      any(c == "diskutil unmount " + TM_MOUNT for c in tm_cold_prompted.calls),
      str(tm_cold_prompted.calls))

tm_warm_prompted = FakeRunner(WARM + [("sudo mount_apfs", (0, "", "")), (TM_FIND, (0, "", ""))])
report = finder.search_time_machine("a/b.md", newest_date_held="2026-08-14",
                                    runner=tm_warm_prompted, prompt_for_root=True)
check("with --prompt-for-root and a credential already cached, the search still runs",
      report.status == NOT_FOUND, "%s %s" % (report.status, report.lines))

code, text = run_main(["a/b.md", "--repo", "/repo", "--skip", "localsnapshots", "--skip", "git",
                       "--skip", "transcripts", "--skip", "box", "--prompt-for-root"],
                      FakeRunner(COLD_THEN_PROMPTED))
check("--prompt-for-root reaches the Time Machine surface from the command line",
      code == 0 and "Recoverable from: time machine." in text, "exit=%s\n%s" % (code, text))

code, text = run_main(["a/b.md", "--repo", "/repo", "--skip", "localsnapshots", "--skip", "git",
                       "--skip", "transcripts", "--skip", "box"], FakeRunner(COLD_THEN_PROMPTED))
check("the flag is off by default: the identical run without it stops at the wall",
      code == 3 and "Could NOT search: time machine" in text, "exit=%s\n%s" % (code, text))

# --------------------------------------------------------------------------
# The spoken line, and the four conditions that keep it rare
# --------------------------------------------------------------------------

DELETED_2026_08_13_NOON = ("--diff-filter=D", (0, "20260813120000\n", ""))
SNAPSHOT_BEFORE = "com.apple.TimeMachine.2026-08-12-202035.backup"
SNAPSHOT_SAME_DAY_AFTER = "com.apple.TimeMachine.2026-08-13-183101.backup"


def tm_wall_report(snapshots=(SNAPSHOT_BEFORE, SNAPSHOT_SAME_DAY_AFTER)):
    """The report shape the Time Machine surface hands back at the password wall."""
    wall = finder.SurfaceReport("time machine", UNAVAILABLE, ["reading INSIDE one needs your password"])
    wall.root_credential_needed = True
    wall.snapshots_enumerated = list(snapshots)
    return wall


def tm_report_without_the_wall_mark(status, line):
    """A Time Machine report that stopped somewhere OTHER than the credential.

    It carries the enumerated snapshots too, so the only thing separating it
    from the report above is the mark itself. Without that the condition-2
    cases would pass merely because the attribute was absent, and a gate that
    spoke for every UNAVAILABLE Time Machine report would slip through them.
    """
    report = finder.SurfaceReport("time machine", status, [line])
    report.snapshots_enumerated = [SNAPSHOT_BEFORE, SNAPSHOT_SAME_DAY_AFTER]
    return report


def spoken(wanted, reports, table=(DELETED_2026_08_13_NOON,), skip=()):
    return finder.speech_line_when_root_password_is_needed(
        wanted, reports, "/repo", skip, FakeRunner(list(table)))


missed = [finder.SurfaceReport("git", NOT_FOUND, ["searched"]),
          finder.SurfaceReport("transcripts", NOT_FOUND, ["searched"])]

line = spoken("docs/a/b.md", missed + [tm_wall_report()])
check("all four conditions met: there is a line to speak",
      line is not None, "the announce half of this change does nothing if this never fires")
check("... naming the tool first and the file last, in one short sentence",
      line and line.startswith(finder.SPOKEN_TOOL_NAME) and line.endswith("b.md")
      and "\n" not in line and len(line.split()) < 20,
      repr(line))
check("... and it speaks the basename, not a path nobody can follow read aloud",
      line and "docs/" not in line, repr(line))

check("condition 1 — a surface that FOUND it means nobody is needed",
      spoken("docs/a/b.md",
             missed + [finder.SurfaceReport("git", FOUND, ["x"], ["git show a:x"]), tm_wall_report()])
      is None)
check("condition 1 — a surface that could NOT be searched does not excuse the wall",
      spoken("docs/a/b.md",
             [finder.SurfaceReport("timeshift", UNAVAILABLE, ["box asleep"]), tm_wall_report()])
      is not None,
      "an unreachable box leaves him just as needed; only a FOUND makes him unnecessary")

check("condition 2 — no wall mark, no line: a warm sudo searched and never met one",
      spoken("docs/a/b.md",
             missed + [tm_report_without_the_wall_mark(NOT_FOUND, "searched")]) is None)
check("condition 2 — a disconnected disk is UNAVAILABLE but is not a credential wall",
      spoken("docs/a/b.md",
             missed + [tm_report_without_the_wall_mark(UNAVAILABLE, "reconnect it")]) is None,
      "speaking here sends him to type a password at a disk that is not plugged in")

check("condition 3 — a path git never tracked has no deletion commit, so no line",
      spoken("docs/a/b.md", missed + [tm_wall_report()], table=()) is None,
      "no deletion commit means no bound, so no backup can be shown to predate anything")
check("condition 3 — every snapshot postdating the deletion means the password cannot help",
      spoken("docs/a/b.md", missed + [tm_wall_report(snapshots=(SNAPSHOT_SAME_DAY_AFTER,))]) is None,
      "18:31 is after a 12:00 deletion; comparing DATES rather than timestamps speaks wrongly here")
check("condition 3 — the bound is a timestamp, so a same-day EARLIER snapshot does count",
      spoken("docs/a/b.md",
             missed + [tm_wall_report(snapshots=("com.apple.TimeMachine.2026-08-13-090000.backup",))])
      is not None)
check("condition 3 — skipping git skips the bound rather than asking git behind the flag's back",
      spoken("docs/a/b.md", missed + [tm_wall_report()], skip={"git"}) is None)

check("condition 4 — a bare filename could not have used the mount anyway",
      spoken("b.md", missed + [tm_wall_report()]) is None)
check("condition 4 — an absolute path is a known path and does qualify",
      spoken("/Users/el/docs/a/b.md", missed + [tm_wall_report()]) is not None)

SPEAKS = [
    ("rev-parse --git-dir", (0, ".git\n", "")),
    ("log --all --full-history -1 --format=%H", (0, "\n", "")),
    ("--name-only", (0, "docs/other.md\n", "")),
    DELETED_2026_08_13_NOON,
    ("tmutil destinationinfo", DESTINATION_INFO),
    ("diskutil info", DISKUTIL_MOUNTED),
    ("diskutil apfs listSnapshots", SNAPSHOT_LIST),
    ("sudo -n true", (1, "", "sudo: a password is required\n")),
    ("say", (0, "", "")),
]

speaking_runner = FakeRunner(SPEAKS)
finder.build_report("docs/a/b.md", "/repo", "/nonexistent", "", "/snap", (),
                    skip={"localsnapshots", "transcripts", "box"}, runner=speaking_runner)
said = [c for c in speaking_runner.calls if c.startswith("say ")]
check("a whole run that hits the wall speaks, once, without an agent in between",
      len(said) == 1 and "b.md" in said[0] and finder.SPOKEN_TOOL_NAME in said[0],
      str(speaking_runner.calls))

silent_runner = FakeRunner(SPEAKS + [("sudo mount_apfs", (0, "", "")),
                                     ("diskutil unmount", (0, "", "")),
                                     (TM_FIND, (0, "", ""))])
finder.build_report("docs/a/b.md", "/repo", "/nonexistent", "", "/snap", (),
                    skip={"localsnapshots", "transcripts", "box"}, runner=silent_runner,
                    prompt_for_root=True)
check("--prompt-for-root never speaks: the person is already at the terminal",
      not any(c.startswith("say ") for c in silent_runner.calls), str(silent_runner.calls))

print()
if failures:
    print("%d case(s) failed: %s" % (len(failures), ", ".join(failures)))
    sys.exit(1)
print("all cases passed")
