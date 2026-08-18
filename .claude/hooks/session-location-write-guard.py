#!/usr/bin/env python3
"""Block file writes from a session seated in the wrong place
(user-walked 2026-08-17, git-infra rules walk).

Wired as a PreToolUse hook on Edit, Write, and NotebookEdit, third alongside
instruction-file-guard.py and backup-and-snapshot-write-guard.py. Two session
states make a file write into the checkout a mistake regardless of the file:

* **Detached HEAD** — the checkout is parked on a raw commit, on no branch.
  A commit made here is mechanically fine and practically lost: no branch
  name points at it, nothing will push it, and the work evaporates with the
  worktree. The session is told to get onto a branch first.

* **The reference checkout** — the machine's primary working copy, the main
  worktree of the repository, which every other agent reads as "what main
  looks like". Working in it corrupts the readers, not just the bench:
  observed 2026-08-14, twelve documents edited and 235 deletions staged
  there by a session seated elsewhere's task. Recognized structurally: in
  the main worktree, and only there, `git rev-parse --absolute-git-dir`
  equals `--git-common-dir`.

Scope: only writes whose target lies inside the session's own checkout are
blocked. The scratchpad, /tmp, and anything outside the repository stay
writable from any state — the hazard is work landing in the tree, not the
session having a tree. Cross-checkout writes (a session in one checkout
writing into another) are a separate rule with its own machinery; this guard
judges only where the session itself sits.

The exception lane, designed in from the start: the merge lane legitimately
edits files in the reference checkout while resolving merge conflicts. The
user's approval for that specific work, quoted into .location-write-approved
at the root of the session's checkout, passes exactly one write per marker —
the same consumed-marker contract as the sibling guards, with its own marker
file so an instruction-file approval and a location approval can never
consume each other.

Like its siblings, this is a tool-call block and cannot see a write made
through a shell command; the rule binds either way. Session location is
resolved from the hook payload's cwd, never from $CLAUDE_PROJECT_DIR, which
lies in forked sessions (rider 6; fixed for all guards 2026-08-17).
"""

import json
import os
import subprocess
import sys
from pathlib import Path

APPROVAL_MARKER_NAME = ".location-write-approved"

DETACHED_DENY_MESSAGE = (
    "Refusing to write {path}: this session's checkout is on a detached HEAD — no branch "
    "points at its commits, so anything committed here is unreachable by name and will be "
    "lost with the worktree. Get onto a branch first (git switch -c <a-branch-name>), or "
    "move to your own seat worktree, then resubmit. If the user has approved writing from "
    "this exact state, quote his approval words into {marker} at the checkout root and "
    "resubmit — the marker is consumed by the one call it approves."
)

REFERENCE_DENY_MESSAGE = (
    "Refusing to write {path}: this session sits in the machine's reference checkout — the "
    "main worktree other agents read as the truth about main. Work belongs in your own "
    "worktree; use it and leave this copy as reference. If this write IS legitimate work "
    "in this checkout — the merge lane resolving conflicts, with the user's approval — "
    "quote his approval words into {marker} at the checkout root and resubmit; the marker "
    "is consumed by the one call it approves."
)


def run_git(arguments, working_directory: Path):
    try:
        return subprocess.run(
            ["git", *arguments], cwd=str(working_directory),
            capture_output=True, text=True, check=False, timeout=15,
        )
    except (OSError, subprocess.SubprocessError) as error:
        return subprocess.CompletedProcess(arguments, 1, "", f"{type(error).__name__}: {error}")


def checkout_root_of(directory: Path):
    result = run_git(["rev-parse", "--show-toplevel"], directory)
    if result.returncode != 0:
        return None
    return Path(result.stdout.strip())


def is_detached(checkout: Path) -> bool:
    branch = run_git(["rev-parse", "--abbrev-ref", "HEAD"], checkout).stdout.strip()
    return branch in ("", "HEAD")


def is_reference_checkout(checkout: Path) -> bool:
    """True only in the repository's main worktree — the machine's reference copy.

    git prints --git-common-dir RELATIVE to the checkout when asked from the
    main worktree (a bare `.git`), so both paths are joined against the
    checkout before comparing — resolving against this process's own cwd
    would be the wrong-base class of bug this project keeps finding.
    """
    git_dir = run_git(["rev-parse", "--absolute-git-dir"], checkout).stdout.strip()
    common_dir = run_git(["rev-parse", "--git-common-dir"], checkout).stdout.strip()
    if not git_dir or not common_dir:
        return False
    try:
        common = Path(common_dir)
        if not common.is_absolute():
            common = checkout / common
        return Path(git_dir).resolve() == common.resolve()
    except OSError:
        return False


def target_inside(checkout: Path, file_path: str) -> bool:
    try:
        Path(file_path).resolve().relative_to(checkout.resolve())
        return True
    except (ValueError, OSError):
        return False


def consume_approval_marker(marker_path: Path) -> bool:
    """One approved write passes; the marker is spent by the call it approves."""
    try:
        content = marker_path.read_text(encoding="utf-8").strip()
    except (FileNotFoundError, OSError):
        return False
    if not content:
        return False
    marker_path.unlink(missing_ok=True)
    return True


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return 0
    tool_input = payload.get("tool_input") or {}
    # NotebookEdit carries notebook_path where the others carry file_path.
    file_path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
    if not file_path:
        return 0

    session_cwd = Path(payload.get("cwd") or os.getcwd())
    checkout = checkout_root_of(session_cwd)
    if checkout is None:
        return 0  # a session outside any checkout has no location to judge
    if not target_inside(checkout, file_path):
        return 0  # scratchpad, /tmp, other trees: not this guard's business

    if is_detached(checkout):
        deny_message = DETACHED_DENY_MESSAGE
    elif is_reference_checkout(checkout):
        deny_message = REFERENCE_DENY_MESSAGE
    else:
        return 0

    if consume_approval_marker(checkout / APPROVAL_MARKER_NAME):
        return 0
    print(deny_message.format(path=file_path, marker=APPROVAL_MARKER_NAME), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
