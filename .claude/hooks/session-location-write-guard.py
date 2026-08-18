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

Scope, two questions about one write. Where the session SITS: the two states
above block writes into the session's own tree; the scratchpad, /tmp, and
other trees stay writable from any state. And where the write LANDS
(user-walked 2026-08-17): a write whose target sits inside the reference
checkout while the session is seated elsewhere is refused — every recorded
cross-checkout incident (the twelve-document bench of 2026-08-14, the
misplaced review records, the misplaced walk ledger) targeted exactly that
copy. Deliberately narrow: writes into scratch worktrees, throwaway clones,
and other seats' trees are NOT blocked — the first two are ordinary work,
and the third has no recorded incident (recorded as unbuilt; an incident is
its build trigger).

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
    "is consumed by the one call it approves. Create the marker with a shell command "
    "(printf/echo): writing it with the Write tool would be refused by this same guard."
)

CROSS_REFERENCE_DENY_MESSAGE = (
    "Refusing to write {path}: it lands inside the machine's reference checkout — the main "
    "worktree other agents read as the truth about main — while this session is seated "
    "elsewhere. Work belongs in your own worktree; if this write must land there, land it "
    "through a branch and the merge lane instead. If it IS legitimate direct work — the "
    "merge lane resolving conflicts, with the user's approval — quote his approval words "
    "into {marker} at the root of your own checkout and resubmit; the marker is consumed "
    "by the one call it approves."
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
    """True only for the machine's reference copy: a main worktree that
    carries linked worktrees.

    Being the main worktree alone is not enough — a standalone scratch clone
    is technically its own main worktree, and treating it as "the reference"
    would block ordinary work in throwaway clones (verdict pinned 2026-08-17,
    resolving the #88 review's standalone-clone finding: a lone clone is its
    own workspace). The reference copy is the one other agents hang their
    seats off, and that is visible structurally: its .git/worktrees/ is
    non-empty.

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
        common = common.resolve()
        if Path(git_dir).resolve() != common:
            return False
        linked = common / "worktrees"
        return linked.is_dir() and any(linked.iterdir())
    except OSError:
        return False


def nearest_existing_ancestor(path: Path):
    """The first existing directory at or above the target, for judging a
    write that creates its own directories."""
    try:
        resolved = path.resolve()
    except (OSError, RuntimeError):
        return None
    for candidate in (resolved.parent, *resolved.parent.parents):
        if candidate.is_dir():
            return candidate
    return None


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

    if checkout is not None and target_inside(checkout, file_path):
        # The seated questions: writes into the session's own tree.
        if is_detached(checkout):
            deny_message = DETACHED_DENY_MESSAGE
        elif is_reference_checkout(checkout):
            deny_message = REFERENCE_DENY_MESSAGE
        else:
            return 0
        marker_root = checkout
    else:
        # The landing question: does this write cross into the reference?
        anchor = nearest_existing_ancestor(Path(file_path))
        target_root = checkout_root_of(anchor) if anchor is not None else None
        if target_root is None or not is_reference_checkout(target_root):
            return 0
        if checkout is not None and checkout.resolve() == target_root.resolve():
            return 0  # same tree; the seated branch above already judged it
        deny_message = CROSS_REFERENCE_DENY_MESSAGE
        # The marker belongs in the tree the SESSION owns; only a session
        # with no checkout at all falls back to the target's root.
        marker_root = checkout if checkout is not None else target_root

    if consume_approval_marker(marker_root / APPROVAL_MARKER_NAME):
        return 0
    print(deny_message.format(path=file_path, marker=APPROVAL_MARKER_NAME), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
