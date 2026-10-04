#!/usr/bin/env python3
"""Block synthetic keystrokes that could race an operator’s typing.

Pass commands as launch arguments; detached tmux injection is permitted.
Detection is literal, not a complete shell interpreter: generated scripts and
unsupported ssh option forms can escape analysis."""

import json
import re
import shlex
import subprocess
import sys
import time

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

COMMAND_SEPARATOR_CHARS = ";\n&|()`"

# Hex encoding isolates expansion commands from quote and glob scanners.
# NUL cannot occur in a real shell command, so the marker cannot collide with command text.
EXPANDED_BODY_COMMANDS_MARK = "\x00"

# Bound recursion because a crashed PreToolUse hook lets the command through.
MAX_SUBSTITUTION_NESTING = 64

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


class HeredocScanState:
    """Quote, substitution, and parameter-expansion state carried between shell lines."""

    def __init__(self):
        self.in_single = False
        self.in_ansi_c = False   # inside $'...', where \' does not end the string
        self.in_double = False
        self.substitution_depths = []
        self.braces = []  # (substitution level, parenthesis count) for each open ${


def scan_line_for_heredoc_markers(line, state):
    """Return (terminator, body_is_expanded, operator_index) triples and update quote state."""
    # Quoted << is data, <<< is a here-string, and numeric delimiters can be arithmetic shifts.
    terminators = []
    depths = state.substitution_depths
    braces = state.braces
    i, n = 0, len(line)
    while i < n:
        char = line[i]
        if state.in_single or state.in_ansi_c:
            if char == "\\" and state.in_ansi_c:
                i += 2
                continue
            if char == "'":
                state.in_single = state.in_ansi_c = False
            i += 1
            continue
        if state.in_double:
            if char == "\\" or line[i:i + 2] == "$$":
                i += 2
                continue
            if char == '"':
                state.in_double = False
            elif line[i:i + 2] == "$(":
                depths.append(0)
                state.in_double = False
                i += 1
            i += 1
            continue
        if char == "\\" or line[i:i + 2] == "$$":
            i += 2
            continue
        if line[i:i + 2] == "$'":
            state.in_ansi_c = True
            i += 2
            continue
        if char == "'":
            state.in_single = True
            i += 1
            continue
        if char == '"':
            state.in_double = True
            i += 1
            continue
        if depths and line[i:i + 2] == "${":
            braces.append((len(depths), depths[-1]))
            i += 2
            continue
        in_braces = bool(braces) and braces[-1][0] == len(depths)
        if char == "}" and in_braces:
            braces.pop()
            i += 1
            continue
        if char in "()" and depths:
            if in_braces and depths[-1] <= braces[-1][1] and not (
                    char == "(" and line[i - 1:i] == "$"):
                i += 1  # A parenthesis in the expansion pattern does not close the substitution.
                continue
            if char == "(":
                depths[-1] += 1
            elif depths[-1]:
                depths[-1] -= 1
            else:
                depths.pop()
                state.in_double = True  # Resume the surrounding string after the substitution closes.
                while braces and braces[-1][0] > len(depths):
                    braces.pop()
            i += 1
            continue
        if char == "#" and (i == 0 or line[i - 1] in " \t;&|()`"):
            break
        if char == "<" and line[i:i + 2] == "<<" and line[i:i + 3] != "<<<" \
                and (i == 0 or line[i - 1] != "<"):
            if inside_shell_arithmetic(line[:i]):
                i += 2  # Arithmetic << is a shift, not a heredoc.
                continue
            j = i + 2
            if j < n and line[j] == "-":
                j += 1
            while j < n and line[j] in " \t":
                j += 1
            delimiter = read_heredoc_delimiter(line, j)
            if delimiter is None:
                i = j + 1
                continue
            terminator, body_is_expanded, end = delimiter
            if end > j and not (body_is_expanded and terminator.isdigit()):
                terminators.append((terminator, body_is_expanded, i))
            i = end
            continue
        i += 1
    return terminators


def inside_shell_arithmetic(prefix):
    """Return whether a shift is inside arithmetic rather than a nested command substitution."""
    if "$((" not in prefix:
        return False
    tail = prefix[prefix.rindex("$((") + 3:]
    if "))" in tail:
        return False
    open_substitutions = 0
    k = 0
    while k < len(tail):
        if tail[k:k + 2] == "$(" and tail[k + 2:k + 3] != "(":
            open_substitutions += 1
            k += 2
            continue
        if tail[k] == ")" and open_substitutions:
            open_substitutions -= 1
        k += 1
    return open_substitutions == 0


def read_heredoc_delimiter(line, start):
    """Return (terminator, body_is_expanded, end), or None for an unclosed quote."""
    # Any quoting in a delimiter suppresses expansion; all quoting is removed from the terminator.
    terminator = []
    quoted = False
    i, n = start, len(line)
    while i < n and line[i] not in " \t<>|&;()`":
        if line[i] == "\\":
            terminator.append(line[i + 1:i + 2])
            quoted = True
            i += 2
        elif line[i] in "'\"":
            closing = line.find(line[i], i + 1)
            if closing == -1:
                return None
            terminator.append(line[i + 1:closing])
            quoted = True
            i = closing + 1
        else:
            terminator.append(line[i])
            i += 1
    return "".join(terminator), not quoted, i


def substitutions_in_expanded_text(text):
    """Return command lists executed while expanding an unquoted-delimiter heredoc."""
    # An unclosed substitution runs nothing; the shell rejects it and stops expansion.
    found = []
    i, n = 0, len(text)
    while i < n:
        if text[i] == "\\" or text[i:i + 2] == "$$":
            i += 2
        elif text[i:i + 2] == "$(":
            _commands, closing = tokenize_command_list(text, i + 2, (i,))
            if closing >= n:
                break
            found.append(text[i + 2:closing])
            i = closing + 1
        elif text[i] == "`":
            closing = i + 1
            while closing < n and text[closing] != "`":
                closing += 2 if text[closing] == "\\" else 1
            if closing >= n:
                break
            found.append(text[i + 1:closing])
            i = closing + 1
        else:
            i += 1
    return found


def split_out_heredocs(command):
    """Return (shell_view, heredocs), retaining consumers and encoded expansion commands."""
    # A body is data unless its consumer executes it; unquoted delimiters also execute substitutions.
    # Lax terminator matching exposes extra text to analysis rather than hiding commands.
    shell_lines, heredocs = [], []
    lines = command.replace(EXPANDED_BODY_COMMANDS_MARK, "").split("\n")
    index = 0
    state = HeredocScanState()
    while index < len(lines):
        line = lines[index]
        terminators = scan_line_for_heredoc_markers(line, state)
        index += 1
        expanded_bodies = []  # (operator_index, marked command lists)
        for terminator, body_is_expanded, operator_index in terminators:
            body_lines = []
            while index < len(lines):
                candidate = lines[index].strip()
                if candidate == terminator:
                    index += 1
                    break
                if candidate.startswith(terminator + ")"):
                    lines[index] = lines[index].lstrip()[len(terminator):]
                    break  # The suffix beginning at ) resumes shell syntax.
                body_lines.append(lines[index])
                index += 1
            body = "\n".join(body_lines)
            heredocs.append((line, body))
            if body_is_expanded:
                expanded_bodies.append((operator_index, "".join(
                    EXPANDED_BODY_COMMANDS_MARK
                    + text.encode("utf-8", "surrogatepass").hex()
                    + EXPANDED_BODY_COMMANDS_MARK
                    for text in substitutions_in_expanded_text(body))))
        for operator_index, marked in reversed(expanded_bodies):
            line = line[:operator_index] + marked + line[operator_index:]
        shell_lines.append(line)
    return "\n".join(shell_lines), heredocs


def tokenize_simple_commands(shell_text, glob_markers=None):
    """Return simple commands with quoting resolved and substitutions preceding their consumers."""
    # This is not a full shell grammar: redirects remain words and expansions are not performed.
    # Glob markers preserve which characters were unquoted and unescaped.
    commands, _end = tokenize_command_list(shell_text, 0, (), glob_markers)
    return commands


class SubstitutionCommand(list):
    """Words tagged with enclosing substitutions so callers keep subshell state isolated."""

    def __init__(self, words, substitution):
        super().__init__(words)
        self.substitution = substitution


def read_whole_command_list(text, substitution, glob_markers):
    """Read all commands, including those after an unmatched closing parenthesis."""
    commands, start = [], 0
    while start < len(text):
        found, end = tokenize_command_list(text, start, substitution, glob_markers)
        commands.extend(found)
        start = end + 1
    return commands


def tokenize_command_list(shell_text, start, substitution, glob_markers=None):
    """Return (commands, end), where end is the closing substitution index or text length."""
    commands, current = [], []
    word = None
    open_parentheses = 0
    brace_depths = []   # Parenthesis depth at each open ${
    last_dollar = None  # Index of the last unquoted, unescaped $
    # Each case carries its parenthesis depth and phase: header before in,
    # pattern before ), then body until ;;, ;& or ;;&.
    open_cases = []

    def end_word():
        nonlocal word
        if word is not None:
            text = "".join(word)
            current.append(text)
            word = None
            if text == "case" and len(current) == 1:
                open_cases.append([open_parentheses, "header"])
            elif (open_cases and open_cases[-1][1] == "header"
                    and len(current) == 3 and current[0] == "case" and text == "in"):
                open_cases[-1][1] = "pattern"
                end_command()
            elif open_cases and text == "esac" and len(current) == 1:
                open_cases.pop()

    def end_command():
        nonlocal current
        end_word()
        if current:
            commands.append(
                SubstitutionCommand(current, substitution) if substitution else current)
            current = []

    i, n = start, len(shell_text)
    while i < n:
        char = shell_text[i]
        if char == "\\":
            if i + 1 < n and shell_text[i + 1] == "\n":
                i += 2
                continue
            if word is None:
                word = []
            if i + 1 < n:
                word.append(shell_text[i + 1])
            i += 2
            continue
        if char == "'":
            if word is None:
                word = []
            closing = i + 1
            if last_dollar == i - 1:
                # $'...' permits escaped quotes, so \' does not end the string.
                while closing < n and shell_text[closing] != "'":
                    closing += 2 if shell_text[closing] == "\\" else 1
            else:
                closing = shell_text.find("'", i + 1)
                if closing == -1:
                    closing = n
            word.append(shell_text[i + 1:closing])
            i = min(closing + 1, n)
            continue
        if char == '"':
            if word is None:
                word = []
            piece = []
            lost_its_place = False
            j = i + 1
            while j < n and shell_text[j] != '"':
                if shell_text[j] == "\\" and j + 1 < n and shell_text[j + 1] in '"\\$`':
                    piece.append(shell_text[j + 1])
                    j += 2
                elif shell_text[j:j + 2] == "$$":
                    piece.append("$$")
                    j += 2
                elif (shell_text[j] == "`" and not lost_its_place
                      and len(substitution) < MAX_SUBSTITUTION_NESTING):
                    closing = j + 1
                    while closing < n and shell_text[closing] != "`":
                        closing += 2 if shell_text[closing] == "\\" else 1
                    if closing >= n:
                        # An unmatched backtick is rejected by the shell and runs nothing.
                        piece.append(shell_text[j])
                        j += 1
                        continue
                    inner = re.sub(r'\\([$`\\"])', r"\1", shell_text[j + 1:closing])
                    commands.extend(read_whole_command_list(
                        inner, substitution + (j,), glob_markers))
                    piece.append(shell_text[j:closing + 1])
                    j = closing + 1
                elif (shell_text[j:j + 2] == "$(" and not lost_its_place
                      and len(substitution) < MAX_SUBSTITUTION_NESTING):
                    substituted, closing = tokenize_command_list(
                        shell_text, j + 2, substitution + (j,), glob_markers)
                    commands.extend(substituted)
                    if closing < n:
                        piece.append(shell_text[j:closing + 1])
                        j = closing + 1
                    else:
                        # An unclosed substitution must not swallow commands after the string.
                        lost_its_place = True
                        piece.append("$(")
                        j += 2
                else:
                    piece.append(shell_text[j])
                    j += 1
            word.append("".join(piece))
            i = j + 1 if j < n else n
            continue
        if char in " \t":
            end_word()
            i += 1
            continue
        if char == EXPANDED_BODY_COMMANDS_MARK:
            closing = shell_text.find(EXPANDED_BODY_COMMANDS_MARK, i + 1)
            if closing == -1:
                closing = n
            encoded = shell_text[i + 1:closing]
            try:
                body_text = bytes.fromhex(encoded).decode("utf-8", "surrogatepass")
            except ValueError:
                body_text = encoded  # An input NUL rather than an encoded expansion marker.
            # Substitutions can contain heredocs whose bodies also need classification.
            body_shell_view, _nested_heredocs = split_out_heredocs(body_text)
            commands.extend(read_whole_command_list(
                body_shell_view, substitution + (i,), glob_markers))
            i = closing + 1
            continue
        if char in COMMAND_SEPARATOR_CHARS:
            if (brace_depths and char in "()"
                    and open_parentheses <= brace_depths[-1]
                    and not (char == "(" and shell_text[i - 1] in "$<>")):
                # Parentheses in ${...} patterns are data unless a nested substitution opened them.
                if word is None:
                    word = []
                word.append(char)
                i += 1
                continue
            end_word()  # Finish esac before interpreting its following parenthesis.
            if open_cases and open_cases[-1][0] == open_parentheses:
                expected = open_cases[-1][1]
                if char == ")" and expected == "pattern":
                    end_command()
                    open_cases[-1][1] = "body"
                    i += 1
                    continue
                if char == "(" and expected == "pattern" and not current:
                    i += 1  # Optional opening parenthesis in a case pattern.
                    continue
                if (char == ";" and expected == "body"
                        and shell_text[i + 1:i + 2] in (";", "&")):
                    end_command()
                    open_cases[-1][1] = "pattern"
                    i += 3 if shell_text[i + 1:i + 3] == ";&" else 2
                    continue
            end_command()
            if char == "(":
                open_parentheses += 1
            elif char == ")":
                if open_parentheses:
                    open_parentheses -= 1
                elif substitution:
                    return commands, i
            i += 1
            continue
        if char == "#" and word is None:
            # Only a word-initial unquoted # opens a shell comment; foo#bar stays one word.
            while i < n and shell_text[i] != "\n":
                i += 1
            continue
        if word is None:
            word = []
        if shell_text[i:i + 2] == "$$":
            # $$ is the process ID; neither dollar starts an expansion.
            word.append("$$")
            i += 2
            continue
        if char == "$":
            last_dollar = i
            if shell_text[i + 1:i + 2] == "{":
                brace_depths.append(open_parentheses)
                word.append("${")
                i += 2
                continue
        elif char == "}" and brace_depths:
            brace_depths.pop()
        word.append(glob_markers.get(char, char) if glob_markers else char)
        i += 1
    end_command()
    return commands, n


def is_program(word, name):
    return word == name or word.endswith("/" + name)


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
        if ("can't find" in error_text or "no server running" in error_text
                or "error connecting" in error_text):
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

    verb_index = find_tmux_keystroke_verb(after)
    if verb_index is None:
        return None
    if verified:
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
        shell_view, heredocs = split_out_heredocs(text)
        for words in tokenize_simple_commands(shell_view):
            reason = analyze_simple_command(words, ssh_context, verified, guard)
            if reason:
                return reason
        for consumer_line, body in heredocs:
            for words in tokenize_simple_commands(consumer_line):
                if any(is_program(word, "osascript") for word in words):
                    if APPLESCRIPT_TYPING_PATTERN.search(body):
                        return SYNTHETIC_TYPING_REASON
                if any(is_program(word, name) for word in words
                       for name in SHELL_CONSUMER_PROGRAMS):
                    reason = analyze_command_text(body, ssh_context,
                                                  verified, guard)
                    if reason:
                        return reason
        return None
    finally:
        guard.depth -= 1


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
    reason = analyze_command_text(command, None, False, guard)
    if reason:
        deny(reason)
    return 0


if __name__ == "__main__":
    if sys.argv[1:2] == [CHECK_MODE_FLAG]:
        sys.exit(run_check_mode(sys.argv[2:]))
    sys.exit(main())
