#!/usr/bin/env python3
"""Warn after an Edit or Write when the written file shares another tracked file's name."""
# Move checks search by file name, so distinct tracked files need distinct names.

import importlib.util
import json
import os
import sys
from pathlib import Path, PurePath

_git_machine_readable_output_spec = importlib.util.spec_from_file_location(
    "git_machine_readable_output_runner_and_parser_common",
    Path(__file__).resolve().parents[1] / "nc-systems" / "general-tools"
    / "git-machine-readable-output-runner-and-parser-common.py")
git_machine_readable_output = importlib.util.module_from_spec(_git_machine_readable_output_spec)
_git_machine_readable_output_spec.loader.exec_module(git_machine_readable_output)

_next_step_lines_spec = importlib.util.spec_from_file_location(
    "failed_command_rerun_then_stop_next_step_lines_common",
    Path(__file__).resolve().parents[1] / "nc-systems" / "general-tools"
    / "failed-command-rerun-then-stop-next-step-lines-common.py")
next_step_lines = importlib.util.module_from_spec(_next_step_lines_spec)
_next_step_lines_spec.loader.exec_module(next_step_lines)

# These names are identified by their folders; SKILL.md and README.md are required by their consumers.
EXEMPT_FILE_NAMES = frozenset({"skill.md", "readme.md", ".gitkeep"})

# A hook runs on every edit; bounded git calls keep a hung read from hanging the agent's turn.
GIT_CALL_TIMEOUT_SECONDS = 10

GIT_FAILURE_TEMPLATE = (
    "file-name-collision-warning: git {command} failed ({outcome}), so {path} was not checked "
    "for a name another tracked file has.\n"
    "Nothing needs rerunning: this check runs again at your next Write or Edit.\n"
    + next_step_lines.same_failure_again_line(
        "at your next Write or Edit", "file-name-collision-warning-hook.py")
)


def git_output(arguments, cwd: Path, accepted_exit_codes=(0,)) -> str:
    """Return git stdout; raises GitCommandFailed when git fails."""
    return os.fsdecode(git_machine_readable_output.run_git(
        cwd, arguments, accepted_exit_codes=accepted_exit_codes,
        timeout_seconds=GIT_CALL_TIMEOUT_SECONDS))


def git_failure_text(failure, path) -> str:
    """Return the stderr text for a git failure; its first line, the one Claude Code shows the user, carries the cause."""
    if failure.returncode is None:
        outcome = failure.stderr
    else:
        outcome = f"exit {failure.returncode}: {' '.join(failure.stderr.split()) or 'no error text'}"
    return GIT_FAILURE_TEMPLATE.format(command=" ".join(failure.arguments), outcome=outcome, path=path)


def checkout_of(working_directory: Path):
    """Return the session's checkout, or None outside any repository; raises GitCommandFailed when git fails."""
    top_level = git_machine_readable_output.run_git_unless_outside_a_repository(
        working_directory, ["rev-parse", "--show-toplevel"], timeout_seconds=GIT_CALL_TIMEOUT_SECONDS)
    if top_level is None or not top_level.strip():
        return None
    return Path(os.fsdecode(top_level).strip()).resolve()


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
    # Without -q, check-ignore prints an ignored path and exits 0, or prints nothing and exits 1.
    return git_output(["check-ignore", "--", str(relative_path)], checkout,
                      accepted_exit_codes=(0, 1)) != ""


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
    """Return other tracked paths sharing the name ignoring case; raises GitCommandFailed when git fails."""
    listing = git_output(["ls-files", "-z"], checkout)
    wanted = relative_path.name.lower()
    return sorted(
        tracked for tracked in listing.split("\0")
        if tracked and PurePath(tracked).name.lower() == wanted
        and not is_the_same_file_on_this_filesystem(
            tracked, relative_path, checkout))


COLLISION_WARNING_TEMPLATE = (
    "file-name-collision-warning: you wrote {path}; the name {name} is already {already}. "
    "A basename, other than SKILL.md, README.md and .gitkeep, belongs to one tracked file, "
    "so the file can be cited by its basename.\n"
    "If you are moving the file, delete {moved_from} in this change.\n"
    "If the file you wrote is a draft of a new version of {draft_of}, rename the file you "
    "wrote so its name ends -draft before the extension, or at the end of a name that has "
    "none; tell whoever expects the old path the new one; and leave {draft_of} as it is.\n"
    "If both files are meant to exist and the file you wrote is not a draft, rename the file "
    "you wrote following the rules in docs/nedschorus-wiki/nedschorus-how-to-choose-a-name-for-files-code-and-"
    "glossary-terms.md, and update what you have already written to point at the new name.\n"
    "If you wrote the file by mistake, delete the file you wrote."
)


def collision_warning_line(relative_path: PurePath, others) -> str:
    """Return the collision warning and instructions shown to the agent."""
    return COLLISION_WARNING_TEMPLATE.format(
        path=relative_path, name=relative_path.name, already=", ".join(others),
        moved_from=others[0] if len(others) == 1 else "the file you moved from",
        draft_of=others[0] if len(others) == 1 else "one of those files")


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

    try:
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
    except git_machine_readable_output.GitCommandFailed as failure:
        print(git_failure_text(failure, file_path), file=sys.stderr)
        return 1
    if not others:
        return 0

    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PostToolUse",
        "additionalContext": collision_warning_line(relative_path, others),
    }}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
