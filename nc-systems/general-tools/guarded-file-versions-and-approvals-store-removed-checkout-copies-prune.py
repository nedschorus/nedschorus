#!/usr/bin/env python3
"""Delete the copies the guarded-file hook keeps for checkouts that no longer exist, except the
versions the user never approved.

The hook, .claude/hooks/guarded-file-unapproved-change-afterward-backup-and-ask-hook.py, keeps
this machine's directory of the log-store kind guarded-file-versions-and-approvals/. For every
guarded file it has seen, the directory mirrors the file's absolute path and holds `approved`,
`log` and one copy per version, named by the version's hash. Every copy is kept forever, so each
new worktree adds about a megabyte that outlives the worktree. This program runs once a day on
each machine, for that machine's own directory, since only that machine can tell whether one
of its paths still exists.

    python3 <this file> [--dry-run]

A run prints a line for each path whose copies it deletes, as it deletes them, so the log
names every deletion even when the run is stopped part way; then a line for each checkout it
pruned, with its size, and a summary. --dry-run prints the checkouts whose copies would be
deleted, and deletes nothing.

WHEN A CHECKOUT NO LONGER EXISTS. The store records neither a file's checkout nor its git
directory, so the checkout is found from the path. A file whose directory still exists belongs
to a checkout that still exists, or to no checkout; its copies are kept, since --restore may
need them to put back a file deleted on a branch. Otherwise the first missing directory on the
file's path stands for its checkout, and that checkout no longer exists when either
- no checkout encloses the nearest directory that still exists, as for ~/agents/<seat>; or
- that enclosing checkout's git ignores the missing directory, as the main clone ignores
  .claude/worktrees/, so the missing directory was a checkout of its own.
A missing directory that git does not ignore was the enclosing checkout's own, deleted on a
branch, and its copies are kept. A directory counts as missing only when the system says it does
not exist; when it cannot tell, as for a directory this process may not search or a volume that is
not mounted, the path's copies are kept and the failure is reported. The hook's files outside any
checkout, ~/.claude/CLAUDE.md and ~/.claude/settings.json, are never pruned.

WHAT IS KEPT. A copy whose version is in the path's approved set is deleted. Every copy of a
path that has a version the user never approved, or a copy whose version the approved set does
not hold, is kept, the approved copies too, so the change can still be shown against the
approved version. `approved` and `log` are never deleted: they are small, and a kept copy
means nothing without them.

CONCURRENCY. The hook takes no lock on the store, and none is needed: the hook writes a copy only
of a file that exists, in its own live checkout or in ~/.claude, and this program deletes only
copies, only under directories that are gone, rechecked just before each path's copies go. Each
unlink is atomic. A checkout re-created at the same path between that check and the unlinks loses
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
cannot be told whether a directory exists, git cannot say whether a directory is ignored, a copy
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
    raised, since a directory that cannot be searched or a volume not mounted still exists."""
    try:
        os.lstat(path)
    except (FileNotFoundError, NotADirectoryError):
        return True
    return False


def removed_checkout(path: str, check_ignore):
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


def prune(store_directory: Path, dry_run: bool, check_ignore=git_ignores_directory):
    """Walk the store and delete what may go. Returns a dict and raises for no failure inside
    the store, so the result can cross the Mac's deadline child: a path that fails is listed in
    "failures", its copies are kept, and the walk goes on. A real run prints each path's
    deletion as it happens, so a run killed part way has already named what it deleted."""
    result = {"checkouts": {}, "bytes": 0, "kept_not_approved": 0, "kept_approved": 0,
              "failures": []}
    outside_files = set(hook.outside_files())

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
            checkout = removed_checkout(path, check_ignore)
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
            copy = path_directory / name
            try:
                size = copy.stat().st_size
                if not dry_run:
                    copy.unlink()
            except OSError as error:
                result["failures"].append(f"{copy} could not be deleted: {error.strerror}")
                continue
            deleted += 1
            deleted_bytes += size
        if deleted and not dry_run:
            print(f"deleted {deleted} copies of {path}, {deleted_bytes} bytes", flush=True)
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
              f"deleted before it stopped is named above on a line that starts with 'deleted'; "
              f"with no such line, it deleted nothing.", file=sys.stderr)
        return EXIT_FAILED
    verb = "would prune" if options.dry_run else "pruned"
    for checkout, size in sorted(result["checkouts"].items()):
        print(f"{verb} {checkout}: {size} bytes")
    sys.stdout.flush()
    for failure in result["failures"]:
        print(failure, file=sys.stderr)
    print(f"{verb} the copies of {len(result['checkouts'])} removed checkouts, "
          f"{result['bytes']} bytes; kept {result['kept_not_approved']} copies of versions not "
          f"approved and {result['kept_approved']} approved copies of the same files; "
          f"{len(result['failures'])} failures")
    return EXIT_FAILED if result["failures"] else EXIT_DONE


if __name__ == "__main__":
    sys.exit(main())
