#!/usr/bin/env python3
"""Find the checkout an edited file is in, and ask git whether git would track the file.

The hooks that check a Markdown file after an Edit or Write share these helpers,
so a git failure is reported the same way in each: every function here that
runs git raises GitCommandFailed, the class the project's git runner module
defines, when git fails, cannot start or times out, and never reads the
failure as "not tracked". The caller reports the exception as its own failure.

Load it by path, under the snake_case form of its file name:

    spec = importlib.util.spec_from_file_location(
        "edited_file_path_within_checkout_root_and_git_check_ignore_common", <path>)
"""

# Deferred annotations let the module load on the Mac's system Python 3.9.
from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

_git_machine_readable_output_spec = importlib.util.spec_from_file_location(
    "git_machine_readable_output_runner_and_parser_common",
    Path(__file__).resolve().with_name("git-machine-readable-output-runner-and-parser-common.py"))
_git_machine_readable_output = importlib.util.module_from_spec(_git_machine_readable_output_spec)
_git_machine_readable_output_spec.loader.exec_module(_git_machine_readable_output)
GitCommandFailed = _git_machine_readable_output.GitCommandFailed

# A hook runs on every edit; a bounded git call keeps a hung git from hanging the agent's turn.
GIT_TIMEOUT_SECONDS = 10


def _run_git(arguments, working_directory: Path):
    """Run git; raise GitCommandFailed when git cannot start or times out."""
    # Not the runner module's run_git: that returns only stdout, and the callers
    # here need git's exit code.
    try:
        return subprocess.run(["git", *arguments], cwd=str(working_directory),
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=GIT_TIMEOUT_SECONDS, check=False)
    except subprocess.TimeoutExpired as error:
        raise GitCommandFailed(arguments, working_directory, None,
                               f"did not finish within {GIT_TIMEOUT_SECONDS} s") from error
    except OSError as error:
        raise GitCommandFailed(arguments, working_directory, None,
                               f"could not start git: {error}") from error


def enclosing_checkout_root(directory: Path):
    """Return the nearest checkout root at or above directory, or None."""
    for candidate in (directory, *directory.parents):
        git_marker = candidate / ".git"
        try:
            if git_marker.is_file() or (git_marker / "HEAD").is_file():
                return candidate
        except OSError:
            continue
    return None


def checkout_relative_path(file_path: str, working_directory: Path):
    """Return (checkout root, Git-relative path), or None outside the session checkout."""
    # Resolve both paths so macOS /tmp and /private/tmp compare equal.
    try:
        root = enclosing_checkout_root(working_directory.resolve())
        if root is None:
            return None
        return root, Path(file_path).resolve().relative_to(root).as_posix()
    except (ValueError, OSError, RuntimeError):
        return None


def git_would_track(root: Path, relative_path: str) -> bool:
    """Return whether git would track relative_path; raise GitCommandFailed when git cannot say."""
    # check-ignore exits 0 for ignored, 1 for trackable, and 128 for failure; tracked files are never ignored.
    arguments = ["check-ignore", "-q", "--", relative_path]
    completed = _run_git(arguments, root)
    if completed.returncode == 1:
        return True
    if completed.returncode == 0:
        return False
    # Only git's first stderr line: each hook reports a failure in one line.
    detail = completed.stderr.strip().splitlines()
    raise GitCommandFailed(arguments, root, completed.returncode, detail[0] if detail else "")


def file_lines_at_head_unless_git_ignores_file(root: Path, relative_path: str):
    """Return the file's lines at HEAD, each with trailing whitespace removed, as a set.

    Return an empty set when HEAD lacks the file and git would track it, and None
    when git ignores it. Raise GitCommandFailed when git cannot say which."""
    committed = _run_git(["show", "HEAD:" + relative_path], root)
    if committed.returncode == 0:
        return set(line.rstrip() for line in committed.stdout.split("\n"))
    if git_would_track(root, relative_path):
        return set()
    return None
