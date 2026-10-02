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
  environment assignments, behind env, command, nohup, nice and timeout, and
  behind the shell keywords that can stand in front of a command (`do`,
  `then`, `if`, `while`, `until` and the rest of LEADING_SHELL_KEYWORDS).
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
  that component, so it is not expanded unless that component itself begins
  with `-`, as in `-Users-el-agents-x/*.jsonl`; this keeps `~/x/*` and
  `/abs/*`, which can never begin with `-`, free of any file-system work.
- Expansion follows the shell's defaults: hidden names are not matched, and
  `**` recurses (zsh's default, bash's with globstar). It stops at the first
  name beginning with `-`, and all expansion in one command shares
  EXPANSION_BUDGET_SECONDS.
- The refusal gives the agent's own command, whole, with `--` put in front of
  the first glob that expands to such a name: the `cd` that put the search in
  that folder, the pipe, the redirections and the agent's quoting come through
  as written. The place is found by asking the shared reader, not by
  re-spelling words: `-- ` is tried at each place a word can start until the
  result reads as the same commands with `--` in front of that word
  (command_with_double_dash_before_word). Re-spelling the search's own words
  dropped the `cd` and quoted `"$k"` as `'$k'`, and a command that then
  prints nothing is the misreading this guard exists to stop. A command can
  hold more than one such search, so `--` is put in front of each, and the
  command given passes this guard when the agent runs it. When the budget
  runs out before the place is found, the refusal falls back to the search's
  own words, re-spelled, without the rest of the command.
- When an option follows that point, inserting `--` there would turn the
  option into a file name, so the refusal says where `--` goes instead of
  giving a command.

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
- Where a subshell ends. The shared tokenizer cuts at parentheses and keeps
  no record of them, so a `cd` inside `( ... )` or `$( ... )` still sets the
  directory for the commands after it, and a search there can be refused
  for a folder it does not run in. The command the refusal gives still works.
- Whether the agent's shell recurses on `**`. Bash without globstar matches
  one level where this guard matches every level, so a search can be refused
  for a name only the deeper levels hold; the command the refusal gives works.
- The budget inside a walk that yields few names. The budget is read before
  each word and after every 256th name, so `**/*.nosuch` over a large tree is
  ended by the hook's registered timeout, not by the budget, and the command
  then runs unguarded.
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
LEADING_SHELL_KEYWORDS = {"do", "then", "else", "elif", "if", "while", "until",
                          "{", "!", "time"}

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

# What an agent reads: what was refused and why -- the glob, a name it expands
# to, and the program that reads that name as an option -- then the one
# instruction that fixes the command. No ruling, date or citation: none of them
# would help the agent fix the command.
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
    whose first component holds no unquoted glob character is expanded only
    when that component itself begins with `-`."""
    first_component = word.split("/", 1)[0]
    if (not word_holds_unquoted_glob(first_component)
            and not first_component.startswith("-")):
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


def read_simple_commands(command):
    """The command's simple commands as this guard reads them: heredoc bodies
    dropped (a body is data here, see the module docstring's limits), and
    every unquoted glob character marked."""
    shell_view, _heredoc_bodies = split_out_heredocs(command)
    return tokenize_simple_commands(mark_unquoted_glob_characters(shell_view))


def command_with_double_dash_before_word(command, commands, command_index,
                                         word_index, deadline, clock):
    """The agent's own command text with `-- ` put in front of one word, or
    None when the budget runs out first.

    `-- ` is tried at each place a word can start, and the place is accepted
    when the shared reader reads the result as the same simple commands with
    `--` in front of that word. So the reader that found the word also says
    where the word is, and nothing here re-spells the command: a place inside
    quotes, a comment or a heredoc body reads differently and is passed over.
    The places where the word's own text stands unquoted are tried first,
    which is the first try for nearly every command."""
    expected = [list(words) for words in commands]
    expected[command_index].insert(word_index, "--")
    spelling = plain_word(commands[command_index][word_index])
    word_starts = [position for position in range(1, len(command))
                   if command[position - 1] in " \t\n"
                   and command[position] not in " \t\n"]
    word_starts.sort(key=lambda position: not command.startswith(spelling, position))
    for position in word_starts:
        if clock() > deadline:
            return None
        candidate = command[:position] + "-- " + command[position:]
        if read_simple_commands(candidate) == expected:
            return candidate
    return None


def refused_search(command, commands, command_index, program_index,
                   directory, deadline, clock):
    """What one search command is refused for, or None when it passes:
    (details, whole_command, respelled_search). The details fill a refusal
    template. whole_command is the agent's own command with `--` put in, or
    None when the budget ran out before the place was found.
    respelled_search is the search's own words with `--` put in, re-spelled,
    for that case. Both are None when no command can be given because an
    option follows the glob."""
    words = commands[command_index]
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
            return details, None, None
        whole_command = command_with_double_dash_before_word(
            command, commands, command_index, program_index + 1 + index,
            deadline, clock)
        # The search's own words from its program on. A shell keyword in
        # front of the program is left out, because `do grep ...` alone is a
        # syntax error.
        first_word = 0
        while words[first_word] in LEADING_SHELL_KEYWORDS:
            first_word += 1
        respelled = (words[first_word:program_index + 1] + arguments[:index]
                     + ["--"] + arguments[index:])
        respelled_search = " ".join(
            item if REDIRECTION_WORD_PATTERN.match(item) or item == "--"
            else shell_spelling_of_word(item)
            for item in respelled)
        return details, whole_command, respelled_search
    return None


def resolve_directory(base, target):
    expanded = os.path.expanduser(target)
    if os.path.isabs(expanded):
        return os.path.normpath(expanded)
    return os.path.normpath(os.path.join(base, expanded))


def first_refused_search(command, payload_cwd, deadline, clock):
    """Walk the command's simple commands in order, carrying the directory a
    literal `cd` puts them in, and return what the first refused search is
    refused for (see refused_search), or None."""
    commands = read_simple_commands(command)
    directory = payload_cwd
    for command_index, words in enumerate(commands):
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
        refused = refused_search(command, commands, command_index,
                                 search_index, directory, deadline, clock)
        if refused:
            return refused
    return None


def analyze_command_text(command, payload_cwd, clock=time.monotonic):
    """The refusal text for the first search in the command that would hand
    its program a name beginning with `-`, or None when every search passes.

    The command given is the whole command, so a second such search in it
    would have the agent refused again on running what the refusal gave.
    `--` is therefore put in front of each further search too, for as long as
    a command can be given and the budget lasts."""
    deadline = clock() + EXPANSION_BUDGET_SECONDS
    refused = first_refused_search(command, payload_cwd, deadline, clock)
    if refused is None:
        return None
    details, whole_command, respelled_search = refused
    if respelled_search is None:
        return REFUSAL_WITHOUT_COMMAND_TEMPLATE.format(**details)
    if whole_command is None:
        return REFUSAL_WITH_COMMAND_TEMPLATE.format(
            accepted_command=respelled_search, **details)
    while clock() <= deadline:
        try:
            further = first_refused_search(whole_command, payload_cwd,
                                           deadline, clock)
        except (ExpansionBudgetSpent, OSError, ValueError, re.error):
            break  # the refusal already found stands; give what there is
        if further is None or further[1] is None:
            break
        whole_command = further[1]
    return REFUSAL_WITH_COMMAND_TEMPLATE.format(
        accepted_command=whole_command, **details)


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
