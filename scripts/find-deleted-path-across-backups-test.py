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
import os
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
