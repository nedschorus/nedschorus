#!/usr/bin/env python3
"""PreToolUse guard: block Bash commands that send synthetic keystrokes at a
surface an operator may be typing on, and teach the safe form in the error.

The rule (nedschorus#27, learned twice on 2026-08-17): synthetic keystrokes
race the human's real ones and splice. AppleScript `write text` corrupted a
window-open command on the user's Mac while he typed; tmux `paste-buffer`
carries the same hazard for any attached session. The safe forms pass the
command as an argument — scripts/open-iterm-window-running-command for a
user-facing window, tmux new-session/respawn-pane with a command for
lifecycle — and injection into a *detached* tmux session stays permitted
until the inbox design (nedschorus#37) replaces it.

Decisions, in order:
- AppleScript synthetic typing — iTerm `write text`, System Events
  `keystroke`/`key code` — in the arguments of an invoked `osascript` (or in
  a heredoc body it consumes): always denied; the opener script fully covers
  the legitimate use.
- tmux keystroke verbs (`send-keys`/`paste-buffer` and their documented
  aliases `send`/`pasteb`): allowed when every `-t` target of that invocation
  verifiably has no attached client (the guard itself runs `tmux
  display-message -p '#{session_attached}'`, over ssh when that tmux is
  ssh-wrapped); denied with the verification recipe when a target is
  attached, unnamed, an unexpanded variable or placeholder (`$SEAT`,
  xargs' `{}`), or unverifiable. A target tmux
  does not know is allowed — keystrokes to a nonexistent session type
  nothing, and the command fails on its own.
- `CLAUDE_VERIFIED_DETACHED=1` as an environment-assignment prefix on the
  command (or on the ssh command wrapping it) skips the tmux check: the
  escape hatch for a caller that has just verified detachment itself. The
  same text inside a keystroke payload string is data and does not count.

How the guard reads a command (the 2026-08-17 review round, PR #82): it
tokenizes the shell text with quoting resolved and splits it into simple
commands, so only words in an actually-invoked command count — quoted prose
like `git commit -m "document the osascript write text rule"` or `grep -rn
"tmux send-keys" scripts/` is a single data word and passes. A `$( ... )`
inside double quotes is not data: the shell runs it, so its contents are read
as commands and the string resumes at its matching `)`. Heredoc bodies
are split out first (quote-state carried across lines, so `<<` inside a
string, a here-string `<<<`, or arithmetic like `1<<20` opens no phantom
heredoc); a body is data unless its consumer executes it — `osascript
<<EOF` is checked for synthetic typing, and a body piped to or fed to a
shell (`sh`, `bash`, `zsh`) is analyzed as a command itself, as are `sh -c`
execution strings (the c may ride in a flag cluster, `bash -lc`) and `eval`
arguments. When the heredoc's delimiter is not quoted the shell expands the
body, so each `$( ... )` and backticked command in the body is read as the
commands it is. Unquoted `#` comments are stripped the way the shell strips
them. An `ssh` whose
remote command contains the tmux invocation attributes probes to that host
(carrying -p/-i/-l); ssh found elsewhere in a command — e.g. inside a
keystroke payload — attributes nothing.

Which tmux SERVER the probe asks (per-seat servers, 2026-08-21): fleet seats
run one tmux server per seat (`tmux -L <seat>`, the launchers' rule since
the Mac's single default server died and took all three Mac seats down at
once), so "no server running" on the default socket no longer means a
session is down — it may be attached on its own socket, and a probe that
stopped at the default socket would misjudge it as safe to type into. The
probe therefore dials, in order:
- the server the guarded command itself dials: its own -L/-S flag when it
  carries one — probed EXCLUSIVELY, since keystrokes can only land on the
  server the command addresses and other sockets are irrelevant — else the
  same plain resolution the command will get ($TMUX's server when the
  command runs inside tmux, the default socket otherwise). The plain probe
  also covers the transition: seats launched before the per-seat change
  still live on the default server.
- only when that server does not know the session and the command carried
  no socket flag: the seat's own per-seat server, `-L <session part of the
  target>` (socket name == session name is the launchers' convention). A
  hit there rules the decision.
An unverifiable probe (timeout, unreachable host) denies immediately — fail
closed, never shopping past an error to a later "unknown". A session that NO
probed server knows stays allowed: keystrokes to a nonexistent session type
nothing, and the command fails on its own.

All probes share one wall-clock budget (PROBE_BUDGET_SECONDS) kept under the
hook's own registered timeout, because a PreToolUse hook that times out
FAILS OPEN in the harness: on overrun the guard denies as unverifiable
instead of dying. Probe results are cached per (host, server flags, target)
within one invocation.

Detection is literal, not adversarial: it corrects the habit of composing
these commands directly, which is the only way the failures have happened.
Known pass-throughs by design: invocations laundered through generated
files, python, backtick substitution inside double quotes, a script fed to
a shell's stdin (`echo ... | sh`), or ssh option forms the probe cannot
reproduce (combined `-p2222`, `-o`/`-J` chains — the probe then dials its
default route, which can misjudge a box it cannot actually see).
"""

import json
import re
import shlex
import subprocess
import sys
import time

OPENER = "scripts/open-iterm-window-running-command"

# The hook's settings.json registration must give the hook more than this
# budget (currently 30s registered vs 18s budget): a timed-out hook fails
# open, so the guard must always answer inside its own timeout.
PROBE_BUDGET_SECONDS = 18.0
PER_PROBE_TIMEOUT_SECONDS = 10.0
SSH_CONNECT_TIMEOUT_SECONDS = 5
MAX_ANALYSIS_DEPTH = 4

KEYSTROKE_VERBS = {"send-keys", "send", "paste-buffer", "pasteb"}
SHELL_CONSUMER_PROGRAMS = {"sh", "bash", "zsh", "dash", "ksh"}

# tmux flags that precede the command verb and consume a value.
TMUX_GLOBAL_VALUE_FLAGS = {"-S", "-L", "-f", "-c", "-T"}

# ssh options that consume a following value; anything else starting with "-"
# is a bare flag. Needed to find the hostname in an ssh-wrapped command.
SSH_VALUE_OPTIONS = {
    "-o", "-p", "-i", "-l", "-F", "-J", "-E", "-L", "-R", "-D", "-W",
    "-b", "-c", "-e", "-m", "-Q", "-S", "-B", "-w",
}
# The subset the probe re-uses so it dials the same box the command would.
SSH_CARRIED_OPTIONS = {"-p", "-i", "-l"}

# Sentinel ssh host for a chain the probe cannot reproduce (ssh inside ssh).
NESTED_SSH_HOST = "<nested-ssh>"

APPLESCRIPT_TYPING_PATTERN = re.compile(r"write text|\bkeystroke\b|\bkey code\b")

ENVIRONMENT_ASSIGNMENT_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")

COMMAND_SEPARATOR_CHARS = ";\n&|()`"

# In the shell view, each command list the shell runs while it expands an
# unquoted-delimiter heredoc body sits between two of these, hex-encoded, at
# the heredoc's <<. The tokenizer decodes it and reads it as a substitution of
# its own, so nothing in it can run past its end. Encoded, it holds no quote,
# glob character or # for a reader that scans the shell view's text itself
# to misread. The shell cannot be handed a NUL, so none can come from a real
# command's text.
EXPANDED_BODY_COMMANDS_MARK = "\x00"

# Deeper than this, a double-quoted `$(` is read as data, the way the reader
# read every one before it learned substitutions. Real commands nest 3 deep at
# most; without a limit, nesting near Python's recursion limit crashed every
# guard, and a crashed PreToolUse hook lets the command through.
MAX_SUBSTITUTION_NESTING = 64

SYNTHETIC_TYPING_REASON = (
    "Blocked: AppleScript synthetic typing — iTerm `write text`, System "
    "Events `keystroke`/`key code` — sends keystrokes that race the user's "
    "real typing and splice (this exact failure corrupted a command on "
    "2026-08-17; rule on nedschorus#27). To open a terminal window running "
    f"a command for the user, run: {OPENER} <command...> — it passes the "
    "command as the new session's own process, no keystrokes involved."
)

ATTACHED_REASON = (
    "Blocked: tmux session '{target}' has an attached client, so "
    "send-keys/paste-buffer would splice into whoever is typing there "
    "(nedschorus#27; evidence on #37). Injection is permitted only into "
    "detached sessions. To show the user something, open them a window with "
    f"{OPENER}; for agent-to-agent messaging the durable path is the "
    "nedschorus#37 inbox design."
)

UNVERIFIED_REASON = (
    "Blocked: could not verify that tmux target '{target}' has no attached "
    "client ({error}). Verify yourself with: {probe} — 0 means detached — "
    "then re-run this command with CLAUDE_VERIFIED_DETACHED=1 prefixed. "
    "Never inject keystrokes at a session someone may be typing in "
    "(nedschorus#27)."
)

UNRESOLVED_TARGET_REASON = (
    "Blocked: tmux target '{target}' contains an unexpanded variable or "
    "substitution placeholder, so this guard cannot verify the real target "
    "is detached — probing the literal text would misjudge it. Inline the "
    "literal session name, or verify detachment yourself with: {probe} — 0 "
    "means detached — then re-run with CLAUDE_VERIFIED_DETACHED=1 prefixed "
    "(rule: nedschorus#27)."
)

NO_TARGET_REASON = (
    "Blocked: this send-keys/paste-buffer names no -t target, so the "
    "keystrokes would land in tmux's current session — possibly the very "
    "one the user is attached to — and cannot be verified detached. Name "
    "the session with -t, or use "
    f"{OPENER} / the nedschorus#37 inbox instead (rule: nedschorus#27)."
)


class GuardRun:
    """Per-invocation mutable state: the shared probe budget clock, the
    (host, target) probe cache, and analysis recursion depth."""

    def __init__(self, runner, clock):
        self.runner = runner
        self.clock = clock
        self.deadline = clock() + PROBE_BUDGET_SECONDS
        self.probe_cache = {}
        self.depth = 0


class HeredocScanState:
    """What the heredoc scan carries from one line to the next: which kind of
    quote it is inside, and one entry per `$(` opened inside double quotes
    and still open, counting the parentheses open inside it."""

    def __init__(self):
        self.in_single = False   # inside '...'
        self.in_ansi_c = False   # inside $'...', where \' does not end the string
        self.in_double = False
        self.substitution_depths = []


def scan_line_for_heredoc_markers(line, state):
    """Find heredoc delimiters opened on this shell line. Quote-aware, with
    quote state carried in and out so a `<<` inside a string — even a string
    opened on an earlier line — is data. `<<<` is a here-string and a purely
    numeric "delimiter" is arithmetic (`1<<20`); neither opens a heredoc.

    A `$(` inside double quotes opens a command substitution, which is shell
    again until its matching `)`, so a `<<` there does open a heredoc — the
    form of `git commit -m "$(cat <<'EOF' ... )"`. A parenthesis inside a
    `${ ... }` of that substitution belongs to the expansion's pattern, as in
    `${x%(*}`, and closes nothing unless a `$(` inside the braces opened it.

    `$$` is the shell's process id, so neither of its `$` starts a `$'...'`
    string or a `$(`.

    Returns a list of (terminator, body_is_expanded, operator_index) triples
    and updates state in place. body_is_expanded is True when no part of the
    delimiter is quoted: the shell then expands the body before the consumer
    reads it. operator_index is where the heredoc's << stands in the line."""
    terminators = []
    depths = state.substitution_depths
    braces = []  # (substitution level, its parenthesis count) at each open ${
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
                i += 1  # part of the expansion's pattern
                continue
            if char == "(":
                depths[-1] += 1
            elif depths[-1]:
                depths[-1] -= 1
            else:
                depths.pop()
                state.in_double = True  # back in the string the $( was opened in
                while braces and braces[-1][0] > len(depths):
                    braces.pop()
            i += 1
            continue
        if char == "#" and (i == 0 or line[i - 1] in " \t;&|()`"):
            break  # unquoted comment — the rest of the line is not shell
        if char == "<" and line[i:i + 2] == "<<" and line[i:i + 3] != "<<<" \
                and (i == 0 or line[i - 1] != "<"):
            prefix = line[:i]
            if "$((" in prefix and "))" not in prefix[prefix.rindex("$(("):]:
                i += 2  # inside shell arithmetic, e.g. $((x<<2))
                continue
            j = i + 2
            if j < n and line[j] == "-":
                j += 1
            while j < n and line[j] in " \t":
                j += 1
            delimiter = read_heredoc_delimiter(line, j)
            if delimiter is None:
                i = j + 1  # a quote in the delimiter never closes
                continue
            terminator, body_is_expanded, end = delimiter
            if end > j and not (body_is_expanded and terminator.isdigit()):
                terminators.append((terminator, body_is_expanded, i))
            i = end
            continue
        i += 1
    return terminators


def read_heredoc_delimiter(line, start):
    """Read the heredoc delimiter word that starts at line[start], the way the
    shell reads it: the line that ends the body is the word with its quotes
    and backslashes removed, so `\\EOF`, `'EOF'` and `E"O"F` all end at EOF,
    and the body is expanded only when no part of the word is quoted.

    Returns (terminator, body_is_expanded, end), end being the index after
    the word, or None when a quote in the word never closes on this line."""
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
    """The command lists the shell runs while it expands text the way it
    expands the body of a heredoc whose delimiter is not quoted: the inside of
    each `$( ... )` and of each pair of backticks. A backslash takes the
    character after it out of play, as it does for the shell there, and `$$`
    is the process id, not the start of a `$(`.

    A substitution that never closes runs nothing: the shell reports a bad
    substitution and expands no further, so it and the text after it are
    data."""
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
    """Return (shell_view, heredocs): the command with heredoc bodies removed,
    and a list of (consumer_line, body) pairs.

    A heredoc body is data to the shell — a commit message or a written file
    mentioning `osascript` and `write text` is prose, not keystrokes, and the
    guard blocked its own commit message before learning this. But the body IS
    the script when the consumer executes it (`osascript <<EOF`, `sh <<EOF`),
    so consumers are kept for the caller to judge.

    One part of a body is not data: when no part of the delimiter is quoted
    (`<<EOF`, not `<<'EOF'`), the shell expands the body and runs every
    `$( ... )` and backticked command in it when it runs the command the
    heredoc belongs to. Each of those command lists stays in the shell view,
    hex-encoded between two EXPANDED_BODY_COMMANDS_MARKs placed just before
    the heredoc's <<, so the callers read it as the commands it is, ahead of the
    command it belongs to and of anything after that on the line. The
    tokenizer reads each as a substitution of its own: a lone quote in it
    cannot reach past its end, and a `cd` in it moves nothing outside it.
    The rest of the body is data as before.

    Terminator matching strips indentation, which is laxer than the shell
    for `<<` without a dash; a body ending early only exposes more lines to
    analysis — the fail-closed direction."""
    shell_lines, heredocs = [], []
    lines = command.split("\n")
    index = 0
    state = HeredocScanState()
    while index < len(lines):
        line = lines[index]
        terminators = scan_line_for_heredoc_markers(line, state)
        index += 1
        expanded_bodies = []  # (operator_index, the marked command lists)
        for terminator, body_is_expanded, operator_index in terminators:
            body_lines = []
            while index < len(lines) and lines[index].strip() != terminator:
                body_lines.append(lines[index])
                index += 1
            index += 1  # the terminator line itself
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


def tokenize_simple_commands(shell_text):
    """Split shell text into simple commands — lists of words with quoting
    resolved — cut at ;, newlines, &, |, parentheses, and backticks. Quoted
    material becomes part of a word and never separates, which is what lets
    the guard tell `tmux send-keys` the invocation from "tmux send-keys" the
    quoted prose. Not a full shell grammar: redirections stay as plain words
    and expansions are not performed.

    One thing inside double quotes is not data: a `$( ... )`, which the shell
    runs. Its simple commands are listed ahead of the command whose word
    holds it, in the order the shell runs them, and that word keeps the
    substitution's text unexpanded, so a caller testing a word for `$` still
    finds it. Each of those commands is a SubstitutionCommand, which says
    which substitution it sits in.

    A reading of a substitution that never finds its closing `)` has lost its
    place, and must not take the rest of the command with it: the commands it
    found are kept, and the string is then read to its closing quote as
    data, so every command after the string is still listed. A double-quoted
    `$(` nested deeper than MAX_SUBSTITUTION_NESTING is data in the same way.

    The hex-encoded text between two EXPANDED_BODY_COMMANDS_MARKs, which
    split_out_heredocs puts there, is a substitution's command list: it is
    decoded and read on its own, its commands are SubstitutionCommands, and
    its end is the second mark."""
    commands, _end = tokenize_command_list(shell_text, 0, ())
    return commands


class SubstitutionCommand(list):
    """A simple command found inside a double-quoted `$( ... )`, or inside a
    substitution in an unquoted-delimiter heredoc body: its words, and in
    `substitution` the substitution it sits in and every one around that,
    outermost first. The shell runs a substitution in a shell of its
    own, so a caller that carries state from one command to the next, as the
    force-push guard carries a `cd`, keeps that state inside the substitution.
    To every other caller it is the list of words it always was."""

    def __init__(self, words, substitution):
        super().__init__(words)
        self.substitution = substitution


def tokenize_command_list(shell_text, start, substitution):
    """tokenize_simple_commands from index start. substitution is empty at
    the top level; inside a double-quoted `$( ... )` it names that
    substitution and the ones around it. Returns (commands, end): inside a
    substitution, end is the index of the `)` that closes it; otherwise, and
    for a substitution that never closes, the length of the text."""
    commands, current = [], []
    word = None
    open_parentheses = 0
    brace_depths = []   # open_parentheses at each ${ still open
    last_dollar = None  # index of the last unquoted, unescaped $

    def end_word():
        nonlocal word
        if word is not None:
            current.append("".join(word))
            word = None

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
                i += 2  # line continuation
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
                # $'...': a backslash escapes, so \' does not end the string.
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
                elif (shell_text[j:j + 2] == "$(" and not lost_its_place
                      and len(substitution) < MAX_SUBSTITUTION_NESTING):
                    substituted, closing = tokenize_command_list(
                        shell_text, j + 2, substitution + (j,))
                    commands.extend(substituted)
                    if closing < n:
                        piece.append(shell_text[j:closing + 1])
                        j = closing + 1
                    else:
                        # Never closed. Keep what it found, and read on to
                        # this string's closing quote as data.
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
                body_text = encoded  # not ours: a NUL the command itself held
            body_commands, _end = tokenize_command_list(
                body_text, 0, substitution + (i,))
            commands.extend(body_commands)
            i = closing + 1
            continue
        if char in COMMAND_SEPARATOR_CHARS:
            if (brace_depths and char in "()"
                    and open_parentheses <= brace_depths[-1]
                    and not (char == "(" and shell_text[i - 1] == "$")):
                # Inside ${ ... } a parenthesis belongs to the expansion's
                # pattern, as in ${x%(*}, unless a $( inside the braces
                # opened it, or opened one around it.
                if word is None:
                    word = []
                word.append(char)
                i += 1
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
            # A word-initial unquoted # opens a comment, exactly the shell's
            # rule — foo#bar stays one word (N3: a comment mentioning the
            # banned forms must not deny the command below it).
            while i < n and shell_text[i] != "\n":
                i += 1
            continue
        if word is None:
            word = []
        if shell_text[i:i + 2] == "$$":
            # The shell's process id: neither $ starts $'...' or ${.
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
        word.append(char)
        i += 1
    end_command()
    return commands, n


def is_program(word, name):
    return word == name or word.endswith("/" + name)


def parse_ssh_invocation(words):
    """Given the words after an `ssh`, return (host, carried_options,
    remote_words). carried_options are the -p/-i/-l pairs the probe re-uses
    so it dials the same box. Combined forms like -p2222 read as bare flags
    and are not carried — a probe that then fails denies as unverifiable."""
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
    """Return the index of the tmux command verb within the words after
    `tmux` when that verb is a keystroke verb, else None. Walks tmux's
    pre-verb global flags rather than grepping, so `tmux kill-session -t
    send` — where 'send' is a target value — is not read as the send alias."""
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
    """The -L/-S socket flag pair the tmux invocation itself carries, from
    the pre-verb global flags: ["-L", "name"], ["-S", "path"], or []. The
    probe must dial the same server the command will — with per-seat servers
    (one tmux server per seat, 2026-08-21), the default server knowing
    nothing about a session says nothing about the server a socket-flagged
    command actually addresses."""
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
        return []  # reached the command verb without a socket flag
    return []


def per_seat_server_flags_for_target(target):
    """The -L flags of the per-seat server a target's session would live on:
    socket name == session name, the launchers' rule since 2026-08-21. The
    session name is the target up to any ':' window/pane qualifier, with
    tmux's '=' exact-match prefix stripped."""
    session_name = target.lstrip("=").split(":", 1)[0]
    return ["-L", session_name] if session_name else []


def extract_tmux_targets(words):
    """All -t values in the words after a keystroke verb: `-t name`,
    `-tname`, and (via the tokenizer) quoted names with spaces. Deduplicated,
    order preserved."""
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
    # ssh joins its command words with spaces and the remote shell re-splits,
    # so each word is quoted — a target like 'seat a' must survive the trip.
    remote = " ".join(shlex.quote(part) for part in tmux_argv)
    return (["ssh", "-o", "BatchMode=yes",
             "-o", "ConnectTimeout=%d" % SSH_CONNECT_TIMEOUT_SECONDS]
            + list(carried) + [host, remote])


def probe_recipe(target, server_flags, ssh_context):
    """The by-hand verification command a deny message teaches. Carries the
    guarded command's own socket flags when it has them; otherwise appends
    the per-seat-server probe, since a seat's session lives on its own
    socket (2026-08-21) and the plain probe alone can answer 'no server
    running' about a seat that is very much attached."""
    def one_probe(flags):
        flags_text = "".join(" %s" % part for part in flags)
        if ssh_context is None or ssh_context[0] == NESTED_SSH_HOST:
            return ('tmux%s display-message -p -t "%s" \'#{session_attached}\''
                    % (flags_text, target))
        host, carried = ssh_context
        ssh_words = ["ssh"] + list(carried) + [host]
        return ("%s 'tmux%s display-message -p -t \"%s\" \"#{session_attached}\"'"
                % (" ".join(ssh_words), flags_text, target))

    recipe = one_probe(server_flags)
    if not server_flags:
        per_seat_flags = per_seat_server_flags_for_target(target)
        if per_seat_flags:
            recipe += (" (finding no server? seats run per-seat tmux servers"
                       " — probe the seat's own socket: %s)"
                       % one_probe(per_seat_flags))
    return recipe


def run_attachment_probe(target, server_flags, ssh_context, guard):
    """One probe against one tmux server. Returns ("count", n) when that
    server answered, ("unknown", error) when it does not know the session
    (or is not running at all), ("unverifiable", error) otherwise. Probes
    share the guard's global budget (a timed-out hook fails open, so
    overruns must deny, not die)."""
    remaining = guard.deadline - guard.clock()
    if remaining <= 0:
        return ("unverifiable",
                "probe budget exhausted (%.0fs) — the hook must answer "
                "before its own timeout, which would fail open"
                % PROBE_BUDGET_SECONDS)
    argv = probe_argv(target, server_flags, ssh_context)
    try:
        completed = guard.runner(argv, capture_output=True, text=True,
                                 timeout=min(PER_PROBE_TIMEOUT_SECONDS, remaining))
    except Exception as error:  # timeout, missing binary — cannot verify
        return ("unverifiable", str(error))
    if completed.returncode != 0:
        error_text = (completed.stderr or "").strip()
        # Three shapes mean "this server cannot answer for that session":
        # "can't find" (server knows sessions, not this one), "no server
        # running" (socket file exists, no server behind it), and "error
        # connecting" (connect-stage failure: absent socket file — the
        # steady state for a never-dialed socket path, PR #122 review P2-2 —
        # or a refused connection on a dead server's leftover socket; matched
        # broadly on purpose, since every connect-stage reason means exactly
        # this). All three mean the NEXT candidate server may still know it.
        if ("can't find" in error_text or "no server running" in error_text
                or "error connecting" in error_text):
            return ("unknown", error_text)
        return ("unverifiable",
                error_text or "probe exited %d" % completed.returncode)
    stdout_text = (completed.stdout or "").strip()
    if not stdout_text:
        # rc 0 with empty stdout is tmux's CANFAIL shape for display-message
        # against a session this (live) server does not know — NOT a count of
        # 0 attached clients (PR #122 review P2-1). Treating it as a count
        # ended the candidate loop and the per-seat -L probe never ran.
        return ("unknown", "server answered but does not know the session")
    try:
        return ("count", int(stdout_text))
    except ValueError:
        return ("unverifiable", "unparseable probe output: %r" % completed.stdout)


def query_session_attached(target, server_flags, ssh_context, guard):
    """Return (attached_count, error). attached_count is None when
    unverifiable; a session NO probed server knows counts as 0 — there is
    nothing to type into, and the command fails on its own.

    Which servers are probed (per-seat tmux servers, 2026-08-21): when the
    command carries its own -L/-S socket flag, exactly that server — the
    only one its keystrokes can reach. Otherwise the plain resolution first
    (the same $TMUX-or-default dial the unflagged command gets, which also
    covers pre-change seats still on the default server), then the seat's
    own server (-L <session part of the target>) — without that second
    probe, an attached session on its own server reads as "no server
    running" and would be misjudged as detached. An unverifiable probe
    denies immediately rather than shopping on to a later "unknown".
    Results are cached per (host, server flags, target)."""
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
        result = (0, detail)  # unknown on this server — the next may know it
    guard.probe_cache[key] = result
    return result


def analyze_simple_command(words, ssh_context, verified, guard):
    """Rule on one simple command. Returns a deny reason or None."""
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
        # eval's arguments are a command; the old substring scan caught this
        # incidentally, the parser must catch it deliberately.
        return analyze_command_text(" ".join(after), ssh_context, verified,
                                    guard)

    if special_kind == "shell":
        # An inline execution string (`sh -c '...'`) is a command, not data,
        # and the c may ride in a flag cluster — `bash -lc`, `sh -euc` (N2).
        # A shell without -c executes a file — laundering, disclaimed.
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
        # Re-joining mirrors ssh itself: it joins the words with spaces and
        # the remote shell re-parses them.
        return analyze_command_text(" ".join(remote_words), remote_context,
                                    verified, guard)

    verb_index = find_tmux_keystroke_verb(after)
    if verb_index is None:
        return None
    if verified:
        return None
    # The command's own -L/-S socket flag names the only server its
    # keystrokes can reach, so the probes must dial that same server.
    server_flags = extract_tmux_server_flags(after[:verb_index])
    targets = extract_tmux_targets(after[verb_index + 1:])
    if not targets:
        return NO_TARGET_REASON
    for target in targets:
        # $VAR and `...` are shell expansions; {} is xargs'/parallel's
        # substitution placeholder (N1) — probing any of them literally gets
        # "can't find" and would allow while the real target may be attached.
        if "$" in target or "`" in target or "{}" in target:
            return UNRESOLVED_TARGET_REASON.format(
                target=target, probe=probe_recipe(target, server_flags, ssh_context))
        attached, error = query_session_attached(target, server_flags,
                                                 ssh_context, guard)
        if attached is None:
            return UNVERIFIED_REASON.format(
                target=target, error=error,
                probe=probe_recipe(target, server_flags, ssh_context))
        if attached > 0:
            return ATTACHED_REASON.format(target=target)
    return None


def analyze_command_text(text, ssh_context, verified, guard):
    """Analyze shell text (the whole Bash command, an ssh remote command, or
    a shell-consumed heredoc body). Returns a deny reason or None."""
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
    sys.exit(main())
