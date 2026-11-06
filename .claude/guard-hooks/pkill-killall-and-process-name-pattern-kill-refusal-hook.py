#!/usr/bin/env python3
"""Refuse pkill, killall, and kill given process ids that a name pattern found.

Every agent on a machine runs as the same user, so a process name pattern
matches other agents' processes as well as one's own: a pattern that names a
program, such as run-all-test-suites.py, or the full command line of one's own
run, also matches every identical run another agent started.

Refused: killall in any form; pkill, except as below; kill with an argument
whose command substitution runs pgrep, pidof or ps, as in kill $(pgrep -f x);
and kill run by xargs in a pipeline whose other stage runs pgrep, pidof or ps,
as in pgrep -f x | xargs kill. A kill naming its process ids, or a variable or
file holding them, as in kill 1234 or kill "$pid", is allowed, and so is
kill -0, which sends no signal and only tests whether a process exists, as
wait loops do: until ! kill -0 $(pgrep -f x | head -1); do sleep 5; done.

pkill -P <process id>, which signals the children of one process and matches
no name, is allowed when every other argument is a signal, as in -TERM, -9,
--signal TERM, or one of -f, -x, -i, -e, -n, -o, which give no pattern of
their own and so match nothing more; pkill -f -P 1234 is therefore allowed.
Any other argument keeps the refusal: a name pattern, as in pkill -P 4321 -f
worker; -v, which would signal every process except those children; and
any other selector, such as -u. Refused too: a -P value whose command
substitution runs pgrep, pidof or ps, as in pkill -P $(pgrep -f worker), and
pkill run by xargs, whose added arguments cannot be read.

Detection is through the shared shell module on tree-sitter-bash, on every
simple command: the program is found after environment assignments and
wrappers such as sudo, timeout and xargs, so a pkill inside a quoted argument
or after echo is text and is allowed. The command string of bash, sh or zsh
-c, and the remote command of ssh, are read and checked the same way, nested
ones included. Not seen: a pid list read in a loop, as in
for p in $(pgrep x); do kill $p; done; a heredoc fed to a shell or to ssh;
and commands run by eval or a script file.
"""

# Deferred annotations let the hook load on the Mac's system Python 3.9.
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_shell_reader_spec = importlib.util.spec_from_file_location(
    "shell_command_tree_sitter_bash_reader_common",
    Path(__file__).resolve().parents[2] / "nc-systems" / "general-tools"
    / "shell-command-tree-sitter-bash-reader-common.py")
shell_reader = importlib.util.module_from_spec(_shell_reader_spec)
_shell_reader_spec.loader.exec_module(shell_reader)
is_program = shell_reader.is_program

NAME_PATTERN_KILL_PROGRAMS = ("pkill", "killall")
PKILL_PARENT_OPTIONS = ("-P", "--parent")
# Options that add no pattern and select no more processes than -P alone does.
PKILL_FLAGS_SELECTING_NO_MORE = frozenset("fxieno")
PKILL_LONG_FLAGS_SELECTING_NO_MORE = frozenset(
    ("--full", "--exact", "--ignore-case", "--echo", "--newest", "--oldest"))
PROCESS_ID_LISTING_PROGRAMS = ("pgrep", "pidof", "ps")

REFUSAL_TEMPLATE = (
    "Refused on purpose: `{what}` signals every process a name pattern matches. "
    "Every agent on this machine runs as the same user, so the pattern also matches "
    "other agents' processes, such as their test runs, and the signal ends their work too.\n"
    "If the process is a background command you started with the Bash tool, stop it "
    "with the TaskStop tool and its task id.\n"
    "If you started the process yourself in another way, kill it by the process id you "
    "recorded when you started it, as in: kill 1234"
)


def program_and_arguments(words):
    """Return (program, arguments, run by xargs) for a simple command, or None."""
    index, receives_standard_input = shell_reader.simple_command_program_index_skipping_wrappers(words)
    if index is None:
        return None
    return words[index], words[index + 1:], not receives_standard_input


def runs_process_id_listing(words):
    found = program_and_arguments(list(words))
    return found is not None and any(is_program(found[0], name) for name in PROCESS_ID_LISTING_PROGRAMS)


def substitution_lists_process_ids(word):
    """Return whether a word's command substitution runs pgrep, pidof or ps."""
    if "$(" not in word and "`" not in word:
        return False
    return any(runs_process_id_listing(inner) for inner in shell_reader.simple_commands(word))


def pipeline_stage_key(child_shell):
    """Return (enclosing shells, pipeline start) of a command's innermost pipeline stage, or None."""
    for position in range(len(child_shell) - 1, -1, -1):
        shell = child_shell[position]
        if shell.kind == shell_reader.PIPELINE_STAGE:
            return tuple(child_shell[:position]), shell.shell_pipeline_first_stage_byte_offset
    return None


def in_pipeline(key, child_shell):
    enclosing, start = key
    position = len(enclosing)
    return (tuple(child_shell[:position]) == enclosing and len(child_shell) > position
            and child_shell[position].kind == shell_reader.PIPELINE_STAGE
            and child_shell[position].shell_pipeline_first_stage_byte_offset == start)


def sends_signal_zero(arguments):
    """Return whether kill's arguments name signal 0, which only tests that a process exists."""
    return bool(arguments) and (arguments[0] == "-0"
                                or (arguments[0] in ("-s", "-n") and arguments[1:2] == ["0"]))


def is_signal_option(argument):
    """Return whether an argument is pkill's -SIGNAL form, as in -9, -TERM or -SIGUSR1."""
    name = argument[1:]
    return (argument.startswith("-") and not argument.startswith("--")
            and (name.isdigit() or (len(name) > 1 and name.isalnum() and name.isupper())))


def pkill_selects_only_children_of_a_process_id(arguments):
    """Return whether pkill's arguments are -P with a process id and nothing that adds a match."""
    parent_given = False
    index = 0
    while index < len(arguments):
        argument = arguments[index]
        value = None
        if argument in PKILL_PARENT_OPTIONS or argument == "--signal":
            if index + 1 >= len(arguments):
                return False
            value = arguments[index + 1]
            index += 1
        elif argument.startswith("--parent=") or argument.startswith("--signal="):
            value = argument.split("=", 1)[1]
        elif argument.startswith("-P"):
            value = argument[2:]
        elif is_signal_option(argument) or argument in PKILL_LONG_FLAGS_SELECTING_NO_MORE:
            pass
        elif (argument.startswith("-") and not argument.startswith("--") and len(argument) > 1
              and set(argument[1:]) <= PKILL_FLAGS_SELECTING_NO_MORE):
            pass
        else:
            return False
        if value is not None and substitution_lists_process_ids(value):
            return False
        if argument in PKILL_PARENT_OPTIONS or argument.startswith(("-P", "--parent=")):
            parent_given = True
        index += 1
    return parent_given


def nested_command_string(program, arguments):
    if is_program(program, "ssh"):
        return shell_reader.ssh_remote_command(arguments)
    if any(is_program(program, runner) for runner in shell_reader.SHELL_STRING_RUNNERS):
        return shell_reader.shell_command_string(arguments)
    return None


def refusal_for(command):
    commands = shell_reader.simple_commands(command)
    for words in commands:
        found = program_and_arguments(list(words))
        if found is None:
            continue
        program, arguments, run_by_xargs = found
        inner = nested_command_string(program, arguments)
        if inner is not None:
            reason = refusal_for(inner)
            if reason:
                return reason
        if (is_program(program, "pkill") and not run_by_xargs
                and pkill_selects_only_children_of_a_process_id(arguments)):
            continue
        for name in NAME_PATTERN_KILL_PROGRAMS:
            if is_program(program, name):
                return REFUSAL_TEMPLATE.format(what=name)
        if not is_program(program, "kill") or sends_signal_zero(arguments):
            continue
        if any(substitution_lists_process_ids(word) for word in arguments):
            return REFUSAL_TEMPLATE.format(what="kill $(pgrep ...)")
        key = pipeline_stage_key(words.child_shell)
        if run_by_xargs and key is not None and any(
                other is not words and in_pipeline(key, other.child_shell)
                and runs_process_id_listing(other) for other in commands):
            return REFUSAL_TEMPLATE.format(what="pgrep ... | xargs kill")
    return None


PARSER_UNAVAILABLE_NEXT_STEP_LINES = (
    "If the command ran pkill, killall, or kill on process ids found by name, tell the user which "
    "command ran, since it may have ended other agents' processes.")


def main(stdin=sys.stdin):
    try:
        payload = json.load(stdin)
    except ValueError:
        return 0
    if not isinstance(payload, dict) or payload.get("tool_name") != "Bash":
        return 0
    command = (payload.get("tool_input") or {}).get("command")
    if not isinstance(command, str):
        return 0
    try:
        reason = refusal_for(command)
    except shell_reader.ShellParserUnavailable as error:
        print(shell_reader.parser_unavailable_hook_output(
            "The pkill and name-pattern kill guard", error, PARSER_UNAVAILABLE_NEXT_STEP_LINES))
        return 0
    if reason:
        deny(reason)
    return 0


def deny(reason):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }}))


if __name__ == "__main__":
    sys.exit(main())
