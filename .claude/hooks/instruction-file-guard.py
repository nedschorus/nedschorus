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
writing the user's exact approval words into .walk-approved at the
repository root; the marker is consumed by the passing call. The override is
deliberately self-serve — the audit value is the visible, quoted approval in
the marker and the transcript, not tamper-proofing.

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
    "change, quote his exact approval words into {marker} at the repository root, then "
    "resubmit your write or edit — the marker is consumed by the one call it approves."
)


def project_root() -> Path:
    return Path(os.environ.get("CLAUDE_PROJECT_DIR", ".")).resolve()


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

    marker_path = project_root() / APPROVAL_MARKER_NAME
    if consume_approval_marker(marker_path):
        return 0

    print(DENY_MESSAGE.format(path=file_path, marker=APPROVAL_MARKER_NAME), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
