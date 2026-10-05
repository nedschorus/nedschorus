#!/usr/bin/env python3
"""Refuse a hand-typed `codex exec` and point at scripts/run-codex-task-from-brief.py.

A `codex exec` typed into a Bash command leaves stdin open, so started from a
background shell it waits for input forever, and nothing stops it. The
program closes stdin and enforces a deadline. Programs that launch Codex
themselves never pass through this hook.

Commands are read with the shared tokenizer of synthetic-keystroke-guard-hook.py,
so `codex exec` inside a quoted argument, such as a grep pattern, is text and
is allowed. A `bash -c`, `sh -c`, `zsh -c` or `ssh` command whose arguments
contain `codex exec` is refused without parsing those arguments.
"""

import importlib.util
import json
import re
import sys
from pathlib import Path

_keystroke_guard_path = Path(__file__).with_name("synthetic-keystroke-guard-hook.py")
_keystroke_guard_spec = importlib.util.spec_from_file_location(
    "synthetic_keystroke_guard_hook", _keystroke_guard_path)
keystroke_guard = importlib.util.module_from_spec(_keystroke_guard_spec)
_keystroke_guard_spec.loader.exec_module(keystroke_guard)

split_out_heredocs = keystroke_guard.split_out_heredocs
tokenize_simple_commands = keystroke_guard.tokenize_simple_commands
is_program = keystroke_guard.is_program

CODEX_EXEC_SUBCOMMANDS = ("exec", "e")
HELP_WORDS = {"-h", "--help", "help"}
COMMAND_RUNNING_PREFIXES = ("env", "command", "nohup", "nice", "timeout",
                            "time", "exec", "caffeinate")
SHELL_STRING_RUNNERS = ("bash", "sh", "zsh", "ssh")
ENVIRONMENT_ASSIGNMENT_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
CODEX_EXEC_IN_TEXT_PATTERN = re.compile(r"(?:^|[\s;&|(/])codex\s+(?:exec|e)(?:\s|$)")

USAGE_LINE = (
    "scripts/run-codex-task-from-brief.py -C <checkout> --brief <file> -o <report> "
    "[--sandbox read-only|workspace-write] [-m <model>] [--effort <effort>] "
    "[--deadline-minutes <minutes>]")

REFUSAL = (
    "Refused: a hand-typed `codex exec`. Typed into a shell, `codex exec` keeps "
    "stdin open and, started in the background, waits for input forever with "
    "nothing to stop it.\n"
    "Write the prompt to a file and run the task with:\n"
    f"  {USAGE_LINE}\n"
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
        elif any(is_program(word, prefix) for prefix in COMMAND_RUNNING_PREFIXES):
            index += 1
            # Skip the prefix's own options and a timeout's duration.
            while index < len(words) and (words[index].startswith("-")
                                          or re.match(r"^\d", words[index])):
                index += 1
        else:
            return index
    return None


def runs_codex_exec(words) -> bool:
    index = program_index_after_prefixes(words)
    if index is None:
        return False
    if is_program(words[index], "codex"):
        # Codex's global options take values, so any exec word counts rather than the first operand.
        rest = words[index + 1:]
        return (any(word in CODEX_EXEC_SUBCOMMANDS for word in rest)
                and not HELP_WORDS & set(rest))
    if any(is_program(words[index], runner) for runner in SHELL_STRING_RUNNERS):
        return any(CODEX_EXEC_IN_TEXT_PATTERN.search(word)
                   for word in words[index + 1:])
    return False


def refusal_for_command(command: str):
    shell_view, _heredoc_bodies = split_out_heredocs(command)
    if any(runs_codex_exec(words) for words in tokenize_simple_commands(shell_view)):
        return REFUSAL
    return None


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
    refusal = refusal_for_command(command) if command else None
    if refusal:
        deny(refusal)
    return 0


if __name__ == "__main__":
    sys.exit(main())
