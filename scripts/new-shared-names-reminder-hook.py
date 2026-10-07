#!/usr/bin/env python3
"""After a write, edit or shell command, name the shared names the branch newly adds, once per agent-session."""
# The hook never blocks: any failure leaves the agent's turn as it was.

import hashlib
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

GIT_CALL_TIMEOUT_SECONDS = 10
FILE_WRITING_TOOL_NAMES = frozenset({"Write", "Edit", "MultiEdit", "NotebookEdit"})
SHELL_TOOL_NAME = "Bash"
BRANCH_CREATION_PATTERN = re.compile(r"\bgit\s+(?:switch\s+(?:-c|--create)|checkout\s+-b)\s+([^\s;&|]+)")
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
    "If a listed name is not one you chose, such as quoted text or an existing name written "
    "differently, leave it.\n"
    "How names are chosen: {page}."
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


def read_state(session_id: str) -> dict:
    try:
        state = json.loads(state_path_for(session_id).read_text())
    except (OSError, ValueError):
        return {"reported": [], "worktree_fingerprint": ""}
    if not isinstance(state, dict):
        return {"reported": [], "worktree_fingerprint": ""}
    return state


def write_state(session_id: str, state: dict) -> None:
    try:
        STATE_DIRECTORY.mkdir(parents=True, exist_ok=True)
        state_path_for(session_id).write_text(json.dumps(state))
    except OSError:
        pass


def worktree_fingerprint(checkout: Path):
    """Return a digest of HEAD and the uncommitted changes, or None when git cannot answer."""
    head = git_output(["rev-parse", "HEAD"], checkout)
    status = git_output(["status", "--porcelain", "--untracked-files=all"], checkout)
    diff = git_output(["diff", "HEAD"], checkout)
    if head is None or status is None or diff is None:
        return None
    return hashlib.sha256((head + status + diff).encode()).hexdigest()


def reminder_text(new_names) -> str:
    lines = "\n".join(f"  {name} ({kind}{', in ' + path if path and path != name else ''})"
                      for path, kind, name in new_names)
    return REMINDER_TEMPLATE.format(names=lines, agent=NAMING_FRESH_AGENT_NAME, page=NAMING_PAGE_PATH)


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
            match = BRANCH_CREATION_PATTERN.search(command)
            if match:
                branch_name = match.group(1)

    state = read_state(session_id)
    fingerprint = worktree_fingerprint(checkout)
    if fingerprint is None:
        return 0
    # A shell command that changed no file and made no branch has nothing new to list.
    if (tool_name == SHELL_TOOL_NAME and branch_name is None
            and fingerprint == state.get("worktree_fingerprint")):
        return 0

    try:
        lister = load_lister()
        names = lister.new_shared_names(checkout, branch_name)
    except Exception:
        return 0

    reported = set(state.get("reported", []))
    new_names = [triple for triple in names if f"{triple[1]}\t{triple[2]}" not in reported]
    state["worktree_fingerprint"] = fingerprint
    state["reported"] = sorted(reported | {f"{kind}\t{name}" for _, kind, name in new_names})
    write_state(session_id, state)
    if not new_names:
        return 0

    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PostToolUse",
        "additionalContext": reminder_text(new_names),
    }}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
