#!/usr/bin/env python3
"""Save the uncommitted work in scratch worktrees before a machine restarts.

A restart empties /tmp (on the Mac, /private/tmp). Commits on a branch survive
in the clone, but a worktree under /tmp loses its uncommitted edits and its
untracked files. For each worktree of the clone that lies under /tmp or
/private/tmp and has uncommitted changes, this program saves `git diff HEAD`
and a tar of the untracked files (files git ignores are not saved), writes a
manifest, copies them to the log-store on ned-box in one subdirectory per
worktree under seats/<seat>/pre-reboot-<UTC date>/, verifies the copy by
checksum, and prints what it saved. The agent-seat is read from the scratchpad path
(`-Users-<user>-agents-<seat>` on the Mac, `-home-<user>-agents-<seat>` on
ned-box); a worktree whose path names no agent-seat is saved under
`unknown-seat`. On ned-box itself the copy is a local one.

It removes nothing, so running it twice is safe: a second run on the same day
saves into pre-reboot-<UTC date>-2, then -3, up to -10, and never overwrites
an earlier save; an eleventh run on one day fails. Any worktree it could not
save, or a copy it could not verify, makes it exit 1 after it has tried every
worktree; read each FAILED line. When ned-box cannot be reached, every save
from the Mac fails this way.

THE RESTART PROCEDURE, for any agent preparing a restart of the Mac or
ned-box:

1. Check that no agent-seat is busy. Use your ListAgents tool and look for
   busy sessions. Check ~/.claude/.run-all-test-suites.lock: if a process
   holds it (`fuser ~/.claude/.run-all-test-suites.lock` on ned-box,
   `lsof ~/.claude/.run-all-test-suites.lock` on the Mac), a test run is
   going. Run `pgrep -fl 'git push|codex exec'` for pushes and Codex runs in
   flight. Tell the user what you found. If anything is busy, wait for it to
   finish or let the user decide; do not stop another agent's work yourself.
   Wait for the user's go-ahead before going on.
2. Make sure no retired agent-seat will come back. A retired agent-seat
   whose ~/.claude/handoffs/<seat>-supervisor-state.json is still on this
   machine is brought back after the restart as an empty agent-seat.
   merge-lane is retired. For each retired agent-seat with no supervisor
   still running, move that file into ~/.claude/handoffs/retired/; if a
   file of that name is already there, add -2, -3 before .json rather than
   overwrite it. Do this before the restart, not after.
3. Run this program on the machine that will restart:
   `python3 scripts/save-uncommitted-scratch-worktrees-before-reboot.py`.
   If it exits 1, tell the user which worktrees were not saved, and why,
   before he restarts. If it exits 2, nothing was looked at: tell the user
   and do not go on.
4. The user restarts the machine. For the Mac: he installs the macOS
   update and relaunches iTerm2; Safari and Docker Desktop need his admin
   password.
5. After login, scripts/restart-live-seats-at-login.py runs by itself and
   brings back the agent-seats that were running: a LaunchAgent starts it
   on the Mac, a systemd unit on ned-box.

WHERE A SAVE IS, AND HOW TO BRING IT BACK. Each saved worktree gets its own
subdirectory, seats/<seat>/pre-reboot-<UTC date>/<NNN>-<worktree name>/,
holding untracked.tar, manifest.json and, when tracked files had changed,
changes.diff; the manifest names the worktree, its branch and its head
commit. To bring the work back, copy that subdirectory to the machine you
work on (`scp -r nedlern@ned-box:<its path> .` from the Mac), and make a
checkout at that head commit. If changes.diff is there, run
`git apply <path to>/changes.diff` in that checkout; when
only untracked files had changed there is no changes.diff, and the
manifest's diff_written is false. Then run `tar -xf <path to>/untracked.tar` in the
same checkout. The diff holds staged and unstaged changes together, so they
come back unstaged. An untracked git repository inside the worktree is in
the tar whole, its .git included, and the manifest lists it under
nested_repositories.

Exit codes: 0 every dirty worktree was saved and verified, or none was
dirty; 1 something was not saved or not verified; 2 bad invocation or the
clone could not be read.
"""

import argparse
import datetime
import hashlib
import json
import os
import re
import shlex
import socket
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

DEFAULT_CLONE = Path.home() / "Projects" / "nedschorus"
DEFAULT_DESTINATION = "nedlern@ned-box:/home/nedlern/nedschorus-logs/seats"
DEFAULT_SCRATCH_ROOTS = ("/tmp", "/private/tmp")
LOG_STORE_HOSTNAME = "ned-box"
UNKNOWN_SEAT = "unknown-seat"
SSH_OPTIONS = ["-o", "BatchMode=yes", "-o", "ConnectTimeout=10"]
# The six variables scripts/run-all-test-suites.py strips: each points git at
# another repository's files.
GIT_REDIRECTING_VARIABLES = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
                             "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_COMMON_DIR")
SEAT_COMPONENT = re.compile(r"^-(?:Users|home)-[^-]+-agents-(.+)$")
DIFF_NAME, TAR_NAME, MANIFEST_NAME = "changes.diff", "untracked.tar", "manifest.json"


class SaveFailed(Exception):
    pass


def git(arguments, cwd, binary=False):
    environment = {k: v for k, v in os.environ.items() if k not in GIT_REDIRECTING_VARIABLES}
    completed = subprocess.run(["git", *arguments], cwd=cwd, capture_output=True,
                               env=environment, check=False)
    if completed.returncode != 0:
        raise SaveFailed(f"git {' '.join(arguments)} in {cwd} exited {completed.returncode}: "
                         f"{completed.stderr.decode(errors='replace').strip()}")
    return completed.stdout if binary else completed.stdout.decode(errors="replace")


def registered_worktrees(clone):
    """Return one dict per worktree from `git worktree list --porcelain`."""
    worktrees, current = [], {}
    for line in git(["worktree", "list", "--porcelain"], clone).splitlines() + [""]:
        if not line:
            if current:
                worktrees.append(current)
            current = {}
            continue
        key, _, value = line.partition(" ")
        current[key] = value if value else True
    return worktrees


def under_scratch_root(path, scratch_roots):
    resolved = os.path.realpath(path)
    for root in scratch_roots:
        root = os.path.realpath(root)
        if resolved == root or resolved.startswith(root.rstrip("/") + "/"):
            return True
    return False


def seat_of(path):
    for component in PurePosixPath(path).parts:
        match = SEAT_COMPONENT.match(component)
        if match:
            return match.group(1)
    return UNKNOWN_SEAT


def sha256_of(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def save_worktree(worktree, staging):
    """Write the diff, the untracked tar and the manifest into staging; return the manifest."""
    path = worktree["worktree"]
    staging.mkdir(parents=True)
    status = git(["status", "--porcelain"], path)
    diff = git(["diff", "HEAD", "--binary", "--no-color"], path, binary=True)
    # git apply refuses an empty diff (exit 128), so an untracked-only save
    # writes none rather than one the restore step would trip on.
    if diff:
        (staging / DIFF_NAME).write_bytes(diff)
    untracked = [name for name in git(["ls-files", "--others", "--exclude-standard", "-z"],
                                      path).split("\0") if name]
    # git lists an untracked nested repository as one "name/" entry; it is
    # archived whole, its .git included, so its own uncommitted work survives.
    nested_repositories = [name.rstrip("/") for name in untracked if name.endswith("/")]
    with tarfile.open(staging / TAR_NAME, "w") as archive:
        for name in untracked:
            archive.add(os.path.join(path, name.rstrip("/")), arcname=name.rstrip("/"),
                        recursive=name.endswith("/"))
    written = [name for name in (DIFF_NAME, TAR_NAME) if (staging / name).exists()]
    saved = [{"name": name, "bytes": (staging / name).stat().st_size,
              "sha256": sha256_of(staging / name)} for name in written]
    manifest = {"worktree": path, "branch": worktree.get("branch", "(detached)"),
                "head": worktree.get("HEAD"), "seat": seat_of(path),
                "status": status.splitlines(), "untracked_files": untracked,
                "nested_repositories": nested_repositories,
                "diff_written": DIFF_NAME in written, "saved": saved}
    (staging / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def split_destination(destination):
    """Return (host, path); host is None for a local path."""
    head = destination.split("/", 1)[0]
    if ":" in head:
        host, _, rest = destination.partition(":")
        return host, rest
    return None, destination


def copy_host_and_store(destination, hostname):
    """Return (host, store path); host is None when the copy is local.

    The default destination is ned-box, so on ned-box itself it is a local
    copy rather than ssh to the same machine; any other destination is
    taken as given.
    """
    host, store = split_destination(destination)
    if destination == DEFAULT_DESTINATION and hostname.split(".")[0] == LOG_STORE_HOSTNAME:
        host = None
    return host, store


def run_checked(command, what):
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise SaveFailed(f"{what}: {shlex.join(command)} exited {completed.returncode}: "
                         f"{completed.stderr.strip()}")
    return completed.stdout


MAKE_UNIQUE_DIRECTORY = (
    'mkdir -p "$1" || exit 1; '
    'for suffix in "" -2 -3 -4 -5 -6 -7 -8 -9 -10; do '
    'if mkdir "$1/$2$suffix" 2>/dev/null; then echo "$1/$2$suffix"; exit 0; fi; done; '
    'echo "ten saves for $2 already exist under $1" >&2; exit 1')


def make_unique_directory(host, parent, name):
    """Create parent/name, or parent/name-2 and so on if it exists; return the one made."""
    command = ["sh", "-c", MAKE_UNIQUE_DIRECTORY, "sh", parent, name]
    if host:
        command = ["ssh", *SSH_OPTIONS, host, shlex.join(command)]
    return run_checked(command, f"could not create a save directory under {parent}").strip()


def copy_and_verify(host, directory, staged_files):
    """Copy the staged files into directory and compare checksums on the far side."""
    names = [file.name for file in staged_files]
    if host:
        run_checked(["scp", "-q", *SSH_OPTIONS, *map(str, staged_files), f"{host}:{directory}/"],
                    f"could not copy to {host}:{directory}")
        listing = run_checked(["ssh", *SSH_OPTIONS, host,
                               shlex.join(["sh", "-c", 'cd "$1" && shift && sha256sum "$@"',
                                           "sh", directory, *names])],
                              f"could not checksum the copy in {host}:{directory}")
        copied = {line.split()[1].lstrip("*"): line.split()[0]
                  for line in listing.splitlines() if line.strip()}
    else:
        copied = {}
        for file in staged_files:
            target = Path(directory) / file.name
            target.write_bytes(file.read_bytes())
            copied[file.name] = sha256_of(target)
    for file in staged_files:
        if copied.get(file.name) != sha256_of(file):
            raise SaveFailed(f"the copy of {file.name} in {directory} does not match its checksum")


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--clone", type=Path, default=DEFAULT_CLONE,
                        help=f"the clone whose worktrees are saved (default: {DEFAULT_CLONE})")
    parser.add_argument("--destination", default=DEFAULT_DESTINATION,
                        help="where seats/<seat>/ lives: host:path over ssh, or a local path "
                             f"(default: {DEFAULT_DESTINATION}, local on ned-box itself)")
    parser.add_argument("--scratch-root", action="append", dest="scratch_roots",
                        help="a directory a restart empties; give it once per root "
                             f"(default: {' and '.join(DEFAULT_SCRATCH_ROOTS)})")
    arguments = parser.parse_args()
    scratch_roots = arguments.scratch_roots or list(DEFAULT_SCRATCH_ROOTS)

    host, store = copy_host_and_store(arguments.destination, socket.gethostname())

    try:
        # Sorted, so a run's order does not depend on how git lists them.
        worktrees = sorted(registered_worktrees(arguments.clone),
                           key=lambda worktree: worktree["worktree"])
    except (SaveFailed, OSError) as error:
        print(f"FAILED: could not list the worktrees of {arguments.clone}: {error}")
        return 2

    date = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    failures, saved, clean, skipped = 0, 0, 0, 0
    seat_directories = {}
    with tempfile.TemporaryDirectory(prefix="pre-reboot-save-") as staging_root:
        for index, worktree in enumerate(worktrees):
            path = worktree["worktree"]
            if not under_scratch_root(path, scratch_roots):
                skipped += 1
                continue
            if not os.path.isdir(path):
                print(f"GONE     {path}: registered but its directory is missing; nothing to save")
                continue
            try:
                if not git(["status", "--porcelain"], path).strip():
                    clean += 1
                    print(f"CLEAN    {path}")
                    continue
                seat = seat_of(path)
                staging = Path(staging_root) / f"{index:03d}-{PurePosixPath(path).name}"
                manifest = save_worktree(worktree, staging)
                if seat not in seat_directories:
                    seat_directories[seat] = make_unique_directory(
                        host, f"{store.rstrip('/')}/{seat}", f"pre-reboot-{date}")
                directory = f"{seat_directories[seat]}/{staging.name}"
                run_checked(["ssh", *SSH_OPTIONS, host, shlex.join(["mkdir", directory])]
                            if host else ["mkdir", directory],
                            f"could not create {directory}")
                copy_and_verify(host, directory,
                                [staging / entry["name"] for entry in manifest["saved"]]
                                + [staging / MANIFEST_NAME])
                where = f"{host}:{directory}" if host else directory
                seat_note = " (no agent-seat in its path)" if seat == UNKNOWN_SEAT else ""
                print(f"SAVED    {path} -> {where}{seat_note}: "
                      f"{len(manifest['status'])} changed path(s), "
                      f"{len(manifest['untracked_files'])} untracked file(s), copy verified")
                saved += 1
            except (SaveFailed, OSError) as error:
                failures += 1
                print(f"FAILED   {path}: {error}")
    print(f"SUMMARY: {saved} saved, {clean} clean, {failures} failed; "
          f"{skipped} worktree(s) outside {', '.join(scratch_roots)} not looked at")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
