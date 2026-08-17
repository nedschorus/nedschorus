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
"tmux send-keys" scripts/` is a single data word and passes. Heredoc bodies
are split out first (quote-state carried across lines, so `<<` inside a
string, a here-string `<<<`, or arithmetic like `1<<20` opens no phantom
heredoc); a body is data unless its consumer executes it — `osascript
<<EOF` is checked for synthetic typing, and a body piped to or fed to a
shell (`sh`, `bash`, `zsh`) is analyzed as a command itself, as are `sh -c`
execution strings (the c may ride in a flag cluster, `bash -lc`) and `eval`
arguments. Unquoted `#` comments are stripped the way the shell strips
them. An `ssh` whose
remote command contains the tmux invocation attributes probes to that host
(carrying -p/-i/-l); ssh found elsewhere in a command — e.g. inside a
keystroke payload — attributes nothing.

All probes share one wall-clock budget (PROBE_BUDGET_SECONDS) kept under the
hook's own registered timeout, because a PreToolUse hook that times out
FAILS OPEN in the harness: on overrun the guard denies as unverifiable
instead of dying. Probe results are cached per (host, target) within one
invocation.

Detection is literal, not adversarial: it corrects the habit of composing
these commands directly, which is the only way the failures have happened.
Known pass-throughs by design: invocations laundered through generated
files, python, command substitution inside double quotes, a script fed to
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


def scan_line_for_heredoc_markers(line, in_single, in_double):
    """Find heredoc delimiters opened on this shell line. Quote-aware, with
    quote state carried in and out so a `<<` inside a string — even a string
    opened on an earlier line — is data. `<<<` is a here-string and a purely
    numeric "delimiter" is arithmetic (`1<<20`); neither opens a heredoc.
    Returns (terminators, in_single, in_double)."""
    terminators = []
    i, n = 0, len(line)
    while i < n:
        char = line[i]
        if in_single:
            if char == "'":
                in_single = False
            i += 1
            continue
        if in_double:
            if char == "\\":
                i += 2
                continue
            if char == '"':
                in_double = False
            i += 1
            continue
        if char == "\\":
            i += 2
            continue
        if char == "'":
            in_single = True
            i += 1
            continue
        if char == '"':
            in_double = True
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
            if j < n and line[j] in "'\"":
                closing = line.find(line[j], j + 1)
                if closing != -1:
                    terminators.append(line[j + 1:closing])
                    i = closing + 1
                    continue
                i = j + 1
                continue
            match = re.match(r"""[^\s<>|&;()'"`]+""", line[j:])
            if match:
                delimiter = match.group(0)
                if not delimiter.isdigit():
                    terminators.append(delimiter)
                i = j + len(delimiter)
                continue
            i = j
            continue
        i += 1
    return terminators, in_single, in_double


def split_out_heredocs(command):
    """Return (shell_view, heredocs): the command with heredoc bodies removed,
    and a list of (consumer_line, body) pairs.

    A heredoc body is data to the shell — a commit message or a written file
    mentioning `osascript` and `write text` is prose, not keystrokes, and the
    guard blocked its own commit message before learning this. But the body IS
    the script when the consumer executes it (`osascript <<EOF`, `sh <<EOF`),
    so consumers are kept for the caller to judge.

    Terminator matching strips indentation, which is laxer than the shell
    for `<<` without a dash; a body ending early only exposes more lines to
    analysis — the fail-closed direction."""
    shell_lines, heredocs = [], []
    lines = command.split("\n")
    index = 0
    in_single = in_double = False
    while index < len(lines):
        line = lines[index]
        terminators, in_single, in_double = scan_line_for_heredoc_markers(
            line, in_single, in_double)
        shell_lines.append(line)
        index += 1
        for terminator in terminators:
            body_lines = []
            while index < len(lines) and lines[index].strip() != terminator:
                body_lines.append(lines[index])
                index += 1
            index += 1  # the terminator line itself
            heredocs.append((line, "\n".join(body_lines)))
    return "\n".join(shell_lines), heredocs


def tokenize_simple_commands(shell_text):
    """Split shell text into simple commands — lists of words with quoting
    resolved — cut at ;, newlines, &, |, parentheses, and backticks. Quoted
    material becomes part of a word and never separates, which is what lets
    the guard tell `tmux send-keys` the invocation from "tmux send-keys" the
    quoted prose. Not a full shell grammar: redirections stay as plain words
    and expansions are not performed."""
    commands, current = [], []
    word = None

    def end_word():
        nonlocal word
        if word is not None:
            current.append("".join(word))
            word = None

    def end_command():
        nonlocal current
        end_word()
        if current:
            commands.append(current)
            current = []

    i, n = 0, len(shell_text)
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
            closing = shell_text.find("'", i + 1)
            if closing == -1:
                word.append(shell_text[i + 1:])
                i = n
            else:
                word.append(shell_text[i + 1:closing])
                i = closing + 1
            continue
        if char == '"':
            if word is None:
                word = []
            piece = []
            j = i + 1
            while j < n and shell_text[j] != '"':
                if shell_text[j] == "\\" and j + 1 < n and shell_text[j + 1] in '"\\$`':
                    piece.append(shell_text[j + 1])
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
        if char in COMMAND_SEPARATOR_CHARS:
            end_command()
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
        word.append(char)
        i += 1
    end_command()
    return commands


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


def probe_argv(target, ssh_context):
    tmux_argv = ["tmux", "display-message", "-p", "-t", target,
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


def probe_recipe(target, ssh_context):
    local = 'tmux display-message -p -t "%s" \'#{session_attached}\'' % target
    if ssh_context is None or ssh_context[0] == NESTED_SSH_HOST:
        return local
    host, carried = ssh_context
    ssh_words = ["ssh"] + list(carried) + [host]
    return ("%s 'tmux display-message -p -t \"%s\" \"#{session_attached}\"'"
            % (" ".join(ssh_words), target))


def query_session_attached(target, ssh_context, guard):
    """Return (attached_count, error). attached_count is None when
    unverifiable; a target tmux does not know counts as 0 — there is nothing
    to type into. Probes share the guard's global budget (a timed-out hook
    fails open, so overruns must deny, not die) and are cached per
    (host, target)."""
    key = (ssh_context, target)
    if key in guard.probe_cache:
        return guard.probe_cache[key]
    if ssh_context is not None and ssh_context[0] == NESTED_SSH_HOST:
        result = (None, "nested ssh — this guard cannot probe through a jump chain")
        guard.probe_cache[key] = result
        return result
    remaining = guard.deadline - guard.clock()
    if remaining <= 0:
        result = (None, "probe budget exhausted (%.0fs) — the hook must "
                        "answer before its own timeout, which would fail open"
                        % PROBE_BUDGET_SECONDS)
        guard.probe_cache[key] = result
        return result
    argv = probe_argv(target, ssh_context)
    try:
        completed = guard.runner(argv, capture_output=True, text=True,
                                 timeout=min(PER_PROBE_TIMEOUT_SECONDS, remaining))
    except Exception as error:  # timeout, missing binary — cannot verify
        result = (None, str(error))
        guard.probe_cache[key] = result
        return result
    if completed.returncode != 0:
        error_text = (completed.stderr or "").strip()
        if "can't find" in error_text or "no server running" in error_text:
            result = (0, error_text)
        else:
            result = (None, error_text or "probe exited %d" % completed.returncode)
    else:
        try:
            result = (int((completed.stdout or "").strip() or "0"), "")
        except ValueError:
            result = (None, "unparseable probe output: %r" % completed.stdout)
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
    targets = extract_tmux_targets(after[verb_index + 1:])
    if not targets:
        return NO_TARGET_REASON
    for target in targets:
        # $VAR and `...` are shell expansions; {} is xargs'/parallel's
        # substitution placeholder (N1) — probing any of them literally gets
        # "can't find" and would allow while the real target may be attached.
        if "$" in target or "`" in target or "{}" in target:
            return UNRESOLVED_TARGET_REASON.format(
                target=target, probe=probe_recipe(target, ssh_context))
        attached, error = query_session_attached(target, ssh_context, guard)
        if attached is None:
            return UNVERIFIED_REASON.format(
                target=target, error=error,
                probe=probe_recipe(target, ssh_context))
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
