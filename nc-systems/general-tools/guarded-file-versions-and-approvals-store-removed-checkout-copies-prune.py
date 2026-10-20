#!/usr/bin/env python3
"""Delete the guarded-file hook's copies of versions a commit now holds, and its approved copies
of files in checkouts that no longer exist.

The hook, .claude/hooks/guarded-file-unapproved-change-afterward-backup-and-ask-hook.py, keeps
this machine's directory of the log-store kind guarded-file-versions-and-approvals/. For every
guarded file it has seen, the directory mirrors the file's absolute path and holds `approved`,
`log` and one copy per version git did not hold when the hook saw it, named by the version's
git blob id. This program runs once a day on each machine, for that machine's own directory,
since only that machine has the checkouts its paths name and can tell whether one still exists.

    python3 <this file> [--dry-run]

A real run prints `deleting <copy path>`, flushed, before it deletes each copy, so the log
names every copy a run stopped part way may have deleted; then a line for each removed checkout
whose copies it deleted, with their bytes, and a summary line. --dry-run prints the same lines,
with "would delete" for "deleted", and deletes nothing.

WHEN A COMMIT HOLDS A COPY'S VERSION. A copy whose blob a commit reachable from a durable ref
of the path's repository holds is deleted, approved or not, in live and removed checkouts
alike, since the hook's --restore and its diffs read such a version back from git. The durable
refs are the branches, tags and remote-tracking branches, and each worktree's HEAD, as
blobs_durable_refs_hold in the hook lists them. refs/work-snapshots/* and refs/stash are not
durable, since they are deleted within hours, so a version only they hold, like a blob only
staged, keeps its copy. The path's repository is the git repository enclosing the path, or,
when the path's directory is gone, its nearest directory that still exists: so the
repository of a removed worktree under the main clone's .claude/worktrees/ is the main clone,
which shares its commits. A path that no repository encloses, such as one under a removed
~/agents/<seat>, has no commit that holds its versions, and only the rules below apply to it.

WHEN A CHECKOUT NO LONGER EXISTS. The store records neither a file's checkout nor its git
directory, so the checkout is found from the path. A file whose directory still exists belongs
to a checkout that still exists, or to no checkout; its copies that no commit holds are kept,
since the hook's --restore may need them to put back a file deleted on a branch. Otherwise the
first missing directory on the file's path stands for its checkout, and that checkout no longer
exists when either
- no checkout encloses the nearest directory that still exists, as for ~/agents/<seat>; or
- that enclosing checkout's git ignores the missing directory, as the main clone ignores
  .claude/worktrees/, so the missing directory was a checkout of its own.
A missing directory that git does not ignore was the enclosing checkout's own, deleted on a
branch, and its copies are kept. A directory counts as missing only when the system says it does
not exist; when it cannot tell, as for a directory this process may not search, the path's copies
are kept and the failure is reported. So are the copies of a path under a volume that may not be
mounted: a path under /Volumes/<name>, /mnt/<name> or /media/<name> whose <name> directory is
missing or empty. A removed checkout that was the only content of its volume is kept too, and
reported. The hook's files outside any
checkout, ~/.claude/CLAUDE.md and ~/.claude/settings.json, are never pruned.

WHAT IS KEPT OF A REMOVED CHECKOUT. Of the copies no commit holds, a copy whose version is in
the path's approved set, the blob ids its `approved` file lists, is deleted. When the path's
`log` names a version not in that set, or a copy's version is not in it, every copy of the
path that no commit holds is kept, the approved ones too, so the change can still be shown
against the approved version. `approved` and `log` are never deleted: they are small, and a
kept copy means nothing without them.

CONCURRENCY. The hook takes no lock on the store, and none is needed: the hook writes a copy only
of a version its checkout's HEAD does not hold, of a file that exists, in its own live checkout
or in ~/.claude, and this program deletes only copies a commit on a durable ref holds, which
loses nothing even when the hook has just written one, or copies under directories that are
gone, rechecked just before each path's copies go. Each unlink is atomic. A checkout re-created at the same path between that check and the unlinks loses
every approved copy of that path, and the hook's next run there copies only the version then on
disk.

SCHEDULE. Once a day at 07:00, after the daily worktree cleanup at 06:30, on each machine.
Installed by nc-systems/general-tools/install-scheduled-jobs-on-this-machine.py from the table
beside it, scheduled-jobs-on-each-machine.json, where a change to the schedule is made.

  ned-box: one cron line.

    0 7 * * * /usr/bin/python3 /home/nedlern/Projects/nedschorus/nc-systems/general-tools/guarded-file-versions-and-approvals-store-removed-checkout-copies-prune.py >> /home/nedlern/.claude/daily-guarded-file-versions-and-approvals-store-removed-checkout-copies-prune.log 2>&1

  the Mac: a launchd job at the same time; a run missed while the Mac sleeps starts at the next
  wake.

Exit status: 0 when done; 1 when the store cannot be reached, a directory cannot be read, it
cannot be told whether a directory exists, git cannot say whether a directory is ignored or
which blobs its commits hold, a copy
cannot be deleted, or the run is stopped part way; the lines on stderr say what failed. A failure
in one path keeps that path's copies and the run goes on to the others.
"""

import argparse
import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path

HOOK_PATH = (Path(__file__).resolve().parents[2] / ".claude" / "hooks"
             / "guarded-file-unapproved-change-afterward-backup-and-ask-hook.py")
_specification = importlib.util.spec_from_file_location(
    "guarded_file_unapproved_change_afterward_backup_and_ask_hook", HOOK_PATH)
hook = importlib.util.module_from_spec(_specification)
_specification.loader.exec_module(hook)

# A copy is named by its git blob id, which is SHA-1 in this project's repositories.
COPY_NAME = re.compile(r"[0-9a-f]{40}")
# On the Mac the store is ned-box's disk over SMB; a mount that hangs must not hang the job.
# The hook's deadline variable overrides it, so a test can stop a run part way.
MAC_DEADLINE_SECONDS = 600

EXIT_DONE = 0
EXIT_FAILED = 1


def is_missing(path: Path):
    """True when path does not exist. Any failure but "no such file" or "not a directory" is
    raised, since a directory that cannot be searched still exists. A volume not mounted looks
    missing here; removed_checkout keeps its paths."""
    try:
        os.lstat(path)
    except (FileNotFoundError, NotADirectoryError):
        return True
    return False


MOUNT_PARENTS = (Path("/Volumes"), Path("/mnt"), Path("/media"))


def unmounted_volume_root(path: str, mount_parents):
    """The directory <mount parent>/<name> that holds path when it is missing or empty, so the
    volume may not be mounted; else None."""
    for parent in mount_parents:
        try:
            root = parent / Path(path).relative_to(parent).parts[0]
        except (ValueError, IndexError):
            continue
        if is_missing(root) or not any(root.iterdir()):
            return root
    return None


def removed_checkout(path: str, check_ignore, mount_parents=MOUNT_PARENTS):
    """The first missing directory on the path of a file, when that directory stands for a
    checkout that no longer exists; else None. check_ignore(root, relative) is True when git in
    root ignores the directory relative/."""
    parent = Path(path).parent
    if not is_missing(parent):
        return None
    missing = parent
    while is_missing(missing.parent):
        missing = missing.parent
    existing = missing.parent
    volume = unmounted_volume_root(path, mount_parents)
    if volume is not None:
        raise RuntimeError(f"{volume} is missing or empty, so its volume may not be mounted")
    root = hook.guard().enclosing_repository_root(existing)
    if root is None:
        return str(missing)
    relative = os.path.relpath(missing, root)
    return str(missing) if check_ignore(root, relative) else None


def git_ignores_directory(root: Path, relative: str):
    result = subprocess.run(["git", "-C", str(root), "check-ignore", "-q", "--", relative + "/"],
                            capture_output=True, text=True, timeout=60, check=False)
    if result.returncode in (0, 1):
        return result.returncode == 0
    raise RuntimeError(f"git check-ignore of {relative}/ in {root} exited {result.returncode}: "
                       f"{result.stderr.strip()}")


class BlobsCommitsHold:
    """The blob ids the commits of each repository's durable refs hold, listed once per
    repository, which all its worktrees share."""

    def __init__(self):
        self.common_directories, self.listed = {}, {}

    def of(self, path: str):
        root = hook.guard().enclosing_repository_root(Path(path).parent)
        if root is None:
            return set()
        if root not in self.common_directories:
            self.common_directories[root] = hook.git_text(
                root, "rev-parse", "--path-format=absolute", "--git-common-dir").strip()
        common = self.common_directories[root]
        if common not in self.listed:
            self.listed[common] = hook.blobs_durable_refs_hold(root)
        return self.listed[common]


def copies_to_delete(path_directory: Path, names):
    """(the copies in one path's directory that may be deleted, the number kept of versions not
    approved, the number of approved copies kept beside them)."""
    copies = sorted(name for name in names if COPY_NAME.fullmatch(name))
    approved = set(hook.valid_line_bodies((path_directory / hook.APPROVED_FILE_NAME).read_bytes()
                                          if hook.APPROVED_FILE_NAME in names else b""))
    log = [body.split("\t") for body in hook.valid_line_bodies(
        (path_directory / hook.LOG_FILE_NAME).read_bytes() if hook.LOG_FILE_NAME in names else b"")]
    never_approved = any(fields[4] not in approved
                         for fields in log if fields[0] == "seen" and len(fields) >= 7)
    not_approved = sum(1 for name in copies if name not in approved)
    if never_approved or not_approved:
        return [], not_approved, len(copies) - not_approved
    return copies, 0, 0


def prune(store_directory: Path, dry_run: bool, check_ignore=git_ignores_directory,
          mount_parents=MOUNT_PARENTS):
    """Walk the store and delete what may go. Returns a dict and raises for no failure inside
    the store, so the result can cross the Mac's deadline child: a path that fails is listed in
    "failures", its copies are kept, and the walk goes on. A real run prints each copy's path
    before deleting it, so a run killed part way has named every copy it may have deleted."""
    result = {"checkouts": {}, "bytes": 0, "kept_not_approved": 0, "kept_approved": 0,
              "failures": [], "held_by_commits": 0, "held_by_commits_bytes": 0}
    outside_files = set(hook.outside_files())
    held_by_commits = BlobsCommitsHold()

    def delete(copy):
        """The copy's size once deleted, or None when it failed."""
        try:
            size = copy.stat().st_size
            if not dry_run:
                print(f"deleting {copy}", flush=True)
                copy.unlink()
        except OSError as error:
            result["failures"].append(f"{copy} could not be deleted: {error.strerror}")
            return None
        return size

    def walk_failed(error):
        result["failures"].append(f"{error.filename} could not be read: {error.strerror}")

    for directory, subdirectories, names in os.walk(store_directory, onerror=walk_failed):
        subdirectories.sort()
        if not any(COPY_NAME.fullmatch(name) for name in names):
            continue
        path_directory = Path(directory)
        path = "/" + str(path_directory.relative_to(store_directory))
        if path in outside_files:
            continue
        try:
            held = held_by_commits.of(path)
        except (RuntimeError, subprocess.SubprocessError) as error:
            result["failures"].append(f"{path}'s copies were kept: {error}")
            continue
        for name in sorted(name for name in names if name in held):
            size = delete(path_directory / name)
            if size is not None:
                result["held_by_commits"] += 1
                result["held_by_commits_bytes"] += size
        names = [name for name in names if name not in held]
        if not any(COPY_NAME.fullmatch(name) for name in names):
            continue
        try:
            checkout = removed_checkout(path, check_ignore, mount_parents)
        except OSError as error:
            result["failures"].append(f"{path}'s copies were kept: whether {error.filename} "
                                      f"exists could not be told: {error.strerror}")
            continue
        except (RuntimeError, subprocess.SubprocessError) as error:
            result["failures"].append(f"{path}'s copies were kept: {error}")
            continue
        if checkout is None:
            continue
        try:
            deletable, kept_not_approved, kept_approved = copies_to_delete(path_directory, names)
        except OSError as error:
            result["failures"].append(f"{path}'s copies were kept: {error.filename} could not "
                                      f"be read: {error.strerror}")
            continue
        result["kept_not_approved"] += kept_not_approved
        result["kept_approved"] += kept_approved
        if not deletable:
            continue
        if not dry_run:
            try:
                if not is_missing(Path(checkout)):
                    continue
            except OSError as error:
                result["failures"].append(f"{path}'s copies were kept: whether {checkout} "
                                          f"exists could not be told: {error.strerror}")
                continue
        deleted, deleted_bytes = 0, 0
        for name in deletable:
            size = delete(path_directory / name)
            if size is None:
                continue
            deleted += 1
            deleted_bytes += size
        result["bytes"] += deleted_bytes
        if deleted:
            result["checkouts"][checkout] = result["checkouts"].get(checkout, 0) + deleted_bytes
    return result


def run(dry_run: bool):
    machine = hook.this_machine()

    def work(store):
        os.close(store.fd)
        return prune(store.directory, dry_run)

    if machine == "mac":
        deadline = float(os.environ.get(hook.DEADLINE_VARIABLE) or MAC_DEADLINE_SECONDS)
        return hook.run_with_deadline(lambda: work(hook.Store(machine)), deadline)
    return work(hook.Store(machine))


def main(arguments=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dry-run", action="store_true",
                        help="list what would be deleted, and delete nothing")
    options = parser.parse_args(arguments)
    try:
        result = run(options.dry_run)
    except (hook.StoreUnreachable, OSError, RuntimeError, subprocess.SubprocessError) as error:
        sys.stdout.flush()
        print(f"{Path(__file__).name}: the prune of the store "
              f"{hook.store_directory(hook.this_machine())} stopped: {error}. Every copy it "
              f"may have deleted is named above on a line that starts with 'deleting', printed "
              f"before the copy was deleted; with no such line, it deleted nothing.", file=sys.stderr)
        return EXIT_FAILED
    verb = "would delete" if options.dry_run else "deleted"
    for checkout, size in sorted(result["checkouts"].items()):
        print(f"removed checkout {checkout}: {verb} {size} bytes of approved copies")
    sys.stdout.flush()
    for failure in result["failures"]:
        print(failure, file=sys.stderr)
    print(f"{verb} {result['held_by_commits']} copies of versions a commit on a durable ref "
          f"holds ({result['held_by_commits_bytes']} bytes), and approved copies in "
          f"{len(result['checkouts'])} removed checkouts ({result['bytes']} bytes); kept, in "
          f"removed checkouts whose files have a version not approved, "
          f"{result['kept_not_approved']} copies of such versions and {result['kept_approved']} "
          f"approved copies; {len(result['failures'])} failures, each named on stderr above")
    return EXIT_FAILED if result["failures"] else EXIT_DONE


if __name__ == "__main__":
    sys.exit(main())
