#!/usr/bin/env python3
"""Refuse search globs that expand to option-like filenames before --.

Variables, remote commands, shell launchers, braces, and git pathspecs are not expanded.
The value of an option that takes one, such as grep -f's pattern file, is not a file to search,
but a value that expands to two or more names, one beginning with -, is refused: the shell
passes only one of them as the value.
A refusal gives the agent's whole command with -- put in; when no place for -- is found,
it gives the search alone only if the command is that search, and otherwise no command.
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

# Options whose value may stand as the next word; that word is the option's value, such as
# grep -f's pattern file, not a file to search, so a dash-named match there is not misread.
GREP_OPTIONS_TAKING_A_VALUE = ("efmABCdD", (
    "--regexp", "--file", "--max-count", "--after-context", "--before-context", "--context",
    "--devices", "--directories", "--exclude", "--include", "--exclude-dir",
    "--exclude-from", "--label", "--binary-files", "--group-separator"))
SEARCH_PROGRAM_OPTIONS_TAKING_A_VALUE = {
    "grep": GREP_OPTIONS_TAKING_A_VALUE,
    "egrep": GREP_OPTIONS_TAKING_A_VALUE,
    "fgrep": GREP_OPTIONS_TAKING_A_VALUE,
    "ugrep": GREP_OPTIONS_TAKING_A_VALUE,
    "rg": ("efgtTmABCjMrE", (
        "--regexp", "--file", "--glob", "--iglob", "--type", "--type-not", "--type-add",
        "--max-count", "--after-context", "--before-context", "--context", "--threads",
        "--max-columns", "--replace", "--encoding", "--max-depth", "--max-filesize",
        "--pre", "--pre-glob", "--ignore-file", "--sort", "--sortr", "--color",
        "--colors", "--path-separator", "--field-match-separator",
        "--field-context-separator", "--context-separator", "--engine", "--type-clear")),
}

SAFE_UNQUOTED_CHARACTERS = re.compile(r"^[A-Za-z0-9_./~@%+=:,-]+$")

REFUSAL_WITH_COMMAND_TEMPLATE = (
    "Refused: {glob_word} expands to names beginning with -, such as {name}, "
    "which {program} reads as options, not as files. Put -- before the file "
    "names and run: {accepted_command}"
)
REFUSAL_OF_OPTION_VALUE_TEMPLATE = (
    "Refused: {glob_word}, the value of {option}, expands to two or more names. The shell "
    "passes only the first of them as {option}'s value, and {program} reads each of the "
    "others as one more word, and a name beginning with - as an option, such as {name}. "
    "-- cannot fix this.\n"
    "If you meant one of the names, write that name in place of {glob_word}.\n"
    "If you meant every name {glob_word} matches, give {option} once before each name.\n"
    "If you meant a file named {glob_word} itself, quote {glob_word}.\n"
    "Then run the command again."
)
REFUSAL_WITHOUT_COMMAND_TEMPLATE = (
    "Refused: {glob_word} expands to names beginning with -, such as {name}, "
    "which {program} reads as options, not as files.\n"
    "Write ./ in front of {glob_word}, as in ./{glob_word}, so that every name begins "
    "with ./ instead of -.\n"
    "Then run the command again."
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


def expansions_that_can_begin_with_dash(word, directory, deadline, clock):
    """Yield the names word expands to in directory, or nothing when none can begin with -.

    Raise when the budget expires.
    """
    # Only the first path component can make the expanded filename begin with -.
    first_component = word.split("/", 1)[0]
    if (not word_holds_unquoted_glob(first_component)
            and not first_component.startswith("-")):
        return
    if clock() > deadline:
        raise ExpansionBudgetSpent()
    base = os.path.normpath(directory)
    # The matches start with the directory as written, not as escaped for the pattern.
    literal_prefix = base if base.endswith(os.sep) else base + os.sep
    pattern_prefix = glob.escape(base) + ("" if base.endswith(os.sep) else os.sep)
    for count, path in enumerate(
            glob.iglob(pattern_prefix + glob_pattern_for_word(word), recursive=True)):
        name = path[len(literal_prefix):]
        # A recursive ** also yields the directory itself, which the shell does not expand to.
        if name:
            yield name
        if count % 256 == 255 and clock() > deadline:
            raise ExpansionBudgetSpent()


def first_expansion_beginning_with_dash(word, directory, deadline, clock):
    """Return the first expansion beginning with -, or None; raise when the budget expires."""
    for name in expansions_that_can_begin_with_dash(word, directory, deadline, clock):
        if name.startswith("-"):
            return name
    return None


def dash_name_among_two_or_more_expansions(word, directory, deadline, clock):
    """Return a name beginning with - that the program may read as an option, else None.

    None when word expands to fewer than two names or to no name beginning with -. The name
    returned is one the shell does not put first in byte order, when there is one.
    """
    names = list(expansions_that_can_begin_with_dash(word, directory, deadline, clock))
    dash_names = sorted(name for name in names if name.startswith("-"))
    if len(names) < 2 or not dash_names:
        return None
    # The shell sorts the names by the locale's collation, which can differ from byte order,
    # so any dash name may come after the first; one that is not first in byte order comes
    # after it in the common orders too. Sorting makes the name independent of listing order.
    first_in_byte_order = min(names)
    later_dash_names = [name for name in dash_names if name != first_in_byte_order]
    return (later_dash_names or dash_names)[0]


def option_takes_the_next_word_as_its_value(program, word):
    """Return whether word is an option of program whose value is the next word."""
    short_options, long_options = SEARCH_PROGRAM_OPTIONS_TAKING_A_VALUE.get(program, ("", ()))
    if word.startswith("--"):
        return word in long_options
    if not word.startswith("-") or word == "-":
        return False
    # In a cluster such as -lf, the first option that takes a value takes the rest of the word,
    # or the next word when it ends the cluster.
    for position, letter in enumerate(word[1:], start=1):
        if letter in short_options:
            return position == len(word) - 1
    return False


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
        if option_takes_the_next_word_as_its_value(program, plain_word(word)):
            value = arguments[index + 1] if index + 1 < len(arguments) else None
            if value is not None and word_holds_unquoted_glob(value):
                name = dash_name_among_two_or_more_expansions(value, directory,
                                                              deadline, clock)
                if name is not None:
                    return ({"glob_word": plain_word(value), "name": name,
                             "program": program, "option": plain_word(word)},
                            None, None)
            index += 2
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
            for later in later_words)
        details = {"glob_word": plain_word(word), "name": name, "program": program}
        if option_follows:
            return details, None, None
        whole_command = command_with_double_dash_before_word(
            command, commands, command_index, program_index + 1 + index,
            deadline, clock)
        respelled_search = None
        if command_is_this_search_alone(command, commands, words):
            respelled_search = search_spelled(
                words[:program_index + 1] + arguments[:index] + ["--"] + arguments[index:],
                words.redirects)
        return details, whole_command, respelled_search
    return None


def search_spelled(words, redirects):
    """Return shell text for the search's words and redirections, -- left unquoted."""
    return " ".join(
        [word if word == "--" else shell_spelling_of_word(word) for word in words]
        + [operator + shell_spelling_of_word(target) for operator, target in redirects])


def shell_tokens(text):
    lexer = shlex.shlex(text, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    return list(lexer)


def command_is_this_search_alone(command, commands, words):
    """Return whether command is the one search and nothing else.

    The search alone runs elsewhere, or does less, when anything stood around it: a cd before
    it, a pipe after it, a loop, a group's redirection, or an & that runs it in the background.
    """
    if len(commands) != 1:
        return False
    # Spelled from the same words, the two differ in tokens only where the command holds more.
    try:
        return shell_tokens(command) == shell_tokens(search_spelled(words, words.redirects))
    except ValueError:
        return False


def resolve_directory(base, target):
    if os.path.isabs(target):
        return os.path.normpath(target)
    return os.path.normpath(os.path.join(base, target))


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
                      if program_index + 1 < len(words) else os.path.expanduser("~"))
            target_path = plain_word(shell_reader.shell_word_tilde_prefix_expand_as_bash_would(target))
            target_is_absolute = os.path.isabs(target_path)
            if (UNRESOLVABLE_DIRECTORY_PATTERN.search(target)
                    or word_holds_unquoted_glob(target)
                    or (directory is None and not target_is_absolute)):
                directory = None
            else:
                directory = resolve_directory(directory or "/", target_path)
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
    # A suggested command has every search fixed, so running it is not refused again; when a
    # later search cannot be fixed by --, no command is given. When the budget runs out first,
    # the suggestion keeps the fixes made so far.
    deadline = clock() + EXPANSION_BUDGET_SECONDS
    refused = first_refused_search(command, payload_cwd, deadline, clock)
    if refused is None:
        return None
    details, whole_command, respelled_search = refused
    if "option" in details:
        return REFUSAL_OF_OPTION_VALUE_TEMPLATE.format(**details)
    if whole_command is None:
        if respelled_search is None:
            return REFUSAL_WITHOUT_COMMAND_TEMPLATE.format(**details)
        return REFUSAL_WITH_COMMAND_TEMPLATE.format(
            accepted_command=respelled_search, **details)
    while clock() <= deadline:
        try:
            further = first_refused_search(whole_command, payload_cwd,
                                           deadline, clock)
        except (ExpansionBudgetSpent, OSError, ValueError, re.error):
            break  # Keep the existing refusal when the remaining budget cannot fix further searches.
        if further is None:
            break
        if further[1] is None:
            return REFUSAL_WITHOUT_COMMAND_TEMPLATE.format(**details)
        whole_command = further[1]
    return REFUSAL_WITH_COMMAND_TEMPLATE.format(
        accepted_command=whole_command, **details)


def unchecked_hook_output(why, report=None):
    """Return the PreToolUse JSON that lets a command through and says why it was not checked.

    report, when given, is the words to tell the user or the dispatching agent.
    """
    message = (
        f"The search-file-argument guard let this command through without checking it, and "
        f"the command has run: {why}\n"
        f"Look at the files the command's file patterns match. If one of them names a file "
        f"whose name starts with -, the search read that name as an option, so run the search "
        f"again with -- before the file names; if none does, the search ran as written.")
    if report is not None:
        message += "\n" + shell_reader.report_to_user_or_dispatching_agent_instruction_build(report)
    return json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "additionalContext": message,
    }})


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
    except ExpansionBudgetSpent:
        print(unchecked_hook_output(
            f"expanding its file patterns took longer than the guard's "
            f"{EXPANSION_BUDGET_SECONDS:.0f}-second limit, which keeps the guard inside its hook "
            f"timeout. The limit is deliberate; nothing failed."))
        return 0
    except (OSError, ValueError, re.error) as error:
        print(unchecked_hook_output(
            f"the guard failed on it ({type(error).__name__}: {error}).",
            f"\"The search-file-argument guard failed on a command and let it through unchecked "
            f"({type(error).__name__}: {error}).\" After those words, "
            f"{shell_reader.COMMAND_AS_FENCED_CODE_BLOCK_INSTRUCTION}."))
        return 0
    if refusal:
        deny(refusal)
    return 0


if __name__ == "__main__":
    sys.exit(main())
