#!/usr/bin/env python3
"""Block synthetic keystrokes that could race an operator’s typing.

Pass commands as launch arguments; detached tmux injection is permitted.
Detection is literal, not a complete shell interpreter: generated scripts and
unsupported ssh option forms can escape analysis."""

import importlib.util
import json
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

_shell_reader_spec = importlib.util.spec_from_file_location(
    "shell_command_tree_sitter_bash_reader_common",
    Path(__file__).resolve().parents[1] / "nc-systems" / "general-tools"
    / "shell-command-tree-sitter-bash-reader-common.py")
shell_reader = importlib.util.module_from_spec(_shell_reader_spec)
_shell_reader_spec.loader.exec_module(shell_reader)
is_program = shell_reader.is_program

_tmux_error_pattern_spec = importlib.util.spec_from_file_location(
    "tmux_target_or_server_does_not_exist_error_pattern_common",
    Path(__file__).resolve().parents[1] / "nc-systems" / "general-tools"
    / "tmux-target-or-server-does-not-exist-error-pattern-common.py")
tmux_error_pattern = importlib.util.module_from_spec(_tmux_error_pattern_spec)
_tmux_error_pattern_spec.loader.exec_module(tmux_error_pattern)

OPENER = "scripts/open-iterm-window-running-command"

# Keep this budget below the registered hook timeout: timed-out hooks fail open.
PROBE_BUDGET_SECONDS = 18.0
PER_PROBE_TIMEOUT_SECONDS = 10.0
SSH_CONNECT_TIMEOUT_SECONDS = 5
MAX_ANALYSIS_DEPTH = 4

KEYSTROKE_VERBS = {"send-keys", "send", "paste-buffer", "pasteb"}
SHELL_CONSUMER_PROGRAMS = {"sh", "bash", "zsh", "dash", "ksh"}

TMUX_GLOBAL_VALUE_FLAGS = {"-S", "-L", "-f", "-c", "-T"}

# Options with values must be skipped as pairs to locate the ssh hostname.
SSH_VALUE_OPTIONS = {
    "-o", "-p", "-i", "-l", "-F", "-J", "-E", "-L", "-R", "-D", "-W",
    "-b", "-c", "-e", "-m", "-Q", "-S", "-B", "-w",
}
SSH_CARRIED_OPTIONS = {"-p", "-i", "-l"}

# Sentinel for an ssh chain the probe cannot reproduce.
NESTED_SSH_HOST = "<nested-ssh>"

APPLESCRIPT_TYPING_PATTERN = re.compile(r"write text|\bkeystroke\b|\bkey code\b")

ENVIRONMENT_ASSIGNMENT_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")


SYNTHETIC_TYPING_REASON = (
    "Blocked: AppleScript synthetic typing (iTerm `write text`, System Events "
    "`keystroke` or `key code`) sends keystrokes that race the user's real typing "
    "and interleave with it.\n"
    "If you want a terminal window running a command for the user, run: "
    f"{OPENER} <command...> (it starts the command as the new window's own "
    "process, with no keystrokes).\n"
    "If you meant to type into another application, stop and tell the user what "
    "you wanted typed."
)

# The window opener runs only on the Mac, so the guard names it only there.
SHOW_THE_USER_ON_MAC_LINE = (
    "If the purpose is to show the user something, open a window with "
    f"{OPENER} <command...>"
)
SHOW_THE_USER_ELSEWHERE_LINE = (
    "If the purpose is to show the user something, tell the user the command "
    "to run; the window opener runs only on the Mac."
)

ATTACHED_REASON = (
    "Blocked: tmux session '{target}' has an attached client, so send-keys or "
    "paste-buffer would interleave with the typing of whoever is attached. "
    "Sending keystrokes is permitted only into detached sessions.\n"
    "If the keystrokes carry a message for another agent-seat, send the message "
    "with the SendMessage tool instead; the ListAgents tool lists the seats' "
    "addresses.\n"
    "If SendMessage cannot reach the seat, tell the user.\n"
    "{show_line}\n"
    "Otherwise, do not send the keystrokes: tell the user what you were trying "
    "to do."
)

UNVERIFIED_REASON = (
    "Blocked: could not verify that tmux target '{target}' has no attached "
    "client ({error}). Keystrokes sent into a session someone is typing in "
    "interleave with that typing.\n"
    "Check the target with: {check_command}\n"
    "If it prints detached, run this command again at once with "
    "CLAUDE_VERIFIED_DETACHED=1 prefixed.\n"
    "If it prints anything else, do not send the keystrokes.\n"
    "If the keystrokes carry a message for another agent-seat, send the message "
    "with the SendMessage tool instead.\n"
    "{show_line}\n"
    "Otherwise, tell the user what you were trying to do."
)

NESTED_SSH_REASON = (
    "Blocked: tmux target '{target}' is reached through more than one ssh hop, "
    "and this guard cannot check through more than one hop that the session "
    "has no attached client. Keystrokes sent into a session someone is typing "
    "in interleave with that typing.\n"
    "If the keystrokes carry a message for another agent-seat, send the message "
    "with the SendMessage tool instead.\n"
    "If one ssh hop from here reaches the machine that runs the session, send "
    "the keystrokes through that one hop, so this guard can check the target.\n"
    "{show_line}\n"
    "Otherwise, tell the user what you were trying to do."
)

UNRESOLVED_TARGET_REASON = (
    "Blocked: tmux target '{target}' holds an unexpanded variable (a shell "
    "variable or command substitution) or an xargs or parallel replacement "
    "string ({{}}), so this guard cannot check that the real session is "
    "detached.\n"
    "If the target is a shell variable or command substitution, find the "
    "session's name where it is set (echo it), write the name into the command "
    "in place of the variable, and run the command again.\n"
    "If the target is xargs' or parallel's {{}}, list the sessions first, then "
    "send to each by name, one command per session."
)

NO_TARGET_REASON = (
    "Blocked: this send-keys or paste-buffer names no -t target, so the "
    "keystrokes would go to tmux's current session, which may be the session "
    "the user is typing in.\n"
    "If the keystrokes are meant for a detached session, name that session with "
    "-t and run the command again.\n"
    "If the keystrokes carry a message for another agent-seat, send the message "
    "with the SendMessage tool instead; the ListAgents tool lists the seats' "
    "addresses.\n"
    "{show_line}\n"
    "Otherwise, do not send the keystrokes: tell the user what you were trying "
    "to do."
)

# The check mode is run by an agent, not by the harness, so it can wait longer than the hook.
CHECK_MODE_FLAG = "--is-target-detached"
CHECK_MODE_PROBE_BUDGET_SECONDS = 60.0
CHECK_MODE_PER_PROBE_TIMEOUT_SECONDS = 30.0
CHECK_MODE_EXIT_DETACHED = 0
CHECK_MODE_EXIT_ATTACHED = 1
CHECK_MODE_EXIT_COULD_NOT_VERIFY = 2


def show_the_user_line(platform=None):
    platform = sys.platform if platform is None else platform
    if platform == "darwin":
        return SHOW_THE_USER_ON_MAC_LINE
    return SHOW_THE_USER_ELSEWHERE_LINE


class GuardRun:
    """Shared probe budget, cache, and recursion depth for one guard invocation."""

    def __init__(self, runner, clock, budget_seconds=PROBE_BUDGET_SECONDS,
                 per_probe_timeout_seconds=PER_PROBE_TIMEOUT_SECONDS):
        self.runner = runner
        self.clock = clock
        self.budget_seconds = budget_seconds
        self.per_probe_timeout_seconds = per_probe_timeout_seconds
        self.deadline = clock() + budget_seconds
        self.probe_cache = {}
        self.depth = 0


def parse_ssh_invocation(words):
    """Return (host, carried_options, remote_words), carrying only separate -p/-i/-l pairs."""
    carried = []
    index = 0
    while index < len(words):
        word = words[index]
        if word in SSH_VALUE_OPTIONS:
            if word in SSH_CARRIED_OPTIONS and index + 1 < len(words):
                carried.extend([word, words[index + 1]])
            index += 2
            continue
        if word.startswith("-"):
            index += 1
            continue
        return word, carried, words[index + 1:]
    return None, carried, []


def find_tmux_keystroke_verb(words):
    """Return the keystroke verb’s index after tmux global flags, or None."""
    index = 0
    while index < len(words):
        word = words[index]
        if word in TMUX_GLOBAL_VALUE_FLAGS:
            index += 2
            continue
        if word.startswith("-"):
            index += 1
            continue
        return index if word in KEYSTROKE_VERBS else None
    return None


def extract_tmux_server_flags(words):
    """Return the invocation’s -L/-S pair, or an empty list."""
    index = 0
    while index < len(words):
        word = words[index]
        if word in ("-L", "-S"):
            if index + 1 < len(words):
                return [word, words[index + 1]]
            return []
        if len(word) > 2 and not word.startswith("--") \
                and word[:2] in ("-L", "-S"):
            return [word[:2], word[2:]]
        if word in TMUX_GLOBAL_VALUE_FLAGS:
            index += 2
            continue
        if word.startswith("-"):
            index += 1
            continue
        return []
    return []


def per_seat_server_flags_for_target(target):
    # The launchers use the session name as the per-seat socket name.
    session_name = target.lstrip("=").split(":", 1)[0]
    return ["-L", session_name] if session_name else []


def extract_tmux_targets(words):
    """Return unique -t targets in invocation order."""
    targets = []
    index = 0
    while index < len(words):
        word = words[index]
        if word == "-t":
            if index + 1 < len(words):
                targets.append(words[index + 1])
                index += 2
                continue
            index += 1
            continue
        if word.startswith("-t") and len(word) > 2 and not word.startswith("--"):
            targets.append(word[2:])
        index += 1
    return list(dict.fromkeys(targets))


def probe_argv(target, server_flags, ssh_context):
    tmux_argv = ["tmux", *server_flags, "display-message", "-p", "-t", target,
                 "#{session_attached}"]
    if ssh_context is None:
        return tmux_argv
    host, carried = ssh_context
    # ssh joins words and the remote shell re-splits them; quote targets containing spaces.
    remote = " ".join(shlex.quote(part) for part in tmux_argv)
    return (["ssh", "-o", "BatchMode=yes",
             "-o", "ConnectTimeout=%d" % SSH_CONNECT_TIMEOUT_SECONDS]
            + list(carried) + [host, remote])


def check_command(target, server_flags, ssh_context):
    """Return the command line that runs this guard's own probe in its check mode."""
    words = ["python3", "scripts/synthetic-keystroke-guard-hook.py", CHECK_MODE_FLAG, target]
    if server_flags:
        words += ["--tmux-server-flag", server_flags[0], server_flags[1]]
    if ssh_context is not None:
        host, carried = ssh_context
        words += ["--ssh-host", host]
        for index in range(0, len(carried) - 1, 2):
            words += ["--ssh-option", carried[index], carried[index + 1]]
    return " ".join(shlex.quote(word) for word in words)


def run_attachment_probe(target, server_flags, ssh_context, guard):
    """Return (status, count_or_error), with status count, unknown, or unverifiable."""
    remaining = guard.deadline - guard.clock()
    if remaining <= 0:
        return ("unverifiable",
                "probe budget exhausted (%.0fs) — the hook must answer "
                "before its own timeout, which would fail open"
                % guard.budget_seconds)
    argv = probe_argv(target, server_flags, ssh_context)
    try:
        completed = guard.runner(argv, capture_output=True, text=True,
                                 timeout=min(guard.per_probe_timeout_seconds, remaining))
    except Exception as error:
        return ("unverifiable", str(error))
    if completed.returncode != 0:
        error_text = (completed.stderr or "").strip()
        # An unknown session or unavailable socket may exist on the next candidate server.
        if tmux_error_pattern.tmux_error_text_says_target_or_server_does_not_exist(error_text):
            return ("unknown", error_text)
        return ("unverifiable",
                error_text or "probe exited %d" % completed.returncode)
    stdout_text = (completed.stdout or "").strip()
    if not stdout_text:
        # tmux CANFAIL returns exit 0 with empty stdout for an unknown session, not zero attached clients.
        return ("unknown", "server answered but does not know the session")
    try:
        return ("count", int(stdout_text))
    except ValueError:
        return ("unverifiable", "unparseable probe output: %r" % completed.stdout)


def query_session_attached(target, server_flags, ssh_context, guard):
    """Return (attached_count, error), with None for unverifiable and 0 for unknown sessions."""
    # An explicit socket is exclusive; otherwise an unknown default session may exist on its own socket.
    # Stop on an unverifiable probe rather than accepting a later unknown result.
    key = (ssh_context, tuple(server_flags), target)
    if key in guard.probe_cache:
        return guard.probe_cache[key]
    if ssh_context is not None and ssh_context[0] == NESTED_SSH_HOST:
        result = (None, "nested ssh — this guard cannot probe through a jump chain")
        guard.probe_cache[key] = result
        return result
    candidate_flags = [list(server_flags)]
    if not server_flags:
        per_seat_flags = per_seat_server_flags_for_target(target)
        if per_seat_flags:
            candidate_flags.append(per_seat_flags)
    result = (0, "")
    for flags in candidate_flags:
        kind, detail = run_attachment_probe(target, flags, ssh_context, guard)
        if kind == "count":
            result = (detail, "")
            break
        if kind == "unverifiable":
            result = (None, detail)
            break
        result = (0, detail)
    guard.probe_cache[key] = result
    return result


def analyze_simple_command(words, ssh_context, verified, guard):
    """Return a denial reason, or None."""
    index = 0
    while index < len(words) and ENVIRONMENT_ASSIGNMENT_PATTERN.match(words[index]):
        index += 1
    verified = verified or "CLAUDE_VERIFIED_DETACHED=1" in words[:index]
    body = words[index:]

    special_kind = special_index = None
    for position, word in enumerate(body):
        for name in ("ssh", "tmux", "osascript", "eval"):
            if is_program(word, name):
                special_kind, special_index = name, position
                break
        if special_kind is None:
            for name in SHELL_CONSUMER_PROGRAMS:
                if is_program(word, name):
                    special_kind, special_index = "shell", position
                    break
        if special_kind:
            break
    if special_kind is None:
        return None
    after = body[special_index + 1:]

    if special_kind == "eval":
        return analyze_command_text(" ".join(after), ssh_context, verified,
                                    guard)

    if special_kind == "shell":
        # The execution flag can be clustered, as in bash -lc or sh -euc.
        for position, word in enumerate(after):
            if (word.startswith("-") and not word.startswith("--")
                    and word[1:].isalpha() and "c" in word[1:]
                    and position + 1 < len(after)):
                return analyze_command_text(after[position + 1], ssh_context,
                                            verified, guard)
        return None

    if special_kind == "osascript":
        if APPLESCRIPT_TYPING_PATTERN.search(" ".join(after)):
            return SYNTHETIC_TYPING_REASON
        return None

    if special_kind == "ssh":
        host, carried, remote_words = parse_ssh_invocation(after)
        if not remote_words or host is None:
            return None
        if ssh_context is not None:
            remote_context = (NESTED_SSH_HOST, ())
        else:
            remote_context = (host, tuple(carried))
        # ssh joins command words with spaces before the remote shell parses them.
        return analyze_command_text(" ".join(remote_words), remote_context,
                                    verified, guard)

    if verified:
        return None
    # tmux runs each command after a `\;` word as its own command, with the same global flags.
    global_flags, tmux_commands = split_tmux_command_sequence(after)
    for tmux_command in tmux_commands:
        reason = analyze_tmux_command(global_flags + tmux_command, ssh_context, guard)
        if reason:
            return reason
    return None


def split_tmux_command_sequence(after):
    """Return (global flags, [each tmux command's words]) for the words after `tmux`."""
    index = 0
    while index < len(after) and after[index].startswith("-"):
        index += 2 if after[index] in TMUX_GLOBAL_VALUE_FLAGS else 1
    commands, current = [], []
    for word in after[index:]:
        if word.endswith(";"):
            # tmux also ends a command at a word whose last character is the separator.
            if word != ";":
                current.append(word[:-1])
            commands.append(current)
            current = []
        else:
            current.append(word)
    commands.append(current)
    return after[:index], commands


def analyze_tmux_command(after, ssh_context, guard):
    """Return a denial reason for one tmux command that types keystrokes into a target, or None."""
    verb_index = find_tmux_keystroke_verb(after)
    if verb_index is None:
        return None
    # An explicit socket names the only server these keystrokes can reach.
    server_flags = extract_tmux_server_flags(after[:verb_index])
    targets = extract_tmux_targets(after[verb_index + 1:])
    if not targets:
        return NO_TARGET_REASON.format(show_line=show_the_user_line())
    for target in targets:
        # Probing expansions or xargs placeholders literally would report unknown and allow a possibly attached target.
        if "$" in target or "`" in target or "{}" in target:
            return UNRESOLVED_TARGET_REASON.format(target=target)
        attached, error = query_session_attached(target, server_flags,
                                                 ssh_context, guard)
        if attached is None and ssh_context is not None and ssh_context[0] == NESTED_SSH_HOST:
            return NESTED_SSH_REASON.format(target=target, show_line=show_the_user_line())
        if attached is None:
            return UNVERIFIED_REASON.format(
                target=target, error=error,
                check_command=check_command(target, server_flags, ssh_context),
                show_line=show_the_user_line())
        if attached > 0:
            return ATTACHED_REASON.format(target=target, show_line=show_the_user_line())
    return None


def analyze_command_text(text, ssh_context, verified, guard):
    """Return a denial reason for shell text, or None."""
    if guard.depth >= MAX_ANALYSIS_DEPTH:
        return None
    guard.depth += 1
    try:
        for words in shell_reader.simple_commands(text):
            reason = analyze_simple_command(words, ssh_context, verified, guard)
            if reason:
                return reason
            for heredoc in words.heredocs:
                reason = analyze_heredoc(words, heredoc.body, ssh_context, verified, guard)
                if reason:
                    return reason
        return None
    finally:
        guard.depth -= 1


def analyze_heredoc(words, body, ssh_context, verified, guard):
    """Return a denial reason when the command fed this heredoc runs it as a script, or None."""
    if any(is_program(word, "osascript") for word in words):
        if APPLESCRIPT_TYPING_PATTERN.search(body):
            return SYNTHETIC_TYPING_REASON
    ssh_index = next((index for index, word in enumerate(words) if is_program(word, "ssh")), None)
    if ssh_index is not None:
        host, carried, remote_words = parse_ssh_invocation(words[ssh_index + 1:])
        # ssh joins its remote words, and the remote shell splits them again.
        remote = " ".join(remote_words).split()
        # The remote shell runs the heredoc when ssh has no remote command, or when the remote
        # command is a shell reading its standard input, such as bash -s.
        if host is not None and (not remote or (
                any(is_program(remote[0], name) for name in SHELL_CONSUMER_PROGRAMS)
                and not any(word.startswith("-") and not word.startswith("--") and "c" in word
                            for word in remote[1:]))):
            remote_context = ((NESTED_SSH_HOST, ()) if ssh_context is not None
                              else (host, tuple(carried)))
            return analyze_command_text(body, remote_context, verified, guard)
        return None
    if any(is_program(word, name) for word in words for name in SHELL_CONSUMER_PROGRAMS):
        return analyze_command_text(body, ssh_context, verified, guard)
    return None


def deny(reason):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }}))


def parse_check_mode_arguments(arguments):
    """Return (target, server_flags, ssh_context) from the check mode's arguments."""
    target = arguments[0]
    server_flags = []
    host = None
    carried = []
    index = 1
    while index < len(arguments):
        word = arguments[index]
        if word == "--tmux-server-flag" and index + 2 < len(arguments) \
                and arguments[index + 1] in ("-L", "-S"):
            server_flags = [arguments[index + 1], arguments[index + 2]]
            index += 3
        elif word == "--ssh-host" and index + 1 < len(arguments):
            host = arguments[index + 1]
            index += 2
        elif word == "--ssh-option" and index + 2 < len(arguments) \
                and arguments[index + 1] in SSH_CARRIED_OPTIONS:
            carried += [arguments[index + 1], arguments[index + 2]]
            index += 3
        else:
            raise ValueError("unrecognised argument %r" % word)
    ssh_context = (host, tuple(carried)) if host is not None else None
    return target, server_flags, ssh_context


def run_check_mode(arguments, runner=subprocess.run, clock=time.monotonic, out=sys.stdout):
    """Print detached, attached, or could not verify for one tmux target, and exit to match."""
    if not arguments:
        print("could not verify: %s names no tmux target" % CHECK_MODE_FLAG, file=out)
        return CHECK_MODE_EXIT_COULD_NOT_VERIFY
    try:
        target, server_flags, ssh_context = parse_check_mode_arguments(arguments)
    except ValueError as error:
        print("could not verify: %s" % error, file=out)
        return CHECK_MODE_EXIT_COULD_NOT_VERIFY
    guard = GuardRun(runner, clock, CHECK_MODE_PROBE_BUDGET_SECONDS,
                     CHECK_MODE_PER_PROBE_TIMEOUT_SECONDS)
    attached, error = query_session_attached(target, server_flags, ssh_context, guard)
    if attached is None:
        print("could not verify: %s" % error, file=out)
        return CHECK_MODE_EXIT_COULD_NOT_VERIFY
    if attached > 0:
        print("attached", file=out)
        return CHECK_MODE_EXIT_ATTACHED
    if error:
        # query_session_attached reads a session no server knows as 0; only a counted 0 is detached.
        print("could not verify: no tmux server reported the session's attached "
              "clients, so the session may not exist (%s)" % error, file=out)
        return CHECK_MODE_EXIT_COULD_NOT_VERIFY
    print("detached", file=out)
    return CHECK_MODE_EXIT_DETACHED


def main(stdin=sys.stdin, runner=subprocess.run, clock=time.monotonic):
    try:
        payload = json.load(stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if payload.get("tool_name") != "Bash":
        return 0
    command = (payload.get("tool_input") or {}).get("command") or ""
    if not command:
        return 0
    guard = GuardRun(runner, clock)
    try:
        reason = analyze_command_text(command, None, False, guard)
    except shell_reader.ShellParserUnavailable as error:
        print(shell_reader.parser_unavailable_hook_output(
            "The synthetic keystroke guard", error))
        return 0
    if reason:
        deny(reason)
    return 0


if __name__ == "__main__":
    if sys.argv[1:2] == [CHECK_MODE_FLAG]:
        sys.exit(run_check_mode(sys.argv[2:]))
    sys.exit(main())
