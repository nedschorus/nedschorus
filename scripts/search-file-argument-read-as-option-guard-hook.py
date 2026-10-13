#!/usr/bin/env python3
"""Refuse search globs that expand to option-like filenames before --.

Variables, remote commands, shell launchers, braces, and git pathspecs are not expanded.
Bare subshell cwd boundaries and bash without globstar may produce false positives.
Expansion fails open on errors or budget exhaustion; sparse walks rely on the hook timeout."""

import glob
import importlib.util
import json
import os
import re
import shlex
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

SEARCH_PROGRAMS = ("grep", "egrep", "fgrep", "rg", "ugrep")

# tree-sitter-bash keeps the time keyword as the first word of the command it times.
LEADING_SHELL_KEYWORDS = {"time"}

ENVIRONMENT_ASSIGNMENT_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")

UNRESOLVABLE_DIRECTORY_PATTERN = re.compile(r"[$`]")

# Markers preserve which glob characters were unquoted and therefore subject to shell expansion.
GLOB_CHARACTER_MARKERS = {"*": "", "?": "", "[": "",
                          "]": ""}
MARKER_GLOB_CHARACTERS = {marker: character
                          for character, marker in GLOB_CHARACTER_MARKERS.items()}
# ] alone cannot open a glob character class.
GLOB_OPENING_MARKERS = {GLOB_CHARACTER_MARKERS[c] for c in "*?["}

# Stay below the hook timeout, which otherwise fails open silently.
EXPANSION_BUDGET_SECONDS = 5.0

SAFE_UNQUOTED_CHARACTERS = re.compile(r"^[A-Za-z0-9_./~@%+=:,-]+$")

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
    """The command's shared glob-expansion time budget was exhausted."""


def word_holds_unquoted_glob(word):
    return any(marker in word for marker in GLOB_OPENING_MARKERS)


def plain_word(word):
    """Return the unexpanded word with glob markers restored."""
    return "".join(MARKER_GLOB_CHARACTERS.get(character, character)
                   for character in word)


def glob_pattern_for_word(word):
    """Return a glob pattern that expands only the word's unquoted glob characters."""
    return "".join(MARKER_GLOB_CHARACTERS[character]
                   if character in MARKER_GLOB_CHARACTERS
                   else glob.escape(character)
                   for character in word)


def shell_spelling_of_word(word):
    """Return shell spelling that preserves unquoted globs and quotes literal characters."""
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
    """Return the first expansion beginning with -, or None; raise when the budget expires."""
    # Only the first path component can make the expanded filename begin with -.
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
    """Return the search-program index after shell keywords and wrappers, or None."""
    index, _ = shell_reader.simple_command_program_index_skipping_wrappers(words)
    if index is not None and any(is_program(words[index], name) for name in SEARCH_PROGRAMS):
        return index
    return None


def read_simple_commands(command):
    """Return simple commands with heredoc data removed and unquoted glob characters marked."""
    return shell_reader.simple_commands(command, glob_markers=GLOB_CHARACTER_MARKERS)


def command_with_double_dash_before_word(command, commands, command_index,
                                         word_index, deadline, clock):
    """Insert -- before the selected word without re-spelling the command, or return None."""
    # Reparse candidates to reject insertion inside quotes, comments, or heredocs.
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
    """Return refusal details and whole-command and re-spelled suggestions, or None if allowed."""
    words = commands[command_index]
    program = os.path.basename(words[program_index])
    arguments = words[program_index + 1:]
    index = 0
    while index < len(arguments):
        word = arguments[index]
        if word == "--":
            return None
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
            for later in later_words)
        details = {"glob_word": plain_word(word), "name": name, "program": program}
        if option_follows:
            return details, None, None
        whole_command = command_with_double_dash_before_word(
            command, commands, command_index, program_index + 1 + index,
            deadline, clock)
        # Omit leading shell keywords: a suggestion starting with do grep would be invalid shell syntax.
        first_word = 0
        while words[first_word] in LEADING_SHELL_KEYWORDS:
            first_word += 1
        respelled = (words[first_word:program_index + 1] + arguments[:index]
                     + ["--"] + arguments[index:])
        respelled_search = " ".join(
            [item if item == "--" else shell_spelling_of_word(item) for item in respelled]
            + [operator + shell_spelling_of_word(target)
               for operator, target in words.redirects if operator != "<<"])
        return details, whole_command, respelled_search
    return None


def resolve_directory(base, target):
    expanded = os.path.expanduser(target)
    if os.path.isabs(expanded):
        return os.path.normpath(expanded)
    return os.path.normpath(os.path.join(base, expanded))


def first_refused_search(command, payload_cwd, deadline, clock):
    """Return the first refused search while tracking literal cd commands."""
    commands = read_simple_commands(command)
    directories = {(): payload_cwd}  # A child shell's cd must not change the parent directory.
    for command_index, words in enumerate(commands):
        substitution = words.child_shell
        enclosing = substitution
        while enclosing not in directories:
            enclosing = enclosing[:-1]
        directory = directories[enclosing]
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
            directories[substitution] = directory
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
    """Return refusal text, or None when all searches pass."""
    # Fix every unsafe search in the suggestion so running the suggestion does not trigger another refusal.
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
            break  # Keep the existing refusal when the remaining budget cannot fix further searches.
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
    except shell_reader.ShellParserUnavailable as error:
        print(shell_reader.parser_unavailable_hook_output(
            "The search-file-argument guard", error))
        return 0
    except (ExpansionBudgetSpent, OSError, ValueError, re.error):
        return 0
    if refusal:
        deny(refusal)
    return 0


if __name__ == "__main__":
    sys.exit(main())
