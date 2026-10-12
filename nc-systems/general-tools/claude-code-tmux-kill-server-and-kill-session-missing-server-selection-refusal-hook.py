#!/usr/bin/env python3
"""Refuse tmux kill-server and kill-session that name no server with -L or -S.

An agent's shell inherits $TMUX, which points at its agent-seat's own tmux
server; a tmux command naming no server acts on that server, and TMUX_TMPDIR
does not redirect it while $TMUX is set. With $TMUX unset, it acts on the
default server, which holds other sessions. Either way a bare kill can end
agent-seats, their supervisors and every agent under them.

Detection is literal, through the shared tokenizer: env and the other command
prefixes are followed, quoted prose is data, and commands run by ssh, bash -c
or eval are outside this guard's scope. Message guide:
docs/nedschorus-wiki/nedschorus-how-to-write-the-refusal-warning-or-reminder-a-program-hands-an-agent.md
"""

import importlib.util
import json
import os
import re
import shlex
import sys
from pathlib import Path

_keystroke_guard_path = (Path(__file__).resolve().parents[2] / "scripts"
                         / "synthetic-keystroke-guard-hook.py")
_keystroke_guard_spec = importlib.util.spec_from_file_location(
    "synthetic_keystroke_guard_hook", _keystroke_guard_path)
keystroke_guard = importlib.util.module_from_spec(_keystroke_guard_spec)
_keystroke_guard_spec.loader.exec_module(keystroke_guard)

split_out_heredocs = keystroke_guard.split_out_heredocs
tokenize_simple_commands = keystroke_guard.tokenize_simple_commands
is_program = keystroke_guard.is_program

COMMAND_RUNNING_PREFIXES = ("env", "command", "exec", "nohup", "nice", "time",
                            "timeout")
PREFIX_VALUE_OPTIONS = {"-u", "--unset", "-n", "-s", "--signal", "-k",
                        "--kill-after"}
# A word the shell would expand; the tokenizer has dropped its quotes, so the
# hook cannot rebuild the word exactly and gives no suggested command for it.
SHELL_EXPANSION_PATTERN = re.compile(r"[$`*?\[]")
SAFE_SESSION_COMMAND_WORD_PATTERN = re.compile(r"[A-Za-z0-9_.:@%=+-]+")
ENVIRONMENT_ASSIGNMENT_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
REDIRECTION_WORD_PATTERN = re.compile(r"^[0-9]*(?:>>|>&|>|<<<|<>|<)")

# Flags before the tmux command that take a value; -L and -S name the server.
TMUX_GLOBAL_VALUE_FLAGS = {"-f", "-c", "-T"}
SERVER_NAMING_FLAGS = ("-L", "-S")

# tmux accepts any unambiguous prefix of a command name.
KILL_COMMAND_PREFIXES = ("kill-ser", "kill-ses")

REFUSAL_WITH_COMMAND_TEMPLATE = (
    "Refused on purpose: `{kill}` names no tmux server, so tmux acts on the "
    "server in $TMUX, which is the tmux server of the agent-seat you run in "
    "(or, with $TMUX unset, the default server, which holds other sessions). "
    "Killing it ends that agent-seat, its supervisor and every agent under "
    "it, you included. TMUX_TMPDIR does not change which server is meant "
    "while $TMUX is set.\n"
    "To kill the private server whose socket lives under {tmpdir}, run:\n"
    "{command}\n"
    "From now on, name the server in every tmux command you run, with "
    "-S <socket path> or -L <name> right after tmux, from the command that "
    "starts the server to the one that kills it."
)

REFUSAL_WITHOUT_COMMAND_MESSAGE = (
    "Refused on purpose: this tmux kill names no tmux server, so tmux acts on "
    "the server in $TMUX, which is the tmux server of the agent-seat you run "
    "in (or, with $TMUX unset, the default server, which holds other "
    "sessions). Killing it ends that agent-seat, its supervisor and every "
    "agent under it, you included.\n"
    "If you started a tmux server of your own, run the same command with "
    "-S <socket path> or -L <name> right after tmux, naming that server, as "
    "in: tmux -L my-server kill-server\n"
    "If you started no tmux server of your own, there is nothing of yours to "
    "clean up: do not kill one, and you need not tell the user.\n"
    "From now on, name the server in every tmux command you run, with "
    "-S <socket path> or -L <name> right after tmux, from the command that "
    "starts the server to the one that kills it."
)


SESSION_REFUSAL_TEMPLATE = (
    "Refused on purpose: `tmux {command}` names no tmux server, so "
    "tmux looks for {target} on the server in $TMUX, which is the tmux server "
    "of the agent-seat you run in (or, with $TMUX unset, the default server, "
    "which holds other sessions). Killing the wrong session there can end "
    "that agent-seat, its supervisor and every agent under it, you included.\n"
    "If you started {target} on a tmux server of your own, run the command "
    "with that server named, as in: tmux -L <name> {command}\n"
    "If you started {target} with a tmux command that named no server, it is "
    "on your agent-seat's server. Check that it is not your agent-seat's own "
    "session, whose name `tmux display-message -p '#S'` prints, and then run: "
    "tmux -S \"${{TMUX%%,*}}\" {command}\n"
    "From now on, name the server in every tmux command you run, with "
    "-S <socket path> or -L <name> right after tmux, from the command that "
    "starts the server to the one that kills it."
)


def session_target(arguments):
    """Return the -t value of a kill-session invocation, or None."""
    for index, word in enumerate(arguments):
        if word == "-t" and index + 1 < len(arguments):
            return arguments[index + 1]
        if word.startswith("-t") and len(word) > 2:
            return word[2:]
    return None


def find_tmux_invocation(words):
    """Return (tmux arguments, TMUX_TMPDIR set by this command or None), or None."""
    index = 0
    tmux_tmpdir = None
    while index < len(words):
        word = words[index]
        if ENVIRONMENT_ASSIGNMENT_PATTERN.match(word):
            if word.startswith("TMUX_TMPDIR="):
                tmux_tmpdir = word[len("TMUX_TMPDIR="):]
            index += 1
            continue
        if any(is_program(word, prefix) for prefix in COMMAND_RUNNING_PREFIXES):
            running_timeout = is_program(word, "timeout")
            index += 1
            while index < len(words):
                option = words[index]
                if ENVIRONMENT_ASSIGNMENT_PATTERN.match(option):
                    if option.startswith("TMUX_TMPDIR="):
                        tmux_tmpdir = option[len("TMUX_TMPDIR="):]
                    index += 1
                    continue
                if option in PREFIX_VALUE_OPTIONS:
                    index += 2
                    continue
                if option.startswith("-"):
                    index += 1
                    continue
                break
            if running_timeout:
                index += 1  # the timeout duration
            continue
        break
    if index < len(words) and is_program(words[index], "tmux"):
        return words[index + 1:], tmux_tmpdir
    return None


def unnamed_server_kill(arguments):
    """Return the kill command word when the invocation kills without -L or -S."""
    index = 0
    while index < len(arguments):
        word = arguments[index]
        if word in SERVER_NAMING_FLAGS or (
                len(word) > 2 and word[:2] in SERVER_NAMING_FLAGS
                and not word.startswith("--")):
            return None
        if word in TMUX_GLOBAL_VALUE_FLAGS:
            index += 2
            continue
        if word.startswith("-"):
            index += 1
            continue
        break
    # Commands after the first follow a ";" word, as in tmux new -d \; kill-server.
    command_positions = [index] + [position + 1 for position in range(index, len(arguments))
                                   if arguments[position] == ";"]
    for position in command_positions:
        if position < len(arguments) and arguments[position].startswith(KILL_COMMAND_PREFIXES):
            return arguments[position]
    return None


def words_without_redirections(words):
    """Drop redirections, which the tokenizer keeps as words, from a suggested command."""
    kept, index = [], 0
    while index < len(words):
        match = REDIRECTION_WORD_PATTERN.match(words[index])
        if match:
            # A bare operator such as > takes its target from the next word.
            index += 2 if match.end() == len(words[index]) else 1
            continue
        kept.append(words[index])
        index += 1
    return kept


def refusal_for(command):
    shell_view, _heredoc_bodies = split_out_heredocs(command)
    for words in tokenize_simple_commands(shell_view):
        if not words:
            continue
        invocation = find_tmux_invocation(list(words))
        if invocation is None:
            continue
        arguments, tmux_tmpdir = invocation
        kill_word = unnamed_server_kill(arguments)
        if kill_word is None:
            continue
        kept = words_without_redirections(arguments)
        if (tmux_tmpdir and "$" not in tmux_tmpdir and "`" not in tmux_tmpdir
                and ";" not in arguments
                and not any(SHELL_EXPANSION_PATTERN.search(word) for word in kept)):
            socket_path = f"{tmux_tmpdir.rstrip('/')}/tmux-{os.getuid()}/default"
            suggested = " ".join(["tmux", "-S", shlex.quote(socket_path)]
                                 + [shlex.quote(word) for word in kept])
            return REFUSAL_WITH_COMMAND_TEMPLATE.format(
                kill=f"tmux {kill_word}", tmpdir=tmux_tmpdir, command=suggested)
        target = session_target(arguments)
        if (kill_word.startswith("kill-ses") and target and ";" not in arguments
                and all(SAFE_SESSION_COMMAND_WORD_PATTERN.fullmatch(word) for word in kept)):
            return SESSION_REFUSAL_TEMPLATE.format(command=" ".join(kept), target=target)
        return REFUSAL_WITHOUT_COMMAND_MESSAGE
    return None


def main(stdin=sys.stdin):
    try:
        payload = json.load(stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if payload.get("tool_name") != "Bash":
        return 0
    command = (payload.get("tool_input") or {}).get("command")
    if not isinstance(command, str):
        return 0
    reason = refusal_for(command)
    if reason:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
