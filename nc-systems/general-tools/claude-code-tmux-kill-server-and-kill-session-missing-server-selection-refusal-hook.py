#!/usr/bin/env python3
"""Refuse tmux kill-server and kill-session that name no server with -L or -S.

An agent's shell inherits $TMUX, which points at its agent-seat's own tmux
server; a tmux command naming no server acts on that server, and TMUX_TMPDIR
does not redirect it while $TMUX is set. With $TMUX unset, it acts on the
default server, which holds other sessions. Either way a bare kill can end
agent-seats, their supervisors and every agent under them.

Detection is literal, through the shared tokenizer, on every simple command:
tmux is found wherever it stands in the command, so shell reserved words
(do, then, !, {), prefixes (env, sudo, timeout, xargs) and assignments before
it do not hide it. A simple command that starts with echo or printf is data.
tmux's options are read the way tmux's getopt reads them, grouped flags and
redirections included, and every command of a tmux command sequence is
checked. Commands run by ssh, bash -c, eval or a script file are outside this
guard's scope.
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
deny = keystroke_guard.deny

# A simple command starting with one of these prints its words; it runs nothing.
DATA_PRINTING_PROGRAMS = ("echo", "printf")
# A word the shell would expand; the tokenizer has dropped its quotes, so the
# hook cannot rebuild the word exactly and gives no suggested command for it.
SHELL_EXPANSION_PATTERN = re.compile(r"[$`*?\[]")
REDIRECTION_WORD_PATTERN = re.compile(r"^[0-9]*(?:>>|>&|>|<<<|<>|<)")

# tmux's getopt string is "2c:CDdf:hlL:NqS:T:uUvV": these letters take a value.
TMUX_SERVER_NAMING_LETTERS = "LS"
TMUX_OTHER_VALUE_LETTERS = "cfT"

# tmux accepts any unambiguous prefix of a command name.
KILL_COMMAND_PREFIXES = ("kill-ser", "kill-ses")

REFUSAL_WITH_COMMAND_TEMPLATE = (
    "Refused on purpose: `{kill}` names no tmux server, so tmux acts on the "
    "server in $TMUX, which is the tmux server of the agent-seat you run in "
    "(or, with $TMUX unset, the default server, which holds other sessions). "
    "Killing it ends that agent-seat, its supervisor and every agent under "
    "it, you included. TMUX_TMPDIR does not change which server is meant "
    "while $TMUX is set.\n"
    "To run it on the private server whose socket lives under {tmpdir}, run:\n"
    "{command}\n"
    "From now on, name the server in every tmux command you run, with "
    "-S <socket path> or -L <name> right after tmux, from the command that "
    "starts the server to the one that kills it."
)

REFUSAL_WITHOUT_COMMAND_MESSAGE = (
    "Refused on purpose: this tmux kill names no tmux server, so tmux acts on "
    "the server in $TMUX, which is the tmux server of the agent-seat you run "
    "in (or, with $TMUX unset, the default server, which holds other "
    "sessions). Killing it, or the wrong session on it, ends that agent-seat, "
    "its supervisor and every agent under it, you included.\n"
    "If you started a tmux server of your own, run the same command with "
    "-S <socket path> or -L <name> right after tmux, naming that server, as "
    "in: tmux -L my-server kill-server, or: tmux -L my-server kill-session "
    "-t my-session\n"
    "If you started a session with a tmux command that named no server, that "
    "session is on your agent-seat's server: do not kill it with tmux. If "
    "the program you started in it must stop, stop that program with kill "
    "and its process id, as you would any background program; otherwise "
    "leave the session.\n"
    "If you started no tmux server or session of your own, there is nothing "
    "of yours to clean up: do not kill one, and you need not tell the user.\n"
    "From now on, name the server in every tmux command you run, with "
    "-S <socket path> or -L <name> right after tmux, from the command that "
    "starts the server to the one that kills it."
)


def find_tmux_invocation(words):
    """Return (tmux arguments, TMUX_TMPDIR set before tmux or None), or None."""
    first = next((word for word in words
                  if not keystroke_guard.ENVIRONMENT_ASSIGNMENT_PATTERN.match(word)), None)
    if first is None or any(is_program(first, name) for name in DATA_PRINTING_PROGRAMS):
        return None
    tmux_tmpdir = None
    for index, word in enumerate(words):
        if word.startswith("TMUX_TMPDIR="):
            tmux_tmpdir = word[len("TMUX_TMPDIR="):]
        elif is_program(word, "tmux"):
            return words[index + 1:], tmux_tmpdir
    return None


def words_without_redirections(words):
    """Drop redirections, which the tokenizer keeps as words."""
    kept, index = [], 0
    while index < len(words):
        match = REDIRECTION_WORD_PATTERN.match(words[index])
        if match:
            # A bare operator such as 2> takes its target from the next word.
            index += 2 if match.end() == len(words[index]) else 1
            continue
        kept.append(words[index])
        index += 1
    return kept


def unnamed_server_kill(arguments):
    """Return the kill command word when the invocation kills without -L or -S."""
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
            if letter in TMUX_SERVER_NAMING_LETTERS:
                return None
            if letter in TMUX_OTHER_VALUE_LETTERS:
                if position == len(letters) - 1:
                    index += 1  # the value is the next word
                break
        index += 1
    # Each later command of a sequence follows a word that is or ends with ";",
    # as in: tmux new -d \; kill-server, or: tmux new -d x\; kill-server
    command_positions = [index] + [position + 1 for position in range(index, len(arguments))
                                   if arguments[position].endswith(";")]
    for position in command_positions:
        if position < len(arguments) and arguments[position].startswith(KILL_COMMAND_PREFIXES):
            return arguments[position]
    return None


def private_socket_path(tmux_tmpdir):
    """Return the default socket under TMUX_TMPDIR, or None when the shell would expand it."""
    if not tmux_tmpdir or SHELL_EXPANSION_PATTERN.search(tmux_tmpdir):
        return None
    directory = os.path.expanduser(tmux_tmpdir)
    if directory.startswith("~"):
        return None
    return f"{directory.rstrip('/')}/tmux-{os.getuid()}/default"


def refusal_for(command):
    shell_view, _heredoc_bodies = split_out_heredocs(command)
    for words in tokenize_simple_commands(shell_view):
        invocation = find_tmux_invocation(list(words))
        if invocation is None:
            continue
        raw_arguments, tmux_tmpdir = invocation
        arguments = words_without_redirections(raw_arguments)
        kill_word = unnamed_server_kill(arguments)
        if kill_word is None:
            continue
        # The one exact command offered names the private server TMUX_TMPDIR
        # points at, for a single tmux command; a command aimed at the
        # agent-seat's own server is never offered.
        socket_path = private_socket_path(tmux_tmpdir)
        if (socket_path and not any(word.endswith(";") for word in arguments)
                and not any(SHELL_EXPANSION_PATTERN.search(word) for word in arguments)):
            suggested = " ".join(["tmux", "-S", shlex.quote(socket_path)]
                                 + [shlex.quote(word) for word in arguments])
            return REFUSAL_WITH_COMMAND_TEMPLATE.format(
                kill=f"tmux {kill_word}", tmpdir=tmux_tmpdir, command=suggested)
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
        deny(reason)
    return 0


if __name__ == "__main__":
    sys.exit(main())
