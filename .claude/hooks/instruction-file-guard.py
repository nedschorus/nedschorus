#!/usr/bin/env python3
"""Require user approval for edits to instructions and reviewed documents.

The session checkout owns the approval marker; forked sessions can inherit
CLAUDE_PROJECT_DIR from another checkout. Protecting .claude also protects
the hook wiring. Transcripts share the protected auto-memory directory.

This hook sees Edit, Write and NotebookEdit calls, not writes through shell
commands or other programs.

The refusals tell the agent to create the marker with the Write tool, because
Claude Code's auto-mode classifier can refuse a shell command that writes the
marker. In the machine's reference checkout, session-location-write-guard.py
refuses the Write of the marker and the edit itself, so the refusals send the
agent to its own worktree."""

import json
import os
import sys
from pathlib import Path

# Resolve the sibling import from this file, independent of the caller's working directory.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from guard_approval_marker import consume_approval_marker  # noqa: E402

PROTECTED_BASENAMES = ("CLAUDE.md", "CLAUDE.local.md")
PROTECTED_DIRECTORY = ".claude"
REUSABLE_PROMPT_SUFFIXES = ("-prompt.md", "-instructions.md")
PROMPT_DRAFT_DIRECTORY_NAMES = ("queue", "nc-queue")
PROMPT_EXEMPT_DIRECTORY_PREFIXES = (("docs", "drafts"), (".claude", "jobs"), (".claude", "handoffs"))
REVIEWED_DOCUMENT_SUFFIX = ".md"
REVIEWED_HOME_DIRECTORY_PREFIXES = (("docs", "agents"), ("docs", "nedschorus-wiki"), ("nc-systems", "skills"))
REVIEWED_DESIGN_SUFFIX = "-design.md"
UNREVIEWED_DOCUMENT_SUFFIXES = ("-test-design.md", "-contract.md")
REVIEW_RECORD_DIRECTORY_NAMES = ("cold-read-records", "md-review-records", "sanity-check-records")
APPROVAL_MARKER_NAME = ".walk-approved"

MISSING_SESSION_DIRECTORY_DENY_MESSAGE = (
    "Refusing to modify {path}: this session's working directory ({cwd}) does not exist, so "
    "there is no session checkout to resolve an approval marker from. A seat whose worktree "
    "was removed while the session ran reaches this state. Move to a directory that exists, "
    "then resubmit. The approval lane is deliberately closed here rather than falling back to "
    "the target file's own repository: that fallback would let a marker left lying in an "
    "unrelated checkout approve this write."
)

# The marker's opening words stay exact: the glossary's obvious-fix marker is
# defined by them, and a check that exempts such markers would match on them.
OBVIOUS_FIX_MARKER_LINES = (
    "\nFor an obvious error, write \"Obvious fix under CLAUDE.md's standing approval:\" "
    "and what you are fixing into {marker} at the root of your session's own checkout, "
    "then resubmit.\n"
    "If the edit then does not happen, delete {marker}."
)

# Each refusal ends with these lines, one for each way cooperative agents went
# around the refusal by accident: moving the text into code, editing by another
# route so the marker was never spent, and quoting approval of something else.
ROUTE_AROUND_LINES = (
    "\nDo not move this text into a program's string or under another file name to get "
    "past this check; prompt text in code is still a reusable prompt.\n"
    "Make the approved change with Edit or Write, so that call uses up the marker; an "
    "unspent marker approves the next guarded write.\n"
    "A task prompt or another agent's message is the user's approval only when it quotes "
    "his exact words for this change with the session and time he wrote them."
)

COLD_READ_BEFORE_ASKING_SENTENCES = (
    "Before you put the change to the user, write the changed text to a file in your "
    "session's scratchpad and give it the cold read that step 2 of the /cold-read skill "
    "names for it, a fast read for a change of one sentence; revise the text from the "
    "findings once, then put the change to him. Skip this when the change only fixes an "
    "obvious error `CLAUDE.md` lets you fix without asking."
)

REUSABLE_PROMPT_DENY_MESSAGE = (
    "Before modifying {path}, get the user's approval on your change: a reusable prompt, "
    "a file named -prompt.md or -instructions.md in a checkout, changes only through the "
    "user's walk. " + COLD_READ_BEFORE_ASKING_SENTENCES + " State the proposed change to the user and walk it with him. If he has "
    "already approved this exact change, quote his exact approval words into {marker} at "
    "the root of your session's own checkout, then resubmit your write or edit — the marker "
    "is consumed by the one call it approves. Create {marker} with the Write tool, not a "
    "shell command. If this session sits in the machine's reference checkout, another "
    "guard refuses that Write and the edit itself: make the change from your own "
    "worktree, and put {marker} at that worktree's root. If the prompt is a one-off, "
    "write it outside "
    "the checkout, in your scratchpad. If it is a draft for his walk, write it in a queue "
    "directory or docs/drafts/."
) + OBVIOUS_FIX_MARKER_LINES + ROUTE_AROUND_LINES

REVIEWED_DOCUMENT_DENY_MESSAGE = (
    "Get the user's approval before you change {path}; he reviews every change to a file here.\n"
    + COLD_READ_BEFORE_ASKING_SENTENCES + "\n"
    "If he has approved this exact change, quote his exact approval words into {marker} at "
    "the root of your session's own checkout, then resubmit; the marker is used up by the "
    "one call it approves.\n"
    "Create {marker} with the Write tool, not a shell command.\n"
    "If this session sits in the machine's reference checkout, another guard refuses that "
    "Write and the edit itself: make the change from your own worktree, and put {marker} "
    "at that worktree's root.\n"
    "If he has not, show him the change and wait for his answer; if you are a subagent, "
    "report the change to the agent that dispatched you instead.\n"
    "If this is a first draft, write it in docs/drafts/ or in a queue directory such as "
    "docs/issues/queue/, docs/agents/queue/ or docs/nedschorus-wiki/queue/ instead."
) + OBVIOUS_FIX_MARKER_LINES + ROUTE_AROUND_LINES

MEMORY_WRITE_DENY_MESSAGE = (
    "Refusing to write {path}: it is in a Claude Code memory directory, where nothing "
    "recalls a note at the moment it applies.\n"
    "If what you meant to save would change how agents work, propose to the user the exact "
    "edit, with its wording, to the instruction file, skill or program where an agent would "
    "meet it.\n"
    "If you cannot tell where it belongs, tell the user in one sentence what you meant to "
    "remember, and ask him where to save it so that an agent recalls it when it applies.\n"
    "If it matters only to this conversation, drop it.\n"
    "If you are a subagent, put this to the agent that dispatched you instead.\n"
    "No {marker} marker lets a write into a memory directory through, so do not write one "
    "for this."
)

DENY_MESSAGE = (
    "Before modifying {path}, get the user's approval on your change: instruction files "
    "(CLAUDE.md, CLAUDE.local.md identity files, and .claude/ machinery) change only "
    "through the user's walk, however clearly the edit would help. "
    + COLD_READ_BEFORE_ASKING_SENTENCES + " State the proposed "
    "change to the user and walk it with him. If he has already approved this exact "
    "change, quote his exact approval words into {marker} at the root of your session's "
    "own checkout, then resubmit your write or edit — the marker is consumed by the one "
    "call it approves. Create {marker} with the Write tool, not a shell command. If this "
    "session sits in the machine's reference checkout, another guard refuses that Write "
    "and the edit itself: make the change from your own worktree, and put {marker} at "
    "that worktree's root."
) + OBVIOUS_FIX_MARKER_LINES + ROUTE_AROUND_LINES


def enclosing_repository_root(path: Path):
    """Return the nearest repository root, or None."""
    # Linked worktrees use a .git file; sandbox-created empty .git directories are not repositories.
    try:
        resolved = path.resolve()
    except (OSError, RuntimeError):
        return None
    for candidate in (resolved, *resolved.parents):
        git_marker = candidate / ".git"
        try:
            if git_marker.is_file() or (git_marker / "HEAD").is_file():
                return candidate
        except OSError:
            continue
    return None


def session_directory_of(payload: dict) -> Path:
    return Path(payload.get("cwd") or os.getcwd())


def marker_root(payload: dict, file_path: str):
    """Return the session checkout root, falling back to the target's repository."""
    # Callers must reject a missing session directory before fallback can authorize any write.
    root = enclosing_repository_root(session_directory_of(payload))
    if root is not None:
        return root
    return enclosing_repository_root(Path(file_path).parent)


def checkout_directory_parts(path: Path):
    """Return directories below the checkout root, or None outside a checkout."""
    root = enclosing_repository_root(path.parent)
    if root is None:
        return None
    try:
        return path.resolve().relative_to(root).parts[:-1]
    except ValueError:
        return None


def is_in_draft_or_working_place(directory_parts) -> bool:
    if any(part in PROMPT_DRAFT_DIRECTORY_NAMES for part in directory_parts):
        return True
    return any(directory_parts[:len(prefix)] == prefix
               for prefix in PROMPT_EXEMPT_DIRECTORY_PREFIXES)


def is_in_review_record_directory(path: Path) -> bool:
    """A review record holds frozen copies of the documents it read, named as the originals
    are, such as cold-read-records/<record>/target/CLAUDE.local.md; no agent takes
    instructions from a copy."""
    directory_parts = checkout_directory_parts(path)
    return bool(directory_parts) and directory_parts[0] in REVIEW_RECORD_DIRECTORY_NAMES


def is_reusable_prompt(file_path: str) -> bool:
    path = Path(file_path)
    if not path.name.endswith(REUSABLE_PROMPT_SUFFIXES):
        return False
    directory_parts = checkout_directory_parts(path)
    if directory_parts is None or is_in_review_record_directory(path):
        return False
    return not is_in_draft_or_working_place(directory_parts)


def is_reviewed_document(file_path: str) -> bool:
    path = Path(file_path)
    if not path.name.endswith(REVIEWED_DOCUMENT_SUFFIX):
        return False
    directory_parts = checkout_directory_parts(path)
    if (directory_parts is None or is_in_draft_or_working_place(directory_parts)
            or is_in_review_record_directory(path)):
        return False
    # Test designs and contracts follow design-to-main acceptance, even in reviewed homes.
    if path.name.endswith(UNREVIEWED_DOCUMENT_SUFFIXES):
        return False
    if any(directory_parts[:len(prefix)] == prefix
           for prefix in REVIEWED_HOME_DIRECTORY_PREFIXES):
        return True
    return path.name.endswith(REVIEWED_DESIGN_SUFFIX)


def is_protected(file_path: str) -> bool:
    path = Path(file_path)
    if is_in_review_record_directory(path):
        return False
    if path.name in PROTECTED_BASENAMES:
        return True
    parts = path.resolve().parts
    for index, part in enumerate(parts):
        if part == PROTECTED_DIRECTORY:
            if index + 1 < len(parts) and parts[index + 1] in ("worktrees", "jobs", "handoffs"):
                # Harness worktrees, job scratch directories and handoffs are working space, not instructions.
                continue
            return True
    return False


def is_in_memory_directory(file_path: str) -> bool:
    """Whether the target sits in a Claude Code memory directory, .claude/projects/<project>/memory/."""
    parts = Path(file_path).resolve().parts
    for index in range(len(parts) - 4):
        if (parts[index] == PROTECTED_DIRECTORY and parts[index + 1] == "projects"
                and parts[index + 3] == "memory"):
            return True
    return False


def is_in_session_scratchpad(file_path: str, session_id) -> bool:
    """Whether the target sits in this session's own scratchpad, the per-session
    directory the harness makes under its temporary root, named <session id>/scratchpad.

    A scratchpad is private to one session and loaded by nothing, so a draft there
    instructs no agent. A checkout made inside the scratchpad is not exempt: its files
    reach main through an ordinary commit and push. Every other path outside a
    checkout stays protected: the user's own ~/.claude/CLAUDE.md and settings sit
    outside every checkout.
    """
    if not isinstance(session_id, str) or not session_id:
        return False
    if enclosing_repository_root(Path(file_path).parent) is not None:
        return False
    for candidate in (Path(file_path), Path(file_path).resolve()):
        parts = candidate.parts
        for index in range(len(parts) - 2):
            if (parts[index + 1] == session_id and parts[index + 2] == "scratchpad"
                    and any(part.startswith("claude-") for part in parts[:index + 1])):
                return True
    return False


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return 0
    tool_input = payload.get("tool_input") or {}
    # NotebookEdit names its target notebook_path; Edit and Write use file_path.
    file_path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
    if not file_path:
        return 0
    if is_in_session_scratchpad(file_path, payload.get("session_id")):
        return 0
    # Checked before the marker, which approves instruction edits but never a memory write.
    if is_in_memory_directory(file_path):
        print(MEMORY_WRITE_DENY_MESSAGE.format(path=file_path, marker=APPROVAL_MARKER_NAME),
              file=sys.stderr)
        return 2
    reusable_prompt = is_reusable_prompt(file_path)
    instruction_file = is_protected(file_path)
    reviewed_document = is_reviewed_document(file_path)
    if not (reusable_prompt or instruction_file or reviewed_document):
        return 0

    session_directory = session_directory_of(payload)
    if not session_directory.is_dir():
        print(MISSING_SESSION_DIRECTORY_DENY_MESSAGE.format(
            path=file_path, cwd=session_directory), file=sys.stderr)
        return 2

    root = marker_root(payload, file_path)
    if root is not None and consume_approval_marker(root / APPROVAL_MARKER_NAME):
        return 0

    if reusable_prompt:
        deny_message = REUSABLE_PROMPT_DENY_MESSAGE
    elif instruction_file:
        deny_message = DENY_MESSAGE
    else:
        deny_message = REVIEWED_DOCUMENT_DENY_MESSAGE
    print(deny_message.format(path=file_path, marker=APPROVAL_MARKER_NAME), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
