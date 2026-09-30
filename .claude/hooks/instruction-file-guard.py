#!/usr/bin/env python3
"""User-block on modifying instruction files (user-walked 2026-08-07, nedschorus#45).

Wired as a PreToolUse hook on Edit, Write, and NotebookEdit. Instruction
files — CLAUDE.md, per-agent CLAUDE.local.md identity files, and everything
under .claude/ — change only through the user's walk. Agents predictably try
to improve them (observed repeatedly in the legacy fleet); a path-scoped rule
cannot stop that (rules are context, not enforcement, and file creation
never triggers them — probed 2026-08-07), so the block lives at the tool
call, where it also catches creation.

User-block, not a wall: the deny message teaches the sanctioned path and
names the override. An edit the user has already approved passes once by
writing the user's exact approval words into .walk-approved at the root of
the session's own checkout; the marker is consumed by the passing call. The
override is deliberately self-serve — the audit value is the visible, quoted
approval in the marker and the transcript, not tamper-proofing.

Classed a user-block rather than a soft-block (user-ruled 2026-09-21, walk
open-questions-concerns-and-recommendations-2026-09-21, item 2). The three
kinds are told apart by whose words clear the block: a soft-block takes the
agent's own reasoning, this one takes the user's, a hard-block takes neither.
The glossary had defined soft-block as a hook refusal cleared by a reason the
agent supplies, which no hook here has ever implemented — so an agent blocked
by this one could read the glossary and conclude it need only state a reason.

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

Reusable prompts are protected wherever they sit in a checkout (user-ruled
2026-09-29, in the MD-skills seat's session: "Agents are bad at writing
prose. We should guard changes to prompts, that is I should approve them, if
they are reusable or not one offs."). A reusable prompt is recognized by name:
a file ending `-prompt.md` or `-instructions.md`, the endings the file-naming
page gives a skill prompt, an agent's initial-agent-instructions and its
instructions. That covers the seat briefs, first prompts, reviewer
instructions and sanity-checker prompts in docs/agents/, which nothing
guarded before, and every skill prompt once the one-directory-per-system
migration (GHI 224) moves it out of .claude/skills/ into nc-systems/skills/
and renames it to carry the ending. The same ruling has that migration move
the prompt text embedded in programs into `-prompt.md` files beside them,
which is how this guard comes to cover it; a path guard cannot see a string
inside code. It extends the user's 2026-09-23 ruling (walk
file-naming-page-revision-2026-09-23, item 8) that guarded only the prompts
and instruction text under nc-systems/skills/, by the same two endings, and
left the code there to pull-request review.

Four places are exempt, because what is written there is not yet, or never
becomes, a reusable prompt: a file outside any checkout (a one-off prompt in
an agent's scratchpad); a queue directory (`queue/` or `nc-queue/`) and
`docs/drafts/`, where a draft waits for the user's walk, which is the
approval; and the .claude/jobs/ and .claude/handoffs/ carve-outs below, which
are working space.

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
REUSABLE_PROMPT_SUFFIXES = ("-prompt.md", "-instructions.md")
PROMPT_DRAFT_DIRECTORY_NAMES = ("queue", "nc-queue")
PROMPT_EXEMPT_DIRECTORY_PREFIXES = (("docs", "drafts"), (".claude", "jobs"), (".claude", "handoffs"))
APPROVAL_MARKER_NAME = ".walk-approved"

MISSING_SESSION_DIRECTORY_DENY_MESSAGE = (
    "Refusing to modify {path}: this session's working directory ({cwd}) does not exist, so "
    "there is no session checkout to resolve an approval marker from. A seat whose worktree "
    "was removed while the session ran reaches this state. Move to a directory that exists, "
    "then resubmit. The approval lane is deliberately closed here rather than falling back to "
    "the target file's own repository: that fallback would let a marker left lying in an "
    "unrelated checkout approve this write."
)

REUSABLE_PROMPT_DENY_MESSAGE = (
    "Before modifying {path}, get the user's approval on your change: a reusable prompt, "
    "a file named -prompt.md or -instructions.md in a checkout, changes only through the "
    "user's walk. State the proposed change to the user and walk it with him. If he has "
    "already approved this exact change, quote his exact approval words into {marker} at "
    "the root of your session's own checkout, then resubmit your write or edit — the marker "
    "is consumed by the one call it approves. If the prompt is a one-off, write it outside "
    "the checkout, in your scratchpad. If it is a draft for his walk, write it in a queue "
    "directory or docs/drafts/."
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


def is_reusable_prompt(file_path: str) -> bool:
    """A file named as a reusable prompt, inside a checkout, and outside the
    directories where drafts and working files are written."""
    path = Path(file_path)
    if not path.name.endswith(REUSABLE_PROMPT_SUFFIXES):
        return False
    root = enclosing_repository_root(path.parent)
    if root is None:
        return False
    try:
        directory_parts = path.resolve().relative_to(root).parts[:-1]
    except ValueError:
        return False
    if any(part in PROMPT_DRAFT_DIRECTORY_NAMES for part in directory_parts):
        return False
    return not any(directory_parts[:len(prefix)] == prefix
                   for prefix in PROMPT_EXEMPT_DIRECTORY_PREFIXES)


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
    if not file_path:
        return 0
    reusable_prompt = is_reusable_prompt(file_path)
    if not reusable_prompt and not is_protected(file_path):
        return 0

    session_directory = session_directory_of(payload)
    if not session_directory.is_dir():
        print(MISSING_SESSION_DIRECTORY_DENY_MESSAGE.format(
            path=file_path, cwd=session_directory), file=sys.stderr)
        return 2

    root = marker_root(payload, file_path)
    if root is not None and consume_approval_marker(root / APPROVAL_MARKER_NAME):
        return 0

    deny_message = REUSABLE_PROMPT_DENY_MESSAGE if reusable_prompt else DENY_MESSAGE
    print(deny_message.format(path=file_path, marker=APPROVAL_MARKER_NAME), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
