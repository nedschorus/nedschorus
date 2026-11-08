#!/usr/bin/env python3
"""Refuse a cold-read-full-run while this agent-session's session-handoff is deferred.

A PreToolUse hook on Bash. A command that runs nc-systems/cold-read/cold-read-grid.py starts
a cold-read-full-run, which outlasts a handoff-deferral. While the agent-session's
handoff-deferred marker file exists, this hook refuses such a command, appends it with its
working directory to the agent-session's file of refused commands, from which the handoff writer
script copies it into the session-handoff, and tells the agent so. A hook running inside a
subagent receives the session id of the agent-session that started the subagent, so a
subagent's command is refused during its agent-session's deferral too.

A command runs the grid when one of its simple commands runs cold-read-grid.py as its program,
or runs a Python interpreter on it as the script, after any wrappers such as env, timeout or
nohup; the command string of bash, sh or zsh -c, and the remote command of ssh, are read the
same way. `--help` or `-h` asks for usage and is let through. Commands are read with the shared
shell reader on tree-sitter-bash, so a grid path inside a quoted argument, a heredoc body, or a
command that only reads the file, such as `sed -n 1,9p cold-read-grid.py`, is not a run. A
command built at run time from a variable, or kept in a script file, is not seen.

Failures: when the shell reader is unavailable during a deferral, or the marker file cannot be
looked up for a command that runs the grid, the command is let through with a message saying it
was not checked and how to stop it and carry it to the successor by hand. When the refused
command cannot be saved, the command is still refused, and the message says it was not saved
and gives the command for the agent to carry by hand.
"""

# Deferred annotations let the hook load on the Mac's system Python 3.9.
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

_shell_reader_spec = importlib.util.spec_from_file_location(
    "shell_command_tree_sitter_bash_reader_common",
    REPOSITORY_ROOT / "nc-systems" / "general-tools" / "shell-command-tree-sitter-bash-reader-common.py")
shell_reader = importlib.util.module_from_spec(_shell_reader_spec)
_shell_reader_spec.loader.exec_module(shell_reader)
is_program = shell_reader.is_program

_deferred_marker_file_spec = importlib.util.spec_from_file_location(
    "handoff_deferred_marker_and_refused_commands_files_common",
    REPOSITORY_ROOT / "nc-systems" / "handoff" / "handoff-deferred-marker-and-refused-commands-files-common.py")
handoff_deferred_marker_and_refused_commands_files_common = importlib.util.module_from_spec(_deferred_marker_file_spec)
_deferred_marker_file_spec.loader.exec_module(handoff_deferred_marker_and_refused_commands_files_common)

COLD_READ_GRID_PROGRAM = "cold-read-grid.py"
PYTHON_INTERPRETER_PATTERN = re.compile(r"(?:.*/)?python(?:\d+(?:\.\d+)?)?$")
# Python's options that take the next word as their value; -c, -m and - (the script read from
# stdin) end the search for a script, since every later word is an argument to it.
PYTHON_VALUE_OPTIONS = {"-W", "-X", "--check-hash-based-pycs"}
PYTHON_NON_SCRIPT_OPTIONS = {"-c", "-m", "-"}
USAGE_OPTIONS = {"--help", "-h"}

COLD_READ_FULL_RUN_REFUSED_AND_SAVED_REASON = (
    "This cold-read-full-run would outlast the handoff-deferral, so this hook refused it and "
    "saved the command for your successor, who runs it after the session-handoff. The handoff "
    "writer adds the command to your session-handoff, so you need not. Report it to whoever "
    "asked for it as put off, not failed."
)

COLD_READ_FULL_RUN_REFUSED_NOT_SAVED_REASON = (
    "Refused on purpose: this cold-read-full-run would outlast the handoff-deferral, so this "
    "hook refused it, but it could not save the command for your successor ({problem}).\n"
    "Add a task to your task list (the TaskCreate tool) for your successor, holding the "
    "directory {working_directory} and the command between the two lines below.\n"
    "--- command ---\n"
    "{command}\n"
    "--- end of command ---\n"
    "Report the cold-read-full-run to whoever asked for it, the user or the agent that "
    "dispatched you, as put off, not failed."
)

# These two let the command run, so stopping it is the only way left to keep it from being cut off.
MARKER_LOOKUP_FAILED_CONTEXT = (
    "The hook .claude/guard-hooks/handoff-deferral-cold-read-full-run-launch-refusal-hook.py let "
    "this cold-read-full-run start unchecked: it could not look up this agent-session's "
    "handoff-deferred marker file ({problem}), so it cannot tell whether a handoff-deferral is "
    "on.\n"
    "If a system message has told you the session-handoff is deferred and this command runs in "
    "the background: stop it with the TaskStop tool, add a task to your task list (the "
    "TaskCreate tool) for your successor holding the directory {working_directory} and the "
    "command {command_json}, and report the cold-read-full-run to whoever asked for it, the user "
    "or the agent that dispatched you, as put off, not failed.\n"
    "If it ran in the foreground, or no deferral was announced, nothing for you to do."
)

PARSER_UNAVAILABLE_NEXT_STEP_TEMPLATE = (
    "This agent-session's session-handoff is deferred, and this command names "
    "nc-systems/cold-read/cold-read-grid.py.\n"
    "If the command starts a cold-read-full-run in the background, it would outlast the "
    "deferral: stop it with the TaskStop tool, add a task to your task list (the TaskCreate "
    "tool) for your successor holding the directory {working_directory} and the command "
    "{command_json}, and report the cold-read-full-run to whoever asked for it, the user or the "
    "agent that dispatched you, as put off, not failed.\n"
    "If it only reads that file, or ran in the foreground, nothing for you to do.")


def python_runs_cold_read_grid(arguments) -> bool:
    index = 0
    while index < len(arguments):
        word = arguments[index]
        if word in PYTHON_NON_SCRIPT_OPTIONS:
            return False
        if word in PYTHON_VALUE_OPTIONS:
            index += 2
            continue
        if word.startswith("-"):
            index += 1
            continue
        return is_program(word, COLD_READ_GRID_PROGRAM) and not USAGE_OPTIONS & set(arguments[index + 1:])
    return False


def simple_command_runs_cold_read_grid(words) -> bool:
    index, _ = shell_reader.simple_command_program_index_skipping_wrappers(words)
    if index is None:
        return False
    program, arguments = words[index], words[index + 1:]
    if is_program(program, COLD_READ_GRID_PROGRAM):
        return not USAGE_OPTIONS & set(arguments)
    if PYTHON_INTERPRETER_PATTERN.match(program):
        return python_runs_cold_read_grid(arguments)
    return False


def command_string_run_by(words):
    """Return the command string bash -c or ssh runs, or None."""
    index, _ = shell_reader.simple_command_program_index_skipping_wrappers(words)
    if index is None:
        return None
    program, arguments = words[index], words[index + 1:]
    if is_program(program, "ssh"):
        return shell_reader.ssh_remote_command(arguments)
    if any(is_program(program, runner) for runner in shell_reader.SHELL_STRING_RUNNERS):
        return shell_reader.shell_command_string(arguments)
    return None


def command_runs_cold_read_grid_script(command: str) -> bool:
    for words in shell_reader.simple_commands(command):
        words = list(words)
        if simple_command_runs_cold_read_grid(words):
            return True
        inner = command_string_run_by(words)
        if inner is not None and command_runs_cold_read_grid_script(inner):
            return True
    return False


def deny(reason):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }}))


def add_context(text):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "additionalContext": text,
    }}))


def main(stdin=sys.stdin, handoff_directory=None) -> int:
    try:
        payload = json.load(stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(payload, dict) or payload.get("tool_name") != "Bash":
        return 0
    command = (payload.get("tool_input") or {}).get("command")
    session_id = payload.get("session_id")
    if not isinstance(command, str) or not isinstance(session_id, str) or not session_id:
        return 0
    # Most commands never name the grid; skip the parse and the marker lookup for them.
    if COLD_READ_GRID_PROGRAM not in command:
        return 0
    working_directory = str(payload.get("cwd") or "")
    filled = {"working_directory": working_directory or "not given", "command_json": json.dumps(command)}
    handoff_directory = handoff_directory or handoff_deferred_marker_and_refused_commands_files_common.default_handoff_directory()
    try:
        runs_grid = command_runs_cold_read_grid_script(command)
    except shell_reader.ShellParserUnavailable as error:
        # Unparsed, the command may start a grid; that matters only during a deferral.
        try:
            deferral_is_on = handoff_deferred_marker_and_refused_commands_files_common.handoff_deferred_marker_exists(handoff_directory, session_id)
        except OSError:
            deferral_is_on = True
        if deferral_is_on:
            print(shell_reader.parser_unavailable_hook_output(
                "The handoff-deferral cold-read-full-run launch hook", error,
                PARSER_UNAVAILABLE_NEXT_STEP_TEMPLATE.format(**filled)))
        return 0
    if not runs_grid:
        return 0
    try:
        if not handoff_deferred_marker_and_refused_commands_files_common.handoff_deferred_marker_exists(handoff_directory, session_id):
            return 0
    except OSError as problem:
        add_context(MARKER_LOOKUP_FAILED_CONTEXT.format(problem=problem, **filled))
        return 0
    try:
        handoff_deferred_marker_and_refused_commands_files_common.cold_read_full_run_command_refused_during_handoff_deferral_append(
            handoff_directory, session_id, command, working_directory)
    except OSError as problem:
        deny(COLD_READ_FULL_RUN_REFUSED_NOT_SAVED_REASON.format(
            problem=problem, working_directory=working_directory or "not given", command=command))
        return 0
    deny(COLD_READ_FULL_RUN_REFUSED_AND_SAVED_REASON)
    return 0


if __name__ == "__main__":
    sys.exit(main())
