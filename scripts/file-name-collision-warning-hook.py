#!/usr/bin/env python3
"""Warn after an Edit or Write when the written file shares another tracked file's name."""
# Move checks search by file name, so distinct tracked files need distinct names.

import json
import subprocess
import sys
from pathlib import Path, PurePath

# These names are identified by their folders; SKILL.md and README.md are required by their consumers.
EXEMPT_FILE_NAMES = frozenset({"skill.md", "readme.md", ".gitkeep"})

# A hook runs on every edit; bounded git calls keep a hung read from hanging the agent's turn.
GIT_CALL_TIMEOUT_SECONDS = 10


def git_output(arguments, cwd: Path):
    """Return git stdout, or None when git cannot answer."""
    try:
        finished = subprocess.run(["git", *arguments], cwd=str(cwd),
                                  capture_output=True, text=True, check=False,
                                  timeout=GIT_CALL_TIMEOUT_SECONDS)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None
    if finished.returncode != 0:
        return None
    return finished.stdout


def checkout_of(working_directory: Path):
    """Return the session's checkout, or None."""
    top_level = git_output(["rev-parse", "--show-toplevel"], working_directory)
    if top_level is None or not top_level.strip():
        return None
    return Path(top_level.strip()).resolve()


def path_within_checkout(file_path: str, checkout: Path):
    """Return the written file's repository-relative path, or None outside the checkout."""
    try:
        resolved = Path(file_path).resolve()
    except (OSError, ValueError):
        return None
    try:
        return resolved.relative_to(checkout)
    except ValueError:
        return None


def is_ignored(relative_path: PurePath, checkout: Path) -> bool:
    try:
        finished = subprocess.run(
            ["git", "check-ignore", "-q", "--", str(relative_path)],
            cwd=str(checkout), capture_output=True, text=True, check=False,
            timeout=GIT_CALL_TIMEOUT_SECONDS)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return False
    return finished.returncode == 0


def is_the_same_file_on_this_filesystem(tracked: str, written: PurePath,
                                        checkout: Path) -> bool:
    # Ask the filesystem: differently cased paths can name one file on a case-folding volume.
    if tracked == str(written):
        return True
    try:
        return (checkout / tracked).samefile(checkout / written)
    except (OSError, ValueError):
        return False


def tracked_paths_sharing_name(relative_path: PurePath, checkout: Path):
    """Return other tracked paths sharing the name ignoring case, or None if git cannot answer."""
    listing = git_output(["ls-files", "-z"], checkout)
    if listing is None:
        return None
    wanted = relative_path.name.lower()
    return sorted(
        tracked for tracked in listing.split("\0")
        if tracked and PurePath(tracked).name.lower() == wanted
        and not is_the_same_file_on_this_filesystem(
            tracked, relative_path, checkout))


def collision_warning_line(relative_path: PurePath, others) -> str:
    """Return the collision warning and instructions shown to the agent."""
    already = ", ".join(others)
    moved_from = others[0] if len(others) == 1 else "the file you moved from"
    return (
        f"file-name-collision-warning: you wrote {relative_path}; "
        f"the name {relative_path.name} is already {already}.\n"
        f"If you are moving the file, delete {moved_from} in this change.\n"
        f"If both files are meant to exist, rename the one you just wrote by "
        f"CLAUDE.md's naming rule, and update what you have already written "
        f"to point at the new name.")


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except (json.JSONDecodeError, ValueError, OSError):
        return 0
    if not isinstance(payload, dict):
        return 0

    tool_input = payload.get("tool_input")
    file_path = tool_input.get("file_path") if isinstance(tool_input, dict) else None
    if not file_path or not isinstance(file_path, str):
        return 0

    # Use payload cwd: CLAUDE_PROJECT_DIR can name the main checkout in a forked worktree session.
    working_directory = payload.get("cwd")
    if not working_directory or not isinstance(working_directory, str):
        return 0
    working_directory = Path(working_directory)
    if not working_directory.is_dir():
        return 0

    checkout = checkout_of(working_directory)
    if checkout is None:
        return 0

    relative_path = path_within_checkout(file_path, checkout)
    if relative_path is None:
        return 0
    if relative_path.name.lower() in EXEMPT_FILE_NAMES:
        return 0
    if is_ignored(relative_path, checkout):
        return 0

    others = tracked_paths_sharing_name(relative_path, checkout)
    if not others:
        return 0

    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PostToolUse",
        "additionalContext": collision_warning_line(relative_path, others),
    }}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
