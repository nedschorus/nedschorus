#!/usr/bin/env python3
"""Refuse a hand-typed `codex exec` and point at scripts/run-codex-task-from-brief.py.

A `codex exec` typed into a Bash command leaves stdin open, so started from a
background shell it waits for input forever, and nothing stops it. The
program closes stdin and enforces a deadline. Programs that launch Codex
themselves never pass through this hook.

Commands are read with the shared shell reader on tree-sitter-bash, so
`codex exec` inside a quoted argument, such as a grep pattern, or inside a
heredoc body, is text and is allowed, and one inside a command substitution
is seen. The command string of `bash -c`, `sh -c` or `zsh -c`, the words
of `eval`, the remote command of `ssh`, and a heredoc fed to a shell or to
ssh that runs it as commands, are read again with the same reader. A command
built at run time from a variable, or kept in a script file, is not seen.
"""

# Deferred annotations let the hook load on the Mac's system Python 3.9.
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

_shell_reader_spec = importlib.util.spec_from_file_location(
    "shell_command_tree_sitter_bash_reader_common",
    Path(__file__).resolve().parent.parent / "nc-systems" / "general-tools"
    / "shell-command-tree-sitter-bash-reader-common.py")
shell_reader = importlib.util.module_from_spec(_shell_reader_spec)
_shell_reader_spec.loader.exec_module(shell_reader)
is_program = shell_reader.is_program

CODEX_EXEC_SUBCOMMANDS = ("exec", "e")
HELP_WORDS = {"-h", "--help", "help"}
# Programs that run the command after them, each with its options that take a value.
COMMAND_RUNNING_PREFIX_VALUE_OPTIONS = {
    "env": {"-u", "-C", "-S", "-P", "--unset", "--chdir", "--split-string"},
    "command": set(), "nohup": set(), "time": set(), "exec": {"-a"},
    "nice": {"-n"},
    "timeout": {"-s", "-k", "--signal", "--kill-after"},
    "caffeinate": {"-t", "-w"},
    "sandbox-exec": {"-f", "-p", "-D"},
    "setsid": set(),
}
SHELL_STRING_RUNNERS = ("bash", "sh", "zsh")
# bash's -o and -O, and their + forms, take an option name as the next word.
SHELL_VALUE_OPTIONS = {"-o", "+o", "-O", "+O"}
# ssh's getopt string is "1246ab:c:e:fgi:kl:m:no:p:qstvxAB:CD:E:F:GI:J:KL:MNO:P:Q:R:S:TVw:W:XYy": these letters take a value.
SSH_VALUE_LETTERS = "bceilmopBDEFIJLOPQRSwW"
ENVIRONMENT_ASSIGNMENT_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")

USAGE_LINE = (
    "scripts/run-codex-task-from-brief.py -C <checkout> --brief <file> -o <report> "
    "[--sandbox read-only|workspace-write] [-m <model>] [--effort <effort>] "
    "[--network] [--writable-root <folder>]... [--outside-git-checkout] "
    "[--web-search] [--deadline-minutes <minutes>] [--run-log <file>]")

REFUSAL = (
    "Refused: a hand-typed `codex exec`. Typed into a shell, `codex exec` keeps "
    "stdin open and, started in the background, waits for input forever with "
    "nothing to stop it.\n"
    "Write the prompt to a file and run the task with:\n"
    f"  {USAGE_LINE}\n"
    "In place of Codex's own options: --sandbox or -s becomes --sandbox; "
    "network access becomes --network; --add-dir or writable_roots becomes "
    "--writable-root, once per folder; --skip-git-repo-check becomes "
    "--outside-git-checkout; --search or web_search becomes --web-search; "
    "-c model_reasoning_effort becomes --effort.\n"
    "That program closes stdin, logs Codex's output, stops Codex at the "
    "deadline, and says what failed when Codex writes no report."
)


def program_index_after_prefixes(words):
    """Return the index of the word the shell runs, past assignments and prefixes."""
    index = 0
    while index < len(words):
        word = words[index]
        if ENVIRONMENT_ASSIGNMENT_PATTERN.match(word):
            index += 1
        elif any(is_program(word, prefix) for prefix in COMMAND_RUNNING_PREFIX_VALUE_OPTIONS):
            value_options = next(options for prefix, options
                                 in COMMAND_RUNNING_PREFIX_VALUE_OPTIONS.items()
                                 if is_program(word, prefix))
            index += 1
            # Skip the prefix's own options, their values, and a timeout's duration.
            while index < len(words) and (words[index].startswith("-")
                                          or re.match(r"^\d", words[index])):
                index += 2 if words[index] in value_options else 1
        else:
            return index
    return None


def shell_command_string(arguments):
    """Return the command string of `bash -c <string>`, or None without -c."""
    reads_string = False
    index = 0
    while index < len(arguments):
        word = arguments[index]
        if word == "--" or not word.startswith(("-", "+")):
            return word if reads_string else None
        if word in SHELL_VALUE_OPTIONS:
            index += 1  # the value is the next word
        elif not word.startswith("--") and "c" in word[1:]:
            reads_string = True
        index += 1
    return None


def shell_reads_commands_from_stdin(arguments) -> bool:
    """Return whether bash, sh or zsh with these arguments runs the commands on its stdin."""
    index = 0
    while index < len(arguments):
        word = arguments[index]
        if word == "--" or not word.startswith(("-", "+")):
            return False  # a script file, or with -c a command string
        if word in SHELL_VALUE_OPTIONS:
            index += 1
        elif not word.startswith("--") and "c" in word[1:]:
            return False
        index += 1
    return True


def ssh_remote_command(arguments):
    """Return the command ssh runs on the remote machine, or None when there is none."""
    index = 0
    while index < len(arguments):
        word = arguments[index]
        if word == "--":
            index += 1
            break
        if not word.startswith("-") or word == "-":
            break
        letters = word[1:]
        for position, letter in enumerate(letters):
            if letter in SSH_VALUE_LETTERS:
                if position == len(letters) - 1:
                    index += 1  # the value is the next word
                break
        index += 1
    remote = arguments[index + 1:]  # past the destination
    return " ".join(remote) if remote else None


def is_shell_reading_stdin(words) -> bool:
    index = program_index_after_prefixes(words)
    return (index is not None
            and any(is_program(words[index], runner) for runner in SHELL_STRING_RUNNERS)
            and shell_reads_commands_from_stdin(words[index + 1:]))


def runs_codex_exec(words, heredocs=()) -> bool:
    """Return whether one simple command, with the heredocs fed to it, runs codex exec."""
    index = program_index_after_prefixes(words)
    if index is None:
        return False
    program, arguments = words[index], words[index + 1:]
    if is_program(program, "codex"):
        # Codex's global options take values, so any exec word counts rather than the first operand.
        return (any(word in CODEX_EXEC_SUBCOMMANDS for word in arguments)
                and not HELP_WORDS & set(arguments))
    if any(is_program(program, runner) for runner in SHELL_STRING_RUNNERS):
        inner = shell_command_string(arguments)
        stdin_is_commands = shell_reads_commands_from_stdin(arguments)
    elif program == "eval":
        inner, stdin_is_commands = " ".join(arguments), False
    elif is_program(program, "ssh"):
        inner = ssh_remote_command(arguments)
        # With no remote command, or a remote shell reading stdin, the remote shell runs ssh's stdin.
        stdin_is_commands = inner is None or any(
            is_shell_reading_stdin(list(remote_words))
            for remote_words in shell_reader.simple_commands(inner))
    else:
        return False
    if inner is not None and command_runs_codex_exec(inner):
        return True
    return stdin_is_commands and any(command_runs_codex_exec(heredoc.body)
                                     for heredoc in heredocs)


def command_runs_codex_exec(command: str) -> bool:
    return any(runs_codex_exec(list(words), words.heredocs)
               for words in shell_reader.simple_commands(command))


def refusal_for_command(command: str):
    return REFUSAL if command_runs_codex_exec(command) else None


def deny(reason):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }}))


def main(stdin=sys.stdin) -> int:
    try:
        payload = json.load(stdin)
    except (json.JSONDecodeError, ValueError):
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
            "The hand-typed codex exec guard", error))
        return 0
    if refusal:
        deny(refusal)
    return 0


if __name__ == "__main__":
    sys.exit(main())
