#!/usr/bin/env python3
"""Refuse a hand-typed `git worktree add` and point at scripts/agent-seat-worktree-create-with-owner-file.py.

A worktree an agent makes by hand can be left with no owner file, which
scripts/clean-worktrees.py needs before it removes a worktree, so such a
worktree stays on disk for good. The creator makes the worktree under the
reference-checkout's .claude/worktrees/ and writes its owner file at once.
Programs that make their own worktrees never pass through this hook, which
sees only the Bash commands an agent types.

What it reads: every simple command, through the shared shell reader on
tree-sitter-bash, whose program, after wrappers such as env and timeout, is
git with the subcommand `worktree add`, global options such as -C and -c
before `worktree` included, and the command string of bash, sh or zsh -c,
read the same way. Not read: the remote command of ssh, so an agent-home
made on ned-box over ssh is allowed; commands run by eval or a script file;
and a command built at run time from a variable. `git worktree list`,
`remove`, `prune` and the other subcommands are allowed.

When the shell reader cannot run, the command is let through and the agent
is told so in additionalContext.

The messages follow
docs/nedschorus-wiki/nedschorus-how-to-write-an-agent-facing-message-such-as-a-hook-refusal-or-script-error.md.
"""

# Deferred annotations let the hook load on the Mac's system Python 3.9.
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

_shell_reader_spec = importlib.util.spec_from_file_location(
    "shell_command_tree_sitter_bash_reader_common",
    REPOSITORY_ROOT / "nc-systems" / "general-tools" / "shell-command-tree-sitter-bash-reader-common.py")
shell_reader = importlib.util.module_from_spec(_shell_reader_spec)
_shell_reader_spec.loader.exec_module(shell_reader)
is_program = shell_reader.is_program

CREATOR_PATH = REPOSITORY_ROOT / "scripts" / "agent-seat-worktree-create-with-owner-file.py"

GIT_GLOBAL_VALUE_FLAGS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--config-env",
                          "--exec-path"}

REFUSAL_MESSAGE = (
    "Refused on purpose: a hand-typed `git worktree add`. Agents make worktrees only with "
    f"{CREATOR_PATH}, which makes the worktree in the reference-checkout's .claude/worktrees/ "
    "and writes its owner file at once, naming your agent-seat; scripts/clean-worktrees.py "
    "never removes a worktree with no owner file, so one made by hand can stay on disk for "
    "good.\n"
    "For a branch, new or existing, in this clone or only on origin, run: "
    f"python3 {CREATOR_PATH} <branch name>\n"
    "  It fetches origin first; a new branch starts at origin/main.\n"
    "For a new branch that starts at another commit, run: "
    f"python3 {CREATOR_PATH} <branch name> --base <commit>\n"
    "For a worktree on no branch, detached at a commit, run: "
    f"python3 {CREATOR_PATH} --detach <directory name> <commit>\n"
    "  <directory name> is a name for its directory inside .claude/worktrees/, such as "
    "pr-123-head.\n"
    "The program prints the new worktree's path; it does not change your directory, so cd "
    "to that path, or pass it to git -C, for your git and test commands.\n"
    "If the program refuses or fails, do what its message says.\n"
    "If you need a worktree somewhere other than .claude/worktrees/, which the program cannot "
    "make, tell the user, or, if you are a subagent, the agent that dispatched you, where you "
    "need it and why.\n"
    "From now on, make every worktree with that program.")

PARSER_UNAVAILABLE_NEXT_STEP_LINES = (
    "If the command made a git worktree, it may have no owner file: run "
    "`python3 scripts/worktree-owner-file-read-and-write.py show --worktree <its path>`, and if "
    "it prints no owner file, run "
    "`python3 scripts/worktree-owner-file-read-and-write.py write --agent-seat <your agent-seat> "
    "--worktree <its path>`.\n"
    f"Make the next worktree with python3 {CREATOR_PATH} <branch name>.")


def is_git_worktree_add(words):
    """True for `git [global options] worktree add ...`, after wrappers such as env and timeout."""
    index, _ = shell_reader.simple_command_program_index_skipping_wrappers(words)
    if index is None or not is_program(words[index], "git"):
        return False
    index += 1
    while index < len(words) and words[index].startswith("-"):
        index += 2 if words[index] in GIT_GLOBAL_VALUE_FLAGS else 1
    return list(words[index:index + 2]) == ["worktree", "add"]


def command_runs_git_worktree_add(command):
    """True when the command, or the command string of a bash, sh or zsh -c in it, runs `git worktree add`."""
    for words in shell_reader.simple_commands(command):
        if is_git_worktree_add(words):
            return True
        index, _ = shell_reader.simple_command_program_index_skipping_wrappers(words)
        if index is not None and any(is_program(words[index], runner)
                                     for runner in shell_reader.SHELL_STRING_RUNNERS):
            inner = shell_reader.shell_command_string(words[index + 1:])
            if inner is not None and command_runs_git_worktree_add(inner):
                return True
    return False


def refusal_for_command(command):
    return REFUSAL_MESSAGE if command_runs_git_worktree_add(command) else None


def main(stdin=sys.stdin):
    try:
        payload = json.load(stdin)
    except ValueError:
        return 0
    if not isinstance(payload, dict) or payload.get("tool_name") != "Bash":
        return 0
    command = (payload.get("tool_input") or {}).get("command") or ""
    if not isinstance(command, str) or not command:
        return 0
    try:
        refusal = refusal_for_command(command)
    except shell_reader.ShellParserUnavailable as error:
        print(shell_reader.parser_unavailable_hook_output(
            "The hand-typed git worktree add guard", error, PARSER_UNAVAILABLE_NEXT_STEP_LINES))
        return 0
    if refusal:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": refusal,
        }}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
