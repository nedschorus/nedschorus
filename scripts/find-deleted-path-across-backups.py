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
surfaces existed. This script means no future agent has to know: it searches all
four and says plainly which ones it could not search, and why.

THE FOUR SURFACES, cheapest first:

  1. git          — every ref in this repo, full history, including paths that
                    no commit reachable from HEAD still contains.
  2. transcripts  — agent session JSONL under ~/.claude/projects, on this Mac
                    AND on the box. A file's content often survives in the
                    transcript of the session that wrote or read it, even when
                    every copy on disk is gone.
  3. Timeshift    — snapshots on ned-box at /mnt/backup/timeshift/snapshots.
                    Ordinary world-readable directories: no privilege needed.
  4. Time Machine — snapshots on the Mac's backup disk. Enumerating them needs
                    no privilege; READING INSIDE ONE NEEDS ROOT (measured
                    2026-08-23: `sudo mount_apfs -o ro` refused without a
                    password). See the honesty contract below.

THE HONESTY CONTRACT. Every surface reports one of three outcomes, and never
conflates the second with the third:

  FOUND        — with the exact command that recovers the content.
  NOT FOUND    — this surface was genuinely searched and does not have it.
  UNAVAILABLE  — this surface could NOT be searched, with the reason and the
                 command that would fix it.

A surface that cannot be read must never render as "not found". That distinction
is the whole point: an agent told "not in Time Machine" stops looking, and an
agent told "Time Machine needs your password, here is the command" asks for it.

READ-ONLY BY CONSTRUCTION. This script only lists, reads, and copies out. It
never writes backup state, which agents are forbidden to do
(.claude/hooks/backup-and-snapshot-write-guard.py holds the tool path; the rule
binds shell commands too). The single state-changing call it can make is
`diskutil mount` on the Time Machine destination — mounting a disk the user
already attached, which is how you read a backup, not a modification of one.
It is attempted only when the destination is attached but unmounted, because
the user's disk does go offline and a script that gives up there is useless to
him (user-ruled 2026-08-23).

NO HARDCODED DEVICE NODES. `/dev/disk5s2` was the backup volume on 2026-08-23;
device numbers reshuffle across replugs. Everything resolves at runtime from the
destination name that `tmutil destinationinfo` reports.

Usage:
  python3 scripts/find-deleted-path-across-backups.py <path>
  python3 scripts/find-deleted-path-across-backups.py <path> --skip box
  python3 scripts/find-deleted-path-across-backups.py <path> --recover-to DIR

<path> may be repo-relative ("docs/issues/46-x.md"), absolute, or any trailing
fragment of a path ("dispositions.md"). Fragments match by path suffix.

Exit code is 0 when at least one surface FOUND it, 1 when every surface that
could be searched came back empty, and 2 on a usage error.
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
        out = ["%-14s %s" % (self.surface, self.status)]
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
# Surface 1 — git
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

    paths = _git_candidate_paths(wanted, repo, runner)
    if not paths:
        return SurfaceReport("git", NOT_FOUND, ["no ref in %s has ever contained a path matching %r" % (repo, wanted)])

    lines = []
    recovery = []
    deletion_dates = []
    for path in paths:
        commit = _git_newest_commit_holding(path, repo, runner)
        if commit is None:
            continue
        sha, date, subject = commit
        lines.append("%s" % path)
        lines.append("    last held by %s (%s) %s" % (sha[:9], date, subject[:70]))
        recovery.append("git -C %s show %s:%s" % (shlex.quote(repo), sha[:9], shlex.quote(path)))
        deletion_dates.append(date)

    if not lines:
        return SurfaceReport("git", NOT_FOUND, ["matching paths appear in history but no commit still holds their content"])

    report = SurfaceReport("git", FOUND, lines, recovery)
    # The newest date on which git still had the file bounds where to look in
    # the filesystem backups: any snapshot after it is unlikely to help.
    report.newest_date_held = max(deletion_dates) if deletion_dates else None
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

    code, out, _ = runner(
        ["git", "-C", repo, "log", "--all", "--full-history", "--name-only", "--format="],
        timeout=LONG_TIMEOUT_SECONDS,
    )
    if code != 0:
        return []
    seen = []
    for line in out.splitlines():
        line = line.strip()
        if not line or line in seen:
            continue
        if path_matches(line, wanted):
            seen.append(line)
    return seen


def _git_newest_commit_holding(path, repo, runner):
    """The newest commit whose tree actually contains `path`.

    Not simply "the newest commit touching it": that commit is usually the one
    that DELETED it, whose tree no longer has the content. Walking back until a
    tree really holds the blob also survives merges, where `<sha>^` picks only
    the first parent and can pick the wrong side.
    """
    code, out, _ = runner(
        ["git", "-C", repo, "log", "--all", "--full-history", "--format=%H|%ad|%s", "--date=short", "--", path],
        timeout=LONG_TIMEOUT_SECONDS,
    )
    if code != 0:
        return None
    for line in out.splitlines():
        parts = line.split("|", 2)
        if len(parts) != 3:
            continue
        sha, date, subject = parts
        exists, _, _ = runner(["git", "-C", repo, "cat-file", "-e", "%s:%s" % (sha, path)])
        if exists == 0:
            return sha, date, subject
    return None


# --------------------------------------------------------------------------
# Surface 2 — agent transcripts, on this Mac and on the box
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
# Surface 3 — Timeshift on the box
# --------------------------------------------------------------------------

def search_timeshift(wanted, box_ssh_host, snapshot_root, search_roots, runner=run_command):
    """Test the path under every Timeshift snapshot on the box.

    Timeshift stores a snapshot as an ordinary directory tree rooted at
    <snapshot>/localhost/<the absolute path it had>, world-readable (verified
    2026-08-23: drwxr-xr-x, and passwordless sudo exists there anyway). So this
    surface needs no privilege at all — the opposite of Time Machine.

    A repo-relative path is tested under each configured root because the same
    relative path exists under several seats on the box.
    """
    if not box_ssh_host:
        return SurfaceReport("timeshift", UNAVAILABLE, ["not searched — no ssh host given (--skip box, or an empty --box-ssh-host)"])

    # Quote the CALLER's path, never the roots. The roots are constants that
    # deliberately carry a `*` (one seat per directory on the box), and
    # shlex.quote would wrap that glob in single quotes, making it a literal
    # asterisk that matches nothing — a surface reporting "searched every
    # snapshot" while never having looked at the seat directories. An unquoted
    # `*` still expands when the rest of the word is quoted.
    if wanted.startswith("/"):
        probes = [shlex.quote(wanted)]
    else:
        probes = ["%s/%s" % (root, shlex.quote(wanted)) for root in search_roots]

    script_lines = ["set -u", "ROOT=%s" % shlex.quote(snapshot_root)]
    script_lines.append('if [ ! -d "$ROOT" ]; then echo "NOROOT"; exit 0; fi')
    script_lines.append('for snap in "$ROOT"/*; do')
    script_lines.append('  [ -d "$snap" ] || continue')
    for probe in probes:
        script_lines.append('  for target in "$snap/localhost"%s; do' % probe)
        script_lines.append('    if [ -e "$target" ]; then echo "HIT $target"; fi')
        script_lines.append("  done")
    script_lines.append("done")
    remote = "\n".join(script_lines)

    code, out, stderr = runner(
        ["ssh", "-o", "ConnectTimeout=10", "-o", "BatchMode=yes", box_ssh_host, remote],
        timeout=LONG_TIMEOUT_SECONDS,
    )
    if code == 255:
        first = stderr.strip().splitlines()[0] if stderr.strip() else "ssh failed"
        return SurfaceReport(
            "timeshift",
            UNAVAILABLE,
            ["the box (%s) is unreachable — %s" % (box_ssh_host, first),
             "the snapshots are fine; this machine just cannot see them right now"],
        )
    if "NOROOT" in out:
        return SurfaceReport("timeshift", UNAVAILABLE, ["%s does not exist on %s — is the backup drive mounted?" % (snapshot_root, box_ssh_host)])

    hits = sorted({line[4:].strip() for line in out.splitlines() if line.startswith("HIT ")}, reverse=True)
    if not hits:
        return SurfaceReport("timeshift", NOT_FOUND, ["searched every snapshot under %s on %s" % (snapshot_root, box_ssh_host)])

    lines = ["%d snapshot(s) on %s still have it, newest first:" % (len(hits), box_ssh_host)]
    for hit in hits[:5]:
        lines.append("    " + hit)
    if len(hits) > 5:
        lines.append("    ... and %d older" % (len(hits) - 5))
    recovery = ["scp %s:%s ." % (box_ssh_host, shlex.quote(hits[0]))]
    return SurfaceReport("timeshift", FOUND, lines, recovery)


# --------------------------------------------------------------------------
# Surface 4 — Time Machine on this Mac
# --------------------------------------------------------------------------

def search_time_machine(wanted, newest_date_held=None, snapshot_limit=DEFAULT_TIME_MACHINE_SNAPSHOT_LIMIT, runner=run_command):
    """Enumerate Time Machine snapshots, and read inside them only if root is free.

    The measured split (2026-08-23): `tmutil` and `diskutil apfs listSnapshots`
    both answer unprivileged, but `sudo mount_apfs -o ro -s <snapshot>` refuses
    without a password, so the CONTENT of a snapshot is unreachable to an
    unattended agent. This function therefore always enumerates, tries a
    non-interactive `sudo -n` (which succeeds when the user has recently
    authenticated), and otherwise hands back the exact command to run rather
    than reporting an empty search.
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
    if can_sudo != 0:
        return SurfaceReport(
            "time machine",
            UNAVAILABLE,
            ["%d snapshots present, %s .. %s — enumerated fine, but reading INSIDE one needs your password"
             % (len(snapshots), snapshots[-1], snapshots[0]),
             "this is a real wall, not an empty result: the file may well be in there",
             _candidate_line(candidates[0], dated_by_git),
             _alternative_line(snapshots, candidates[0], dated_by_git)],
            ["mkdir -p /tmp/tm-ro && sudo mount_apfs -o ro -s %s %s /tmp/tm-ro && ls /tmp/tm-ro"
             % (candidates[0], device),
             "# then look for the path under /tmp/tm-ro, and: sudo umount /tmp/tm-ro"],
        )

    lines = ["%d snapshots present; opened %d with an already-warm sudo" % (len(snapshots), len(candidates))]
    hits = []
    for snapshot in candidates:
        hit = _time_machine_probe(snapshot, device, wanted, runner)
        if hit:
            hits.append((snapshot, hit))
    if not hits:
        lines.append("searched %s and did not find it" % ", ".join(candidates))
        return SurfaceReport("time machine", NOT_FOUND, lines)
    for snapshot, hit in hits:
        lines.append("%s holds %s" % (snapshot, hit))
    recovery = [
        "mkdir -p /tmp/tm-ro && sudo mount_apfs -o ro -s %s %s /tmp/tm-ro" % (hits[0][0], device),
        "cp /tmp/tm-ro%s . && sudo umount /tmp/tm-ro" % hits[0][1],
    ]
    return SurfaceReport("time machine", FOUND, lines, recovery)


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


def _time_machine_probe(snapshot, device, wanted, runner):
    mount_point = "/tmp/find-deleted-path-across-backups-ro"
    runner(["mkdir", "-p", mount_point])
    code, _, _ = runner(["sudo", "-n", "mount_apfs", "-o", "ro", "-s", snapshot, device, mount_point], timeout=LONG_TIMEOUT_SECONDS)
    if code != 0:
        return None
    try:
        if wanted.startswith("/"):
            probe = mount_point + wanted
            exists, _, _ = runner(["test", "-e", probe])
            return wanted if exists == 0 else None
        # Assumes a mounted Time Machine snapshot exposes /Users at its root.
        # That is the documented layout, but it is UNVERIFIED here: confirming it
        # needs the password this whole branch exists because we do not have.
        found, out, _ = runner(
            ["find", mount_point + "/Users", "-path", "*/" + wanted, "-maxdepth", "12"],
            timeout=LONG_TIMEOUT_SECONDS,
        )
        for line in out.splitlines():
            if line.strip():
                return line.strip()[len(mount_point):]
        return None
    finally:
        runner(["sudo", "-n", "umount", mount_point], timeout=LONG_TIMEOUT_SECONDS)


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


def build_report(wanted, repo, transcripts_dir, box_ssh_host, snapshot_root, search_roots, skip=(), runner=run_command):
    reports = []
    newest_date_held = None

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
        reports.append(search_time_machine(wanted, newest_date_held, runner=runner))
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


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Find a deleted path across git, agent transcripts, Timeshift and Time Machine.",
    )
    parser.add_argument("path", help="repo-relative, absolute, or any trailing fragment of the path")
    parser.add_argument("--repo", default=os.environ.get("FIND_DELETED_PATH_REPO", "."),
                        help="git repository to search (default: current directory)")
    parser.add_argument("--transcripts-dir", default=os.environ.get("FIND_DELETED_PATH_TRANSCRIPTS_DIR", DEFAULT_TRANSCRIPTS_DIR))
    parser.add_argument("--box-ssh-host", default=os.environ.get("FIND_DELETED_PATH_BOX_SSH_HOST", DEFAULT_BOX_SSH_HOST))
    parser.add_argument("--timeshift-snapshot-root", default=os.environ.get("FIND_DELETED_PATH_TIMESHIFT_SNAPSHOT_ROOT", DEFAULT_TIMESHIFT_SNAPSHOT_ROOT))
    parser.add_argument("--skip", action="append", default=[],
                        choices=["git", "transcripts", "box", "timeshift", "timemachine"],
                        help="skip a surface (repeatable); 'box' skips everything on the box — "
                             "its transcripts as well as Timeshift — so nothing is sent over ssh")
    args = parser.parse_args(argv)

    # One form for every surface: an absolute path inside the repository is
    # searched for by its repo-relative name, and the header says so.
    wanted, _ = _repo_relative_form(args.path, args.repo)
    shown = wanted if wanted == args.path else "%s (given as %s)" % (wanted, args.path)

    reports = build_report(
        wanted,
        args.repo,
        args.transcripts_dir,
        args.box_ssh_host,
        args.timeshift_snapshot_root,
        DEFAULT_BOX_SEARCH_ROOTS,
        skip=set(args.skip),
    )
    print(render(shown, reports))
    return 0 if any(r.status == FOUND for r in reports) else 1


if __name__ == "__main__":
    sys.exit(main())
