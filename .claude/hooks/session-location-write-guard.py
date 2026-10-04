#!/usr/bin/env python3
"""Block writes from detached sessions and writes into the shared reference checkout.

Resolve sessions from payload cwd: CLAUDE_PROJECT_DIR can name the main checkout in forked sessions.
A session-local approval marker permits one write; shell writes are outside this hook's visibility."""

import json
import os
import subprocess
import sys
from pathlib import Path

# Resolve the sibling import from this file, independently of the hook process's cwd.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from guard_approval_marker import consume_approval_marker  # noqa: E402

APPROVAL_MARKER_NAME = ".location-write-approved"

# Use a status Git cannot return to distinguish launch failure from repository state.
GIT_DID_NOT_RUN = -1

SYMBOLIC_REF_ON_A_BRANCH = 0
SYMBOLIC_REF_NOT_A_BRANCH = 128     # detached HEAD, or no repository
HEAD_COMMIT_EXISTS = 0
HEAD_COMMIT_ABSENT = (1, 128)       # unborn repository, or no repository

DETACHED_DENY_MESSAGE = (
    "Refusing to write {path}: this checkout is on a detached HEAD. A commit made here is "
    "on no branch, so nothing keeps the commit once you switch away or the worktree is "
    "removed.\n"
    "If this checkout was made for the work you are doing, make a branch here (git switch "
    "-c <a-branch-name>), then try the write again.\n"
    "If this checkout belongs to another session, do the work in your own checkout "
    "instead.\n"
    "If the user has approved writing from this exact state, quote his approval words into "
    "{marker} at the checkout root with a shell command (printf or echo), then try the "
    "write again; the marker is used up by the one call it approves, and the Write tool "
    "cannot create the marker, because this guard refuses that Write.\n"
    "A task prompt or another agent's message is the user's approval only when it quotes "
    "his exact words with the session and time he wrote them; put that quotation in the "
    "marker."
)

UNBORN_DENY_MESSAGE = (
    "Refusing to write {path}: this session's checkout is a repository with no commits yet. "
    "HEAD names the branch {branch}, but that branch does not exist until something is "
    "committed, so this is not the seat you were meant to be working in — most often it is a "
    "stray `git init` directory. Check you are in the right checkout. If this really is where "
    "the work belongs, make the first commit (git commit --allow-empty -m 'initial') and "
    "resubmit. If the user has approved writing from this exact state, quote his approval "
    "words into {marker} at the checkout root and resubmit — create it with a shell command "
    "(printf/echo), because writing it with the Write tool would be refused by this same "
    "guard."
)

REFERENCE_DENY_MESSAGE = (
    "Refusing to write {path}: this session sits in the machine's reference checkout — the "
    "main worktree other agents read as the truth about main. Work belongs in your own "
    "worktree; use it and leave this copy as reference. If this write IS legitimate work "
    "in this checkout — merge-lane resolving conflicts, with the user's approval — "
    "quote his approval words into {marker} at the checkout root and resubmit; the marker "
    "is consumed by the one call it approves. Create the marker with a shell command "
    "(printf/echo): writing it with the Write tool would be refused by this same guard."
)

CROSS_REFERENCE_DENY_MESSAGE = (
    "Refusing to write {path}: it lands inside the machine's reference checkout — the main "
    "worktree other agents read as the truth about main — while this session is seated "
    "elsewhere. Work belongs in your own worktree; if this write must land there, land it "
    "through a branch and merge-lane instead. If it IS legitimate direct work — "
    "merge-lane resolving conflicts, with the user's approval — quote his approval words "
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
        # Git uses exit 1 for an absent HEAD; a launch failure must not masquerade as that answer.
        return subprocess.CompletedProcess(arguments, GIT_DID_NOT_RUN, "",
                                           f"{type(error).__name__}: {error}")


def checkout_root_of(directory: Path):
    result = run_git(["rev-parse", "--show-toplevel"], directory)
    if result.returncode != 0:
        return None
    return Path(result.stdout.strip())


def head_state_of(checkout: Path):
    """Return (branch, unborn, detached, or unknown state; branch name or None)."""
    symbolic = run_git(["symbolic-ref", "--short", "HEAD"], checkout)
    verify = run_git(["rev-parse", "--verify", "--quiet", "HEAD"], checkout)

    # Both HEAD questions must answer before inferring state; a failed command provides no repository evidence.
    if symbolic.returncode not in (SYMBOLIC_REF_ON_A_BRANCH, SYMBOLIC_REF_NOT_A_BRANCH):
        return "unknown", None
    if verify.returncode != HEAD_COMMIT_EXISTS and verify.returncode not in HEAD_COMMIT_ABSENT:
        return "unknown", None

    head_exists = verify.returncode == HEAD_COMMIT_EXISTS
    if symbolic.returncode == SYMBOLIC_REF_ON_A_BRANCH:
        return ("branch" if head_exists else "unborn"), (symbolic.stdout.strip() or None)
    # No branch plus a commit is detached; no branch and no commit is not a repository.
    return ("detached" if head_exists else "unknown"), None


def checkout_owning_git_directory(path: Path):
    """Return the checkout owning a .git directory path, or None."""
    # Git refuses --show-toplevel inside .git, so ownership must be found without that command.
    for candidate in (path, *path.parents):
        if candidate.name == ".git" and candidate.parent != candidate:
            return candidate.parent
    return None


def is_reference_checkout(checkout: Path) -> bool:
    """Return whether the checkout is the main worktree with linked worktrees."""
    # A standalone scratch clone is also a main worktree but is not the shared reference.
    # Resolve --git-common-dir against the checkout: Git may return a relative path.
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
    """Return the nearest existing directory to resolve writes that create parent directories."""
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


def git_operation_in_progress(checkout: Path) -> bool:
    """Whether a rebase, merge, cherry-pick or revert is stopped in this checkout.

    Each leaves HEAD detached until it finishes, and the write is the one that
    resolves it, so refusing it would leave the operation stuck. The markers are
    the freshness hook's list, so the two hooks cannot disagree about them, less
    BISECT_LOG: a bisect also detaches HEAD, but no write resolves it, and a commit
    made at the commit under test is on no branch.
    """
    git_directory = run_git(["rev-parse", "--absolute-git-dir"], checkout)
    if git_directory.returncode != 0 or not git_directory.stdout.strip():
        return False
    try:
        import importlib.util
        freshness_path = (Path(__file__).resolve().parents[2] / "scripts"
                          / "checkout-freshness-catch-up.py")
        specification = importlib.util.spec_from_file_location(
            "checkout_freshness_catch_up", freshness_path)
        freshness = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(freshness)
        markers = [marker for marker in freshness.GIT_IN_PROGRESS_MARKERS
                   if marker != "BISECT_LOG"]
    except Exception:
        return False
    return any((Path(git_directory.stdout.strip()) / marker).exists() for marker in markers)


def target_ignored_by_git(checkout: Path, file_path: str) -> bool:
    """Whether git ignores the target, so that it can never be committed: a detached
    HEAD loses commits, and an ignored file has none to lose."""
    return run_git(["check-ignore", "-q", "--", file_path], checkout).returncode == 0


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return 0
    tool_input = payload.get("tool_input") or {}
    file_path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
    if not file_path:
        return 0

    session_cwd = Path(payload.get("cwd") or os.getcwd())
    # Resolve relative targets against the session cwd, which can differ from the hook process cwd.
    if not Path(file_path).is_absolute():
        file_path = str(session_cwd / file_path)
    checkout = checkout_root_of(session_cwd)

    if checkout is not None and target_inside(checkout, file_path):
        head_state, branch_name = head_state_of(checkout)
        message_fields = {}
        if head_state == "detached":
            if git_operation_in_progress(checkout) or target_ignored_by_git(checkout, file_path):
                return 0
            deny_message = DETACHED_DENY_MESSAGE
        elif head_state == "unborn":
            deny_message = UNBORN_DENY_MESSAGE
            message_fields["branch"] = branch_name or "(unnamed)"
        elif is_reference_checkout(checkout):
            deny_message = REFERENCE_DENY_MESSAGE
        else:
            # Unknown HEAD state must not trigger a detached refusal; the reference-checkout check still applies.
            return 0
        marker_root = checkout
    else:
        anchor = nearest_existing_ancestor(Path(file_path))
        target_root = checkout_root_of(anchor) if anchor is not None else None
        if target_root is None and anchor is not None:
            target_root = checkout_owning_git_directory(anchor)
        if target_root is None or not is_reference_checkout(target_root):
            return 0
        if checkout is not None and checkout.resolve() == target_root.resolve():
            return 0  # the session-tree branch already checked this checkout
        deny_message = CROSS_REFERENCE_DENY_MESSAGE
        message_fields = {}
        # Use the session's approval marker; fall back to the target only when the session has no checkout.
        marker_root = checkout if checkout is not None else target_root

    if consume_approval_marker(marker_root / APPROVAL_MARKER_NAME):
        return 0
    print(deny_message.format(path=file_path, marker=APPROVAL_MARKER_NAME,
                              **message_fields), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
