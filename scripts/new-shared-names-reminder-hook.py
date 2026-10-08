#!/usr/bin/env python3
"""After a write, edit or shell command, name the shared names the branch newly adds, once per agent-session."""
# The hook never blocks: any failure leaves the agent's turn as it was, apart from one line saying the check failed.

import hashlib
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

GIT_CALL_TIMEOUT_SECONDS = 10
# A first reminder on a large branch would otherwise run to hundreds of lines.
REMINDER_NAME_LIMIT = 30
LISTER_COMMAND = "scripts/new-shared-names-in-changed-files-list.py"
FILE_WRITING_TOOL_NAMES = frozenset({"Write", "Edit", "MultiEdit", "NotebookEdit"})
SHELL_TOOL_NAME = "Bash"
GIT_GLOBAL_OPTIONS = r"\bgit\s+(?:(?:-C|-c)\s+\S+\s+|--\S+\s+)*"
BRANCH_NAME = r"([A-Za-z0-9][^\s;&|]*)"
BRANCH_CREATION_PATTERNS = (
    # git checkout|switch [options]... -b|-B|-c|-C|--create|--force-create <name>
    re.compile(GIT_GLOBAL_OPTIONS + r"(?:checkout|switch)\s+(?:-\S*\s+)*?"
               r"(?:-b|-B|-c|-C|--create|--force-create)\s+" + BRANCH_NAME),
    # git worktree add [options]... -b|-B <name>
    re.compile(GIT_GLOBAL_OPTIONS + r"worktree\s+add\s+(?:-\S*\s+)*?(?:-b|-B)\s+" + BRANCH_NAME),
    # git branch [-f|--force|-t|--track|--no-track|-q|--quiet]... <name>; listing, deleting and renaming do not match
    re.compile(GIT_GLOBAL_OPTIONS + r"branch\s+(?:(?:-f|--force|-t|--track|--no-track|-q|--quiet)\s+)*"
               + BRANCH_NAME),
)
STATE_DIRECTORY = Path(tempfile.gettempdir()) / "new-shared-names-reminder-hook-state"
SESSION_ID_SAFE_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
LISTER_PATH = Path(__file__).resolve().parent / "new-shared-names-in-changed-files-list.py"
NAMING_PAGE_PATH = "docs/nedschorus-wiki/nedschorus-how-to-choose-a-name-for-files-code-and-glossary-terms.md"
NAMING_FRESH_AGENT_NAME = "new-name-propose-and-check-fresh-agent"

REMINDER_TEMPLATE = (
    "new-shared-names-reminder: your branch now adds these shared names, which other files "
    "or agents will meet:\n{names}\n"
    "Send them, with one sentence on what each names, to the {agent} subagent, run in the "
    "background, and keep working.\n"
    "When it flags a name, rename it everywhere your branch uses it, in one commit.\n"
    "If it flags a new project-term or system-term, put the new term to the user before you "
    "use it.\n"
    "If a listed name is not one you chose, such as quoted text or an existing name written "
    "differently, do not send it and do not rename it.\n"
    "How names are chosen: {page}."
)
MORE_NAMES_LINE = "  and {count} more; run {command} to see all"
FAILURE_TEMPLATE = (
    "new-shared-names-reminder: the check for new shared names on this branch failed, so "
    "no names are being listed: {error}\n"
    "If the error names origin/main, run `git fetch`; the check runs again after your next "
    "edit.\n"
    "Until it works, check new names by hand against {page}."
)


def load_lister():
    spec = importlib.util.spec_from_file_location("new_shared_names_in_changed_files_list", LISTER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git_output(arguments, cwd: Path):
    try:
        finished = subprocess.run(["git", *arguments], cwd=str(cwd), capture_output=True,
                                  text=True, check=False, timeout=GIT_CALL_TIMEOUT_SECONDS)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None
    if finished.returncode != 0:
        return None
    return finished.stdout


def state_path_for(session_id: str) -> Path:
    return STATE_DIRECTORY / f"{session_id}.json"


def empty_state() -> dict:
    return {"reported": [], "worktree_fingerprint": "", "file_cache": {}, "reported_failures": []}


def read_state(session_id: str) -> dict:
    try:
        state = json.loads(state_path_for(session_id).read_text())
    except (OSError, ValueError):
        return empty_state()
    if not isinstance(state, dict):
        return empty_state()
    return dict(empty_state(), **state)


def write_state(session_id: str, state: dict) -> None:
    try:
        STATE_DIRECTORY.mkdir(parents=True, exist_ok=True)
        temporary = state_path_for(session_id).with_suffix(".partial")
        temporary.write_text(json.dumps(state))
        temporary.replace(state_path_for(session_id))
    except OSError:
        pass


def worktree_fingerprint(checkout: Path):
    """Return a digest of HEAD, the uncommitted changes and the untracked files, or None when git cannot answer."""
    head = git_output(["rev-parse", "HEAD"], checkout)
    status = git_output(["status", "--porcelain", "--untracked-files=all"], checkout)
    diff = git_output(["diff", "HEAD"], checkout)
    untracked = git_output(["ls-files", "--others", "--exclude-standard"], checkout)
    if head is None or status is None or diff is None or untracked is None:
        return None
    parts = [head, status, diff]
    for path in untracked.splitlines():
        try:
            details = (checkout / path).stat()
        except OSError:
            continue
        parts.append(f"{path}\0{details.st_size}\0{details.st_mtime_ns}")
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()


def created_branch_name(command: str):
    for pattern in BRANCH_CREATION_PATTERNS:
        match = pattern.search(command)
        if match:
            return match.group(1)
    return None


def reminder_text(new_names) -> str:
    lines = [f"  {name} ({kind}{', in ' + path if path and path != name else ''})"
             for path, kind, name in new_names[:REMINDER_NAME_LIMIT]]
    if len(new_names) > REMINDER_NAME_LIMIT:
        lines.append(MORE_NAMES_LINE.format(count=len(new_names) - REMINDER_NAME_LIMIT,
                                            command=LISTER_COMMAND))
    return REMINDER_TEMPLATE.format(names="\n".join(lines), agent=NAMING_FRESH_AGENT_NAME,
                                    page=NAMING_PAGE_PATH)


def emit(text: str) -> None:
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PostToolUse",
        "additionalContext": text,
    }}, ensure_ascii=False))


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except (json.JSONDecodeError, ValueError, OSError):
        return 0
    if not isinstance(payload, dict):
        return 0

    tool_name = payload.get("tool_name")
    if tool_name not in FILE_WRITING_TOOL_NAMES and tool_name != SHELL_TOOL_NAME:
        return 0
    session_id = payload.get("session_id")
    if not isinstance(session_id, str) or not SESSION_ID_SAFE_PATTERN.match(session_id):
        return 0
    working_directory = payload.get("cwd")
    if not isinstance(working_directory, str) or not Path(working_directory).is_dir():
        return 0
    top_level = git_output(["rev-parse", "--show-toplevel"], Path(working_directory))
    if not top_level or not top_level.strip():
        return 0
    checkout = Path(top_level.strip())

    branch_name = None
    if tool_name == SHELL_TOOL_NAME:
        tool_input = payload.get("tool_input")
        command = tool_input.get("command") if isinstance(tool_input, dict) else None
        if isinstance(command, str):
            branch_name = created_branch_name(command)

    state = read_state(session_id)
    fingerprint = worktree_fingerprint(checkout)
    if fingerprint is None:
        return 0
    # A shell command that changed no file and made no branch has nothing new to list.
    if (tool_name == SHELL_TOOL_NAME and branch_name is None
            and fingerprint == state.get("worktree_fingerprint")):
        return 0
    state["worktree_fingerprint"] = fingerprint

    reported = set(state.get("reported", []))
    file_cache = state.get("file_cache") if isinstance(state.get("file_cache"), dict) else {}
    try:
        lister = load_lister()
        names = lister.new_shared_names(checkout, branch_name, already_reported=frozenset(reported),
                                        file_cache=file_cache)
    except Exception as failure:
        error = str(failure) or type(failure).__name__
        failures = set(state.get("reported_failures", []))
        state["file_cache"] = file_cache
        if error not in failures:
            state["reported_failures"] = sorted(failures | {error})
            write_state(session_id, state)
            emit(FAILURE_TEMPLATE.format(error=error, page=NAMING_PAGE_PATH))
        else:
            write_state(session_id, state)
        return 0

    state["file_cache"] = file_cache
    state["reported"] = sorted(reported | {f"{kind}\t{name}" for _, kind, name in names})
    write_state(session_id, state)
    if not names:
        return 0
    emit(reminder_text(names))
    return 0


if __name__ == "__main__":
    sys.exit(main())
