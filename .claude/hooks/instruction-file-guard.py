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
carve-out is added when a real harness write trips this guard, not in advance.
Two exist, each added that way: `.claude/worktrees/` (an agent's isolated
checkout) and `.claude/jobs/` (a background job's scratch directory, which the
harness hands out for temporary files and deletes with the job).
"""

import json
import os
import sys
from pathlib import Path

PROTECTED_BASENAMES = ("CLAUDE.md", "CLAUDE.local.md")
PROTECTED_DIRECTORY = ".claude"
APPROVAL_MARKER_NAME = ".walk-approved"

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


def marker_root(payload: dict, file_path: str):
    """The session's own checkout root; the target's repository as fallback.

    The payload's cwd is the session's own view of where it works, which is
    correct in forked sessions where $CLAUDE_PROJECT_DIR is not (rider 6).
    The fallback covers a session seated outside any checkout: the only root
    left to honour is the target file's own.
    """
    session_cwd = payload.get("cwd") or os.getcwd()
    root = enclosing_repository_root(Path(session_cwd))
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
            if index + 1 < len(parts) and parts[index + 1] in ("worktrees", "jobs"):
                # A worktree checkout's home under .claude/worktrees/, or a
                # background job's scratch directory under .claude/jobs/<id>/tmp
                # — both are working space the harness hands out, not machinery
                # that instructs anybody. The jobs carve-out was added 2026-08-13
                # after a real write tripped the guard, which is the condition
                # this file's docstring sets for adding one.
                continue
            return True
    return False


def consume_approval_marker(marker_path: Path) -> bool:
    """One approved change passes; the marker is spent by the call it approves."""
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
    file_path = (payload.get("tool_input") or {}).get("file_path") or ""
    if not file_path or not is_protected(file_path):
        return 0

    root = marker_root(payload, file_path)
    if root is not None and consume_approval_marker(root / APPROVAL_MARKER_NAME):
        return 0

    print(DENY_MESSAGE.format(path=file_path, marker=APPROVAL_MARKER_NAME), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
