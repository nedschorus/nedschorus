#!/usr/bin/env python3
"""Warn after an Edit or Write when the written file shares another tracked file's name."""
# Move checks search by file name, so distinct tracked files need distinct names.

import importlib.util
import json
import os
import shlex
import sys
from pathlib import Path, PurePath

_git_machine_readable_output_spec = importlib.util.spec_from_file_location(
    "git_machine_readable_output_runner_and_parser_common",
    Path(__file__).resolve().parents[1] / "nc-systems" / "general-tools"
    / "git-machine-readable-output-runner-and-parser-common.py")
git_machine_readable_output = importlib.util.module_from_spec(_git_machine_readable_output_spec)
_git_machine_readable_output_spec.loader.exec_module(git_machine_readable_output)

_next_step_lines_spec = importlib.util.spec_from_file_location(
    "failed_command_agent_facing_message_rerun_once_then_stop_and_report_lines_common",
    Path(__file__).resolve().parents[1] / "nc-systems" / "general-tools"
    / "failed-command-agent-facing-message-rerun-once-then-stop-and-report-lines-common.py")
next_step_lines = importlib.util.module_from_spec(_next_step_lines_spec)
_next_step_lines_spec.loader.exec_module(next_step_lines)

# These names are identified by their folders; SKILL.md and README.md are required by their consumers.
EXEMPT_FILE_NAMES = frozenset({"skill.md", "readme.md", ".gitkeep"})

# A hook runs on every edit; bounded git calls keep a hung read from hanging the agent's turn.
GIT_CALL_TIMEOUT_SECONDS = 10

GIT_FAILURE_TEMPLATE = (
    "file-name-collision-warning: git {command} failed ({outcome}), so {path} was not checked "
    "for a name another tracked file has.\n"
    "A later run of this hook checks only the file that run's Write or Edit touched, so check "
    "{path} by running the next line's command: if git's error above names a lock file, first wait "
    "one minute, and do not delete the lock file; otherwise run the command now. The command "
    "prints nothing if the name is free. Otherwise it prints JSON whose "
    "hookSpecificOutput.additionalContext field holds one of two texts: when another tracked file "
    "has the name, this hook's warning, whose instructions you follow; or, when git fails again, a "
    "git-failure message like this one, and the line here that begins \"If a line starting\" says "
    "what to do then.\n"
    "{rerun}\n"
    + next_step_lines.hook_agent_instruction_if_git_failure_recurs_tell_user_both_outputs_line(
        "when you run that command", "file-name-collision-warning:")
)


def shell_command_that_runs_this_hook_on_one_file_as_claude_code_would(working_directory,
                                                                         file_path) -> str:
    """Return a shell command that runs this hook on file_path as Claude Code would."""
    payload = json.dumps({"cwd": str(working_directory), "tool_input": {"file_path": file_path}})
    return f"printf '%s\\n' {shlex.quote(payload)} | python3 {shlex.quote(str(Path(__file__).resolve()))}"


def git_output(arguments, cwd: Path, accepted_exit_codes=(0,)) -> str:
    """Return git stdout; raises GitCommandFailed when git fails."""
    return os.fsdecode(git_machine_readable_output.run_git(
        cwd, arguments, accepted_exit_codes=accepted_exit_codes,
        timeout_seconds=GIT_CALL_TIMEOUT_SECONDS))


def git_failure_text(failure, path, working_directory) -> str:
    """Return the agent's text for a git failure; its first line carries the cause."""
    if failure.returncode is None:
        outcome = failure.stderr
    else:
        outcome = f"exit {failure.returncode}: {' '.join(failure.stderr.split()) or 'no error text'}"
    rerun = shell_command_that_runs_this_hook_on_one_file_as_claude_code_would(working_directory, path)
    return GIT_FAILURE_TEMPLATE.format(command=" ".join(failure.arguments), outcome=outcome, path=path,
                                       rerun=rerun)


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
        print_for_agent(git_failure_text(failure, file_path, working_directory))
        return 0
    if not others:
        return 0

    print_for_agent(collision_warning_line(relative_path, others))
    return 0


def print_for_agent(text) -> None:
    """Print text as additionalContext, which the agent reads next when the hook exits 0.

    A git failure takes this channel too: Claude Code records the stderr of a
    PostToolUse exit 1 in the transcript but never passes it to the model.
    """
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PostToolUse",
        "additionalContext": text,
    }}, ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(main())
