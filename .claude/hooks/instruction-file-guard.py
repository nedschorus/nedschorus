#!/usr/bin/env python3
"""Soft block on modifying instruction files (user-walked 2026-08-07, nedschorus#45).

Wired as a PreToolUse hook on Edit, Write, and NotebookEdit. Instruction
files — CLAUDE.md, per-agent CLAUDE.local.md identity files, and everything
under .claude/ — change only through the user's walk. Agents predictably try
to improve them (observed repeatedly in the legacy fleet); a path-scoped rule
cannot stop that (rules are context, not enforcement, and file creation
never triggers them — probed 2026-08-07), so the block lives at the tool
call, where it also catches creation.

Soft block, not a wall: the deny message teaches the sanctioned path and
names the override. An edit the user has already approved passes once by
writing the user's exact approval words into .walk-approved at the root of
the session's own checkout; the marker is consumed by the passing call. The
override is deliberately self-serve — the audit value is the visible, quoted
approval in the marker and the transcript, not tamper-proofing.

Root resolution (reworked 2026-08-17; rider 6 of
docs/issues/queue/45-session-seat-and-isolation-riders.md, user-walked in the
git-infra rules walk): the marker is looked for at the root of the SESSION'S
OWN checkout — the enclosing repository of the hook payload's cwd — never via
$CLAUDE_PROJECT_DIR. That variable lies in forked sessions: it names the main
checkout while settings load from the worktree, and a stale marker sitting in
the main checkout was observed silently authorizing a guarded write in an
unrelated session (2026-08-14). Resolving from the session's own checkout
makes a cross-checkout marker inert in every case and keeps approved markers
in the tree the agent owns, instead of littering the reference checkout (the
class rejected at PRs #57/#58). A session seated in no checkout at all falls
back to the target file's own repository root.

.claude/ is in the protected set as self-protection: this hook's own wiring
lives in .claude/settings.json, and an unguarded settings file is a guard an
agent can delete.

The harness's auto-memory under ~/.claude/projects/ is deliberately inside the
protected set (user-ruled 2026-08-11): every memory entry is user-reviewed.
Other harness state (transcripts, handoffs) carries no review requirement — a
carve-out is added when a real write trips this guard, not in advance. Three
exist, each added that way: `.claude/worktrees/` (an agent's isolated
checkout), `.claude/jobs/` (a background job's scratch directory, which the
harness hands out for temporary files and deletes with the job), and
`.claude/handoffs/` (a seat's handoff material). The handoffs carve-out was
user-ruled 2026-08-31 after the handoff skill began prescribing
`~/.claude/handoffs/<seat>-next-step-<stamp>.md` for the retiring agent's own
draft and this guard refused the Write. Note what tripped it: an agent's Write,
prescribed by a committed skill, rather than a write by the harness itself.
That is a shade narrower than the sentence above, and is recorded rather than
smoothed over.

Transcripts stay protected, and that is collateral rather than intent: the
`.jsonl` files sit under ~/.claude/projects/ beside the auto-memory, so no
directory-level carve-out separates them. `.claude/handoffs/` has no such
entanglement — it is a sibling of projects/ holding nothing user-reviewed.
"""

import json
import os
import sys
from pathlib import Path

# The marker lane lives in a sibling module so both guards share one copy of
# the contract (extracted 2026-08-19). Resolving this file's own directory
# explicitly rather than relying on sys.path[0]: this project has been bitten
# repeatedly by code that assumed the wrong base directory, and a guard that
# fails to import is a guard that does not run.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from guard_approval_marker import consume_approval_marker  # noqa: E402

PROTECTED_BASENAMES = ("CLAUDE.md", "CLAUDE.local.md")
PROTECTED_DIRECTORY = ".claude"
APPROVAL_MARKER_NAME = ".walk-approved"

MISSING_SESSION_DIRECTORY_DENY_MESSAGE = (
    "Refusing to modify {path}: this session's working directory ({cwd}) does not exist, so "
    "there is no session checkout to resolve an approval marker from. A seat whose worktree "
    "was removed while the session ran reaches this state. Move to a directory that exists, "
    "then resubmit. The approval lane is deliberately closed here rather than falling back to "
    "the target file's own repository: that fallback would let a marker left lying in an "
    "unrelated checkout approve this write."
)

DENY_MESSAGE = (
    "Before modifying {path}, get the user's approval on your change: instruction files "
    "(CLAUDE.md, CLAUDE.local.md identity files, and .claude/ machinery) change only "
    "through the user's walk, however clearly the edit would help. State the proposed "
    "change to the user and walk it with him. If he has already approved this exact "
    "change, quote his exact approval words into {marker} at the root of your session's "
    "own checkout, then resubmit your write or edit — the marker is consumed by the one "
    "call it approves."
)


def enclosing_repository_root(path: Path):
    """Nearest ancestor (or the path itself) that carries .git.

    A .git *file* counts too — that is how a linked worktree marks its root —
    so seats, task worktrees, and the main checkout all resolve alike.
    Returns None when no enclosing repository exists.
    """
    try:
        resolved = path.resolve()
    except (OSError, RuntimeError):
        return None
    for candidate in (resolved, *resolved.parents):
        try:
            if (candidate / ".git").exists():
                return candidate
        except OSError:
            continue
    return None


def session_directory_of(payload: dict) -> Path:
    """Where the session says it is working."""
    return Path(payload.get("cwd") or os.getcwd())


def marker_root(payload: dict, file_path: str):
    """The session's own checkout root; the target's repository as fallback.

    The payload's cwd is the session's own view of where it works, which is
    correct in forked sessions where $CLAUDE_PROJECT_DIR is not (rider 6).
    The fallback covers a session seated outside any checkout — a real
    directory that simply is not in a repository — where the only root left to
    honour is the target file's own.

    Callers must establish that the session directory EXISTS before calling
    this (PR #86's review). A vanished directory is a broken payload rather
    than a session seated outside a repository, and the two are
    indistinguishable here: both find no enclosing repository, so both would
    take the fallback and let a marker in the target's repository approve a
    write the session never earned.
    """
    root = enclosing_repository_root(session_directory_of(payload))
    if root is not None:
        return root
    return enclosing_repository_root(Path(file_path).parent)


def is_protected(file_path: str) -> bool:
    path = Path(file_path)
    if path.name in PROTECTED_BASENAMES:
        return True
    parts = path.resolve().parts
    for index, part in enumerate(parts):
        if part == PROTECTED_DIRECTORY:
            if index + 1 < len(parts) and parts[index + 1] in ("worktrees", "jobs", "handoffs"):
                # A worktree checkout's home under .claude/worktrees/, a
                # background job's scratch directory under .claude/jobs/<id>/tmp,
                # or a seat's handoff material under .claude/handoffs/ — all
                # working space the harness hands out, not machinery that
                # instructs anybody. Each carve-out was added after a real write
                # tripped the guard, which is the condition this file's docstring
                # sets for adding one: jobs 2026-08-13, handoffs 2026-08-31.
                continue
            return True
    return False


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return 0
    tool_input = payload.get("tool_input") or {}
    # NotebookEdit carries its target in notebook_path where Edit and Write use
    # file_path. This guard is registered on NotebookEdit, so reading only
    # file_path left every notebook write unguarded (PR #86's review).
    file_path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
    if not file_path or not is_protected(file_path):
        return 0

    session_directory = session_directory_of(payload)
    if not session_directory.is_dir():
        print(MISSING_SESSION_DIRECTORY_DENY_MESSAGE.format(
            path=file_path, cwd=session_directory), file=sys.stderr)
        return 2

    root = marker_root(payload, file_path)
    if root is not None and consume_approval_marker(root / APPROVAL_MARKER_NAME):
        return 0

    print(DENY_MESSAGE.format(path=file_path, marker=APPROVAL_MARKER_NAME), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
