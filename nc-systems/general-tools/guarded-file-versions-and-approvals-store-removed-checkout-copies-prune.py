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

--dry-run lists the checkouts whose copies would be deleted, with their sizes, and deletes
nothing.

WHEN A CHECKOUT NO LONGER EXISTS. The store records neither a file's checkout nor its git
directory, so the checkout is found from the path. A file whose directory still exists belongs
to a checkout that still exists, or to no checkout; its copies are kept, since --restore may
need them to put back a file deleted on a branch. Otherwise the first missing directory on the
file's path stands for its checkout, and that checkout no longer exists when either
- no checkout encloses the nearest directory that still exists, as for ~/agents/<seat>; or
- that enclosing checkout's git ignores the missing directory, as the main clone ignores
  .claude/worktrees/, so the missing directory was a checkout of its own.
A missing directory that git does not ignore was the enclosing checkout's own, deleted on a
branch, and its copies are kept.

WHAT IS KEPT. A copy whose version is in the path's approved set is deleted. Every copy of a
path that has a version the user never approved is kept, the approved copies too, so the change
can still be shown against the approved version; so is any copy that the approved set and the
log do not account for. `approved` and `log` are never deleted: they are small, and a kept copy
means nothing without them.

CONCURRENCY. The hook takes no lock on the store, and none is needed: the hook writes a copy only
of a file that exists, in its own live checkout or in ~/.claude, and this program deletes only
copies, only under directories that are gone, rechecked just before each path's copies go. Each
unlink is atomic. A checkout re-created at the same path between that check and the unlink loses
an approved copy, and the hook's next run there copies the file again.

SCHEDULE. Once a day at 07:00, after the daily worktree cleanup at 06:30, on each machine.
Installed by nc-systems/general-tools/install-scheduled-jobs-on-this-machine.py from the table
beside it, scheduled-jobs-on-each-machine.json, where a change to the schedule is made.

  ned-box: one cron line.

    0 7 * * * /usr/bin/python3 /home/nedlern/Projects/nedschorus/nc-systems/general-tools/guarded-file-versions-and-approvals-store-removed-checkout-copies-prune.py >> /home/nedlern/.claude/daily-guarded-file-versions-and-approvals-store-removed-checkout-copies-prune.log 2>&1

  the Mac: a launchd job at the same time; a run missed while the Mac sleeps starts at the next
  wake.

Exit status: 0 when done; 1 when the store cannot be reached or read, git cannot say whether a
directory is ignored, or a copy cannot be deleted; the lines on stderr say what failed.
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
MAC_DEADLINE_SECONDS = 600

EXIT_DONE = 0
EXIT_FAILED = 1


def removed_checkout(path: str, check_ignore):
    """The first missing directory on the path of a file, when that directory stands for a
    checkout that no longer exists; else None. check_ignore(root, relative) is True when git in
    root ignores the directory relative/."""
    parent = Path(path).parent
    if parent.exists():
        return None
    missing = parent
    while not missing.parent.exists():
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
    """The copies in one path's directory that may be deleted, and the number kept because the
    path has a version the user never approved."""
    copies = sorted(name for name in names if COPY_NAME.fullmatch(name))
    approved = set(hook.valid_line_bodies((path_directory / hook.APPROVED_FILE_NAME).read_bytes()
                                          if hook.APPROVED_FILE_NAME in names else b""))
    log = [body.split("\t") for body in hook.valid_line_bodies(
        (path_directory / hook.LOG_FILE_NAME).read_bytes() if hook.LOG_FILE_NAME in names else b"")]
    seen = [fields for fields in log if fields[0] == "seen" and len(fields) >= 7]
    # For ~/.claude/settings.json the approved key and the copy's name differ; the log pairs them.
    approved_copies = approved | {fields[5] for fields in seen if fields[4] in approved}
    never_approved = any(fields[4] not in approved for fields in seen)
    if never_approved or any(name not in approved_copies for name in copies):
        return [], len(copies)
    return copies, 0


def prune(store_directory: Path, dry_run: bool, check_ignore=git_ignores_directory):
    """Walk the store and delete what may go. Returns a dict, never raises for a failed delete,
    so the result can cross the Mac's deadline child: deleting goes on past a failure, and every
    failure is listed."""
    result = {"checkouts": {}, "bytes": 0, "kept": 0, "failures": []}

    def walk_failed(error):
        raise hook.StoreUnreachable(f"{error.filename} could not be read: {error.strerror}")

    for directory, _, names in os.walk(store_directory, onerror=walk_failed):
        if not any(COPY_NAME.fullmatch(name) for name in names):
            continue
        path_directory = Path(directory)
        path = "/" + str(path_directory.relative_to(store_directory))
        checkout = removed_checkout(path, check_ignore)
        if checkout is None:
            continue
        try:
            deletable, kept = copies_to_delete(path_directory, names)
        except OSError as error:
            raise hook.StoreUnreachable(f"{error.filename} could not be read: {error.strerror}")
        result["kept"] += kept
        if not deletable:
            continue
        if not dry_run and os.path.lexists(checkout):
            continue
        for name in deletable:
            copy = path_directory / name
            try:
                size = copy.stat().st_size
                if not dry_run:
                    copy.unlink()
            except OSError as error:
                result["failures"].append(f"{copy} could not be deleted: {error.strerror}")
                continue
            result["bytes"] += size
            result["checkouts"][checkout] = result["checkouts"].get(checkout, 0) + size
    return result


def run(dry_run: bool):
    machine = hook.this_machine()

    def work(store):
        os.close(store.fd)
        return prune(store.directory, dry_run)

    if machine == "mac":
        return hook.run_with_deadline(lambda: work(hook.Store(machine)), MAC_DEADLINE_SECONDS)
    return work(hook.Store(machine))


def main(arguments=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dry-run", action="store_true",
                        help="list what would be deleted, and delete nothing")
    options = parser.parse_args(arguments)
    try:
        result = run(options.dry_run)
    except (hook.StoreUnreachable, OSError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"{Path(__file__).name}: the store {hook.store_directory(hook.this_machine())} was "
              f"not pruned: {error}", file=sys.stderr)
        return EXIT_FAILED
    if options.dry_run:
        for checkout, size in sorted(result["checkouts"].items()):
            print(f"would prune {checkout}: {size} bytes")
    for failure in result["failures"]:
        print(failure, file=sys.stderr)
    verb = "would prune" if options.dry_run else "pruned"
    print(f"{verb} the copies of {len(result['checkouts'])} removed checkouts, "
          f"{result['bytes']} bytes; kept {result['kept']} copies of versions not approved; "
          f"{len(result['failures'])} deletes failed")
    return EXIT_FAILED if result["failures"] else EXIT_DONE


if __name__ == "__main__":
    sys.exit(main())
