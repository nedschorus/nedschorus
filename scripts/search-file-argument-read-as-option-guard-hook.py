#!/usr/bin/env python3
"""PreToolUse guard on Bash: refuse a grep, rg or ugrep whose file list, once
the shell has expanded its globs, would hold a name beginning with `-`, which
the program reads as options instead of as a file; say to put `--` before the
file names, and give the command it would accept.

THE BEHAVIOUR IT DEFENDS AGAINST, named per CLAUDE.md's reviewer rule. On
2026-09-22 agents searched the Claude Code transcript folders with commands of
the shape `cd ~/.claude/projects && grep -l phrase */*.jsonl`. Every folder
there is named after a path, `-Users-el-agents-merge-lane`, so the shell hands
grep `-Users-el-agents-merge-lane/x.jsonl`, and grep reads that word as the
options -U, -s, -e and so on. The search prints nothing, and the agent reads
"no hits". PR "The empty-search check's measurement is redone over today's
transcripts, and every firing is sorted"
(https://github.com/nedschorus/nedschorus/pull/763) sorted every firing of
the empty-search check over 62,005 commands from both machines: this shape
caused two of the four real misses and 8 of the 15 broken searches.

Measured again while writing this guard (2026-10-01, a scratch folder holding
`-Users-el-agents-x/a.jsonl` and `plain/b.jsonl`, both containing the searched
word, searched with `-l word */*.jsonl`): macOS /usr/bin/grep and the agent's
own `grep` (Claude Code's shell function, which runs ugrep) printed nothing
and exited 2; the agent's `rg` printed "word: No such file or directory" and
exited 2. With `--` before the file names, all three listed both files. The
test reproduces this against the real programs before it tests the guard.

DECISIONS, in order:
- Deny, never warn. A warning added after the command runs arrives with the
  empty result already read as "no hits".
- Programs: grep, egrep, fgrep, rg, ugrep, by name or by path, behind leading
  environment assignments and behind env, command, nohup, nice and timeout.
  The agent's `grep` and `rg` are shell functions with those names, so they
  are covered by name.
- Only a word whose glob characters stood outside quotes is expanded, the way
  the shell expands it. The shared tokenizer resolves quotes, so before it
  runs, every unquoted `*`, `?`, `[` and `]` is swapped for a private-use
  character (mark_unquoted_glob_characters); a quoted `"*.jsonl"` reaches the
  program as itself, and passes.
- A word is expanded in the directory the command runs in: the payload's cwd,
  or a literal `cd` earlier in the same command, as the force-push guard
  resolves it.
- Words after `--` are file names to every one of these programs, so they
  pass. Every other word holding an unquoted glob character is expanded, one
  that begins with `-` included: an option such as `--include=*.py` names no
  file, so it expands to nothing and passes, while `-[U]*/*.jsonl` expands to
  the folder and is refused.
- Only the first character of an expanded name matters. A pattern whose first
  path component holds no glob character expands only to names beginning with
  that component, so it is not expanded at all; this keeps `~/x/*` and
  `/abs/*`, which can never begin with `-`, free of any file-system work.
- Expansion follows the shell's defaults: hidden names are not matched, and
  `**` recurses (zsh's default, bash's with globstar). It stops at the first
  name beginning with `-`, and all expansion in one command shares
  EXPANSION_BUDGET_SECONDS.
- The refusal gives the command with `--` inserted before the first glob that
  expands to such a name. When an option follows that point, inserting `--`
  there would turn the option into a file name, so the refusal says where
  `--` goes instead of rebuilding the command.

IT FAILS OPEN, saying nothing, on: an unreadable payload; a `cd` whose target
it cannot resolve; an expansion that raises or runs out of the budget. A
guard that blocks ordinary searches when it cannot tell would cost more than
the mistake it prevents.

WHAT IT CANNOT SEE, so a later reader does not mistake a limit for a check:
- A command inside a double-quoted command substitution, `"$(grep ...)"`, is
  one data word to the shared tokenizer: GHI "The Bash guards' shared shell
  reader does not read inside a double-quoted command substitution"
  (https://github.com/nedschorus/nedschorus/issues/710).
- A file name reaching the program through a variable, as in `for f in
  */*.jsonl; do grep -l word "$f"; done`, which fails the same way: variables
  are not expanded.
- A search inside an ssh remote command: it is one quoted word here, and its
  glob expands on the other machine, which this guard cannot list.
- xargs, find -exec, sh -c, eval, and a heredoc fed to a shell.
- `git grep`, whose file arguments are pathspecs.
- Brace expansion, `{a,b}`, which is left as literal text.
- A glob given as an option's separate value (`-f *.txt`) is judged like any
  file word: if it expands to more than one name beginning with `-`, the rest
  are read as options anyway, so the refusal still holds.

The tokenizer, the heredoc split and `is_program` are imported from
scripts/synthetic-keystroke-guard-hook.py rather than copied, as the
force-push guard imports them: one shell reader, reviewed once. The test
asserts the import.
"""

import glob
import importlib.util
import json
import os
import re
import shlex
import sys
import time
from pathlib import Path

_keystroke_guard_path = Path(__file__).with_name("synthetic-keystroke-guard-hook.py")
_keystroke_guard_spec = importlib.util.spec_from_file_location(
    "synthetic_keystroke_guard_hook", _keystroke_guard_path)
keystroke_guard = importlib.util.module_from_spec(_keystroke_guard_spec)
_keystroke_guard_spec.loader.exec_module(keystroke_guard)

split_out_heredocs = keystroke_guard.split_out_heredocs
tokenize_simple_commands = keystroke_guard.tokenize_simple_commands
is_program = keystroke_guard.is_program

SEARCH_PROGRAMS = ("grep", "egrep", "fgrep", "rg", "ugrep")

# Shell keywords that can stand in front of a command on the same line.
LEADING_SHELL_KEYWORDS = {"do", "then", "else", "elif", "{", "!", "time"}

# Programs that run the rest of their words as a command. `timeout` takes
# options and a duration first; `nice` may take `-n <value>`.
COMMAND_RUNNING_PREFIXES = ("env", "command", "nohup", "nice", "timeout")
PREFIX_VALUE_OPTIONS = {"-u", "--unset", "-n", "-s", "--signal", "-k",
                        "--kill-after"}

ENVIRONMENT_ASSIGNMENT_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")

# A redirection as the shared tokenizer leaves it, as in the force-push guard.
REDIRECTION_WORD_PATTERN = re.compile(r"^[0-9]*(?:>>|>|<<<|<>|<)")

# A `cd` target this guard cannot resolve without running the shell.
UNRESOLVABLE_DIRECTORY_PATTERN = re.compile(r"[$`]")

# Unquoted glob characters, swapped for private-use characters before the
# shared tokenizer resolves quotes, so a word still says which of its glob
# characters the shell would expand.
GLOB_CHARACTER_MARKERS = {"*": "", "?": "", "[": "",
                          "]": ""}
MARKER_GLOB_CHARACTERS = {marker: character
                          for character, marker in GLOB_CHARACTER_MARKERS.items()}
# `]` alone opens nothing; a word needs one of these to be a glob.
GLOB_OPENING_MARKERS = {GLOB_CHARACTER_MARKERS[c] for c in "*?["}

# Kept well under the hook's registered timeout: a PreToolUse hook that
# overruns its timeout fails open silently.
EXPANSION_BUDGET_SECONDS = 5.0

# Characters a word can show unquoted in the command the refusal suggests.
SAFE_UNQUOTED_CHARACTERS = re.compile(r"^[A-Za-z0-9_./~@%+=:,-]+$")

# What an agent reads: instruction only, with the condition it applies under.
# Why and when live in this module's docstring.
REFUSAL_WITH_COMMAND_TEMPLATE = (
    "Refused: {glob_word} expands to names beginning with -, such as {name}, "
    "which {program} reads as options, not as files. Put -- before the file "
    "names and run: {accepted_command}"
)
REFUSAL_WITHOUT_COMMAND_TEMPLATE = (
    "Refused: {glob_word} expands to names beginning with -, such as {name}, "
    "which {program} reads as options, not as files. Put -- after the last "
    "option and before the file names, then run the command again."
)


class ExpansionBudgetSpent(Exception):
    """All glob expansion in one command shares one wall-clock budget."""


def mark_unquoted_glob_characters(shell_text):
    """Return shell_text with every glob character that stands outside quotes,
    and is not backslash-escaped, swapped for its private-use marker.

    Quote rules follow the shared tokenizer exactly, so the tokenizer still
    sees the same quotes and comments: single quotes take everything
    literally; inside double quotes a backslash escapes only `"`, `\\`, `$`
    and a backtick; outside quotes a backslash escapes the next character;
    and a `#` opening a word starts a comment that runs to the end of its
    line, whose quotes must not change the state."""
    marked = []
    in_single = in_double = False
    index, length = 0, len(shell_text)
    while index < length:
        character = shell_text[index]
        if in_single:
            marked.append(character)
            if character == "'":
                in_single = False
            index += 1
            continue
        if in_double:
            if character == "\\" and index + 1 < length \
                    and shell_text[index + 1] in '"\\$`':
                marked.append(shell_text[index:index + 2])
                index += 2
                continue
            if character == '"':
                in_double = False
            marked.append(character)
            index += 1
            continue
        if character == "\\":
            marked.append(shell_text[index:index + 2])
            index += 2
            continue
        if character == "'":
            in_single = True
        elif character == '"':
            in_double = True
        elif character == "#" and (index == 0
                                   or shell_text[index - 1] in " \t\n;&|()`"):
            end_of_line = shell_text.find("\n", index)
            end_of_line = length if end_of_line == -1 else end_of_line
            marked.append(shell_text[index:end_of_line])
            index = end_of_line
            continue
        elif character in GLOB_CHARACTER_MARKERS:
            marked.append(GLOB_CHARACTER_MARKERS[character])
            index += 1
            continue
        marked.append(character)
        index += 1
    return "".join(marked)


def word_holds_unquoted_glob(word):
    return any(marker in word for marker in GLOB_OPENING_MARKERS)


def plain_word(word):
    """The word as the program would receive it unexpanded: markers back to
    their glob characters."""
    return "".join(MARKER_GLOB_CHARACTERS.get(character, character)
                   for character in word)


def glob_pattern_for_word(word):
    """A glob.glob pattern for a marked word: its unquoted glob characters
    active, every other character matching only itself."""
    return "".join(MARKER_GLOB_CHARACTERS[character]
                   if character in MARKER_GLOB_CHARACTERS
                   else glob.escape(character)
                   for character in word)


def shell_spelling_of_word(word):
    """How the suggested command writes a word: unquoted glob characters bare,
    so the shell still expands them, and literal runs quoted only when they
    need it."""
    pieces, literal_run = [], []

    def flush_literal_run():
        if literal_run:
            text = "".join(literal_run)
            pieces.append(text if SAFE_UNQUOTED_CHARACTERS.match(text)
                          else shlex.quote(text))
            literal_run.clear()

    for character in word:
        if character in MARKER_GLOB_CHARACTERS:
            flush_literal_run()
            pieces.append(MARKER_GLOB_CHARACTERS[character])
        else:
            literal_run.append(character)
    flush_literal_run()
    return "".join(pieces)


def first_expansion_beginning_with_dash(word, directory, deadline, clock):
    """The first name the word expands to in `directory` that begins with
    `-`, or None. Raises ExpansionBudgetSpent when the shared budget runs out.

    Only the first path component decides the first character, so a word
    whose first component holds no unquoted glob character is not expanded."""
    first_component = word.split("/", 1)[0]
    if not word_holds_unquoted_glob(first_component):
        return None
    if clock() > deadline:
        raise ExpansionBudgetSpent()
    base = os.path.normpath(directory)
    prefix = glob.escape(base) + os.sep
    for count, path in enumerate(
            glob.iglob(prefix + glob_pattern_for_word(word), recursive=True)):
        relative = path[len(prefix):]
        if relative.startswith("-"):
            return relative
        if count % 256 == 255 and clock() > deadline:
            raise ExpansionBudgetSpent()
    return None


def search_program_index(words):
    """Index of the search program in a simple command's words, or None.

    Reads through leading shell keywords, environment assignments, and
    programs that run the rest of their words (env, command, nohup, nice,
    timeout) with their options and values."""
    index = 0
    while index < len(words):
        word = words[index]
        if word in LEADING_SHELL_KEYWORDS:
            index += 1
            continue
        if ENVIRONMENT_ASSIGNMENT_PATTERN.match(word):
            index += 1
            continue
        if any(is_program(word, prefix) for prefix in COMMAND_RUNNING_PREFIXES):
            running_timeout = is_program(word, "timeout")
            index += 1
            while index < len(words):
                option = words[index]
                if ENVIRONMENT_ASSIGNMENT_PATTERN.match(option):
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
                index += 1  # the duration
            continue
        break
    if index < len(words) and any(is_program(words[index], name)
                                  for name in SEARCH_PROGRAMS):
        return index
    return None


def refusal_for_search(words, program_index, directory, deadline, clock):
    """The refusal text for one search command, or None when it passes."""
    program = os.path.basename(words[program_index])
    arguments = words[program_index + 1:]
    index = 0
    while index < len(arguments):
        word = arguments[index]
        if word == "--":
            return None
        redirection = REDIRECTION_WORD_PATTERN.match(word)
        if redirection:
            target_is_next_word = redirection.end() == len(word)
            index += 2 if target_is_next_word else 1
            continue
        if not word_holds_unquoted_glob(word):
            index += 1
            continue
        name = first_expansion_beginning_with_dash(word, directory, deadline, clock)
        if name is None:
            index += 1
            continue
        later_words = arguments[index + 1:]
        option_follows = any(
            plain_word(later).startswith("-") and later != "-"
            and not REDIRECTION_WORD_PATTERN.match(later)
            for later in later_words)
        details = {"glob_word": plain_word(word), "name": name, "program": program}
        if option_follows:
            return REFUSAL_WITHOUT_COMMAND_TEMPLATE.format(**details)
        accepted = (words[:program_index + 1] + arguments[:index] + ["--"]
                    + arguments[index:])
        accepted_command = " ".join(
            item if REDIRECTION_WORD_PATTERN.match(item) or item == "--"
            else shell_spelling_of_word(item)
            for item in accepted)
        return REFUSAL_WITH_COMMAND_TEMPLATE.format(
            accepted_command=accepted_command, **details)
    return None


def resolve_directory(base, target):
    expanded = os.path.expanduser(target)
    if os.path.isabs(expanded):
        return os.path.normpath(expanded)
    return os.path.normpath(os.path.join(base, expanded))


def analyze_command_text(command, payload_cwd, clock=time.monotonic):
    """Walk the command's simple commands in order, carrying the directory a
    literal `cd` puts them in, and return the first refusal, or None.

    Heredoc bodies are dropped first: a body is data here (see the module
    docstring's limits)."""
    shell_view, _heredoc_bodies = split_out_heredocs(command)
    marked_view = mark_unquoted_glob_characters(shell_view)
    deadline = clock() + EXPANSION_BUDGET_SECONDS
    directory = payload_cwd
    for words in tokenize_simple_commands(marked_view):
        if not words:
            continue
        program_index = 0
        while (program_index < len(words)
               and ENVIRONMENT_ASSIGNMENT_PATTERN.match(words[program_index])):
            program_index += 1
        if program_index < len(words) and is_program(words[program_index], "cd"):
            target = (words[program_index + 1]
                      if program_index + 1 < len(words) else "~")
            target_is_absolute = os.path.isabs(os.path.expanduser(plain_word(target)))
            if (UNRESOLVABLE_DIRECTORY_PATTERN.search(target)
                    or word_holds_unquoted_glob(target)
                    or (directory is None and not target_is_absolute)):
                directory = None
            else:
                directory = resolve_directory(directory or "/", plain_word(target))
            continue
        if directory is None:
            continue
        search_index = search_program_index(words)
        if search_index is None:
            continue
        refusal = refusal_for_search(words, search_index, directory, deadline, clock)
        if refusal:
            return refusal
    return None


def deny(reason):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }}))


def main(stdin=sys.stdin, clock=time.monotonic):
    try:
        payload = json.load(stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(payload, dict) or payload.get("tool_name") != "Bash":
        return 0
    command = (payload.get("tool_input") or {}).get("command") or ""
    if not command:
        return 0
    payload_cwd = payload.get("cwd") or os.getcwd()
    try:
        refusal = analyze_command_text(command, payload_cwd, clock)
    except (ExpansionBudgetSpent, OSError, ValueError, re.error):
        return 0
    if refusal:
        deny(refusal)
    return 0


if __name__ == "__main__":
    sys.exit(main())
