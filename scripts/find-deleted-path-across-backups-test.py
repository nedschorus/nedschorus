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

import importlib.util
import sys
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


# --------------------------------------------------------------------------
# path matching
# --------------------------------------------------------------------------

check("suffix match on a full path", finder.path_matches("a/b/c.md", "a/b/c.md"))
check("suffix match on a trailing fragment", finder.path_matches("docs/a/b/c.md", "b/c.md"))
check("suffix match on a bare basename", finder.path_matches("docs/a/b/c.md", "c.md"))
check("no match on a partial component",
      not finder.path_matches("docs/notes.md", "otes.md"),
      "matching mid-component would make 'notes.md' find 'my-notes.md'")

# --------------------------------------------------------------------------
# git
# --------------------------------------------------------------------------

git_found = FakeRunner([
    ("rev-parse --git-dir", (0, ".git\n", "")),
    ("log --all --full-history -1 --format=%H", (0, "abc123def\n", "")),
    ("log --all --full-history --format=%H|%ad|%s", (0, "abc123def|2026-08-14|retire review records\n", "")),
    ("cat-file -e", (0, "", "")),
])
report = finder.search_git("md-review-records/x/dispositions.md", "/repo", git_found)
check("git reports FOUND for a deleted path still in history", report.status == FOUND)
check("git hands back a runnable recovery command",
      any(c.startswith("git -C") and " show " in c for c in report.recovery),
      str(report.recovery))
check("git records the last date it held the file (bounds the backup search)",
      getattr(report, "newest_date_held", None) == "2026-08-14")

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
    ("cat-file -e deadbeef:", (128, "", "does not exist")),
    ("cat-file -e feedface:", (0, "", "")),
])
report = finder.search_git("a/b.md", "/repo", git_walks_back)
check("git skips the deleting commit and cites one whose tree has the blob",
      report.status == FOUND and any("feedface" in c for c in report.recovery),
      str(report.recovery))

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
      "/home/nedlern/agents/*/" in generated and "'/home/nedlern/agents/*" not in generated,
      generated)

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

print()
if failures:
    print("%d case(s) failed: %s" % (len(failures), ", ".join(failures)))
    sys.exit(1)
print("all cases passed")
