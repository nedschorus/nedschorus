#!/usr/bin/env python3
"""PreToolUse soft-block on replacing the whole of an existing GHI-MD.

WHAT IT REFUSES: a Write tool call on an existing GHI-MD, and a Bash command
that writes over one with `cp`, `mv`, `tee` or a truncating redirection (`>`,
`>|`, `&>`, `N>`, `>&` to a file). A GHI-MD here is a file named
`<number>-*.md` directly in the `docs/issues/` directory of a checkout, so the
copies under `docs/issues/queue/`, `docs/issues/archived/` and inside
`cold-read-records/` are not GHI-MDs. A file that does not exist yet is not
replaced, so writing a new GHI-MD passes.

A whole-file replacement puts the agent's copy over every change merged into
the GHI-MD on main after that copy was written. The Edit tool changes one
passage and keeps the rest, so it is not refused.

CLEARING A REFUSAL: the agent writes its reason into the marker file the
refusal names, at the root of the agent-session's checkout, and runs the
command again. The marker clears that one call and is consumed by it.

WHAT IT LETS THROUGH, because nothing is replaced: `tee -a`, `>>` and `&>>`,
which append; `cp` or `mv` of a GHI-MD to another place; `cp -T` or `mv -T`
onto a directory, which fails.

WHAT IT CANNOT SEE: other programs that write files, such as `install`,
`rsync`, `dd`, `sed -i`, `git checkout -- <path>`, `git restore`, or a Python
or heredoc script; a target named through a variable, a glob or a command
substitution, which is read as written; a relative target after a `cd` whose
directory is a variable or another unreadable word, which passes; and the same
command limits as the other Bash guards that use the shared shell module
(`sh -c`, `eval`, `ssh`). A target is resolved against the agent-session's
working directory and each literal `cd` before it, as bash would.
"""

import importlib.util
import json
import os
import re
import sys
from pathlib import Path

_HOOKS_DIRECTORY = Path(__file__).resolve().parent
_REPOSITORY_ROOT = _HOOKS_DIRECTORY.parents[1]


def _load(module_name, path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


shell_reader = _load(
    "shell_command_tree_sitter_bash_reader_common",
    _REPOSITORY_ROOT / "nc-systems" / "general-tools"
    / "shell-command-tree-sitter-bash-reader-common.py")
_marker_common = _load("guard_approval_marker_common",
                       _HOOKS_DIRECTORY / "guard-approval-marker-common.py")
# The instruction-file guard's checkout-root and marker-root lookups, so both
# guards place their marker files at the same root.
_instruction_file_guard = _load("instruction_file_guard",
                                _HOOKS_DIRECTORY / "instruction-file-guard.py")

REASON_MARKER_NAME = ".ghi-md-whole-file-replacement-reason"
GHI_MD_DIRECTORY_PARTS = ("docs", "issues")
GHI_MD_NAME_PATTERN = re.compile(r"^\d+-.*\.md$")

# Messages to agents follow docs/nedschorus-wiki/nedschorus-how-to-write-an-agent-facing-message-such-as-a-hook-refusal-or-script-error.md.
REFUSAL = (
    "Refused: this command replaces the whole GHI-MD {path}, which can undo changes merged "
    "into it on main after your copy was written.\n"
    "Change the GHI-MD with the Edit tool instead, one passage at a time, so main's other "
    "changes stay.\n"
    "If you mean to replace the whole file, write your reason into {marker_path} and run the "
    "command again."
)

PARSER_UNAVAILABLE_NEXT_STEP_LINES = (
    "If the command wrote over an existing GHI-MD, a docs/issues/<number>-*.md file, with cp, "
    "mv, tee or a > redirection, and you did not mean to replace the whole file, run git diff "
    "origin/main -- <that file>: each difference you did not mean to make is a change on main "
    "that the command undid, so put it back with the Edit tool.")

# Read from `cp --help` and `mv --help`, GNU coreutils 9.4: the options whose
# value may stand as the next word. Other long options take theirs after `=`.
COPY_OR_MOVE_SHORT_OPTIONS_TAKING_A_VALUE = "tS"
COPY_OR_MOVE_LONG_OPTIONS_TAKING_A_VALUE = ("--target-directory", "--suffix")
TRUNCATING_REDIRECTION_PATTERN = re.compile(r"(?:\d*|&)>\|?")
# `>&word` and `N>&word` write to the file word unless word is a descriptor or `-`.
DUPLICATING_REDIRECTION_PATTERN = re.compile(r"\d*>&")


def is_existing_ghi_md(path):
    """Whether path is an existing file named <number>-*.md in a checkout's docs/issues/."""
    if not GHI_MD_NAME_PATTERN.match(path.name) or not path.is_file():
        return False
    return (_instruction_file_guard.checkout_directory_parts(path)
            == GHI_MD_DIRECTORY_PARTS)


def path_in(directory, word):
    """The path word names, read from directory, or None when directory is unknown."""
    word = shell_reader.shell_word_tilde_prefix_expand_as_bash_would(word)
    if os.path.isabs(word):
        return Path(os.path.normpath(word))
    if directory is None:
        return None
    return Path(os.path.normpath(os.path.join(directory, word)))


def copy_or_move_targets(arguments, directory):
    """The files a `cp` or `mv` with these arguments writes, as paths."""
    target_directory = None
    no_target_directory = False
    operands = []
    index = 0
    while index < len(arguments):
        word = arguments[index]
        index += 1
        if word == "--":
            operands.extend(arguments[index:])
            break
        if word.startswith("--"):
            name, has_value, value = word.partition("=")
            if name == "--no-target-directory":
                no_target_directory = True
            elif name in COPY_OR_MOVE_LONG_OPTIONS_TAKING_A_VALUE:
                if not has_value:
                    value = arguments[index] if index < len(arguments) else ""
                    index += 1
                if name == "--target-directory":
                    target_directory = value
            continue
        if word.startswith("-") and len(word) > 1:
            for position, letter in enumerate(word[1:], start=1):
                if letter == "T":
                    no_target_directory = True
                if letter in COPY_OR_MOVE_SHORT_OPTIONS_TAKING_A_VALUE:
                    value = word[position + 1:]
                    if not value:
                        value = arguments[index] if index < len(arguments) else ""
                        index += 1
                    if letter == "t":
                        target_directory = value
                    break
            continue
        operands.append(word)
    if target_directory is not None:
        destination, sources = path_in(directory, target_directory), operands
    elif len(operands) >= 2:
        destination, sources = path_in(directory, operands[-1]), operands[:-1]
    else:
        return []
    if destination is None:
        return []
    if target_directory is None and (no_target_directory or not destination.is_dir()):
        return [destination]
    return [destination / os.path.basename(os.path.normpath(source)) for source in sources]


def tee_targets(arguments, directory):
    """The files a `tee` with these arguments writes over, as paths; none when it appends."""
    operands = []
    for index, word in enumerate(arguments):
        if word == "--":
            operands.extend(arguments[index + 1:])
            break
        if word == "--append" or (word.startswith("-") and not word.startswith("--")
                                  and "a" in word[1:]):
            return []
        if word.startswith("-") and len(word) > 1:
            continue
        operands.append(word)
    return [path for path in (path_in(directory, word) for word in operands) if path]


def redirection_targets(redirects, directory):
    """The files these redirections write over, as paths."""
    targets = []
    for operator, target in redirects:
        truncates = TRUNCATING_REDIRECTION_PATTERN.fullmatch(operator) or (
            DUPLICATING_REDIRECTION_PATTERN.fullmatch(operator)
            and target and not target.isdigit() and target != "-")
        if truncates and target:
            path = path_in(directory, target)
            if path is not None:
                targets.append(path)
    return targets


def replaced_paths_in_command(command, working_directory):
    """Every path the command's cp, mv, tee and redirections write over, in order."""
    commands = shell_reader.simple_commands(command)
    # A child shell's cd does not change the directory of the shell around it.
    directories = {(): working_directory}
    paths = []
    for words in commands:
        enclosing = words.child_shell
        while enclosing not in directories:
            enclosing = enclosing[:-1]
        directory = directories[enclosing]
        paths.extend(redirection_targets(words.redirects, directory))
        index, _ = shell_reader.simple_command_program_index_skipping_wrappers(words)
        if index is None:
            continue
        arguments = words[index + 1:]
        if shell_reader.is_program(words[index], "cd"):
            target = arguments[0] if arguments else os.path.expanduser("~")
            directory = (None if target == "-" or re.search(r"[$`*?\[]", target)
                         else path_in(directory, target))
            directories[words.child_shell] = None if directory is None else str(directory)
        elif shell_reader.is_program(words[index], "cp") or shell_reader.is_program(
                words[index], "mv"):
            paths.extend(copy_or_move_targets(arguments, directory))
        elif shell_reader.is_program(words[index], "tee"):
            paths.extend(tee_targets(arguments, directory))
    return paths


def replaced_ghi_md(candidates):
    """The first existing GHI-MD among candidate paths, or None."""
    return next((path for path in candidates if is_existing_ghi_md(path)), None)


def ghi_md_replaced_by_command(command, working_directory):
    """The first existing GHI-MD the command writes over, or None; reads no marker file."""
    return replaced_ghi_md(replaced_paths_in_command(command, working_directory))


def deny(reason):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }}))


def main(stdin=sys.stdin):
    try:
        payload = json.load(stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(payload, dict):
        return 0
    tool_name = payload.get("tool_name")
    tool_input = payload.get("tool_input") or {}
    working_directory = payload.get("cwd")
    if not isinstance(working_directory, str) or not working_directory:
        working_directory = os.getcwd()
    if tool_name == "Write":
        file_path = tool_input.get("file_path") or ""
        candidates = [path_in(working_directory, file_path)] if file_path else []
    elif tool_name == "Bash":
        command = tool_input.get("command") or ""
        try:
            candidates = replaced_paths_in_command(command, working_directory)
        except shell_reader.ShellParserUnavailable as error:
            print(shell_reader.parser_unavailable_hook_output(
                "The GHI-MD whole-file replacement soft-block", error,
                PARSER_UNAVAILABLE_NEXT_STEP_LINES))
            return 0
    else:
        return 0
    replaced = replaced_ghi_md(candidates)
    if replaced is None:
        return 0
    marker_path = _instruction_file_guard.marker_root(payload, str(replaced)) / REASON_MARKER_NAME
    if _marker_common.consume_approval_marker(marker_path):
        return 0
    deny(REFUSAL.format(path=replaced, marker_path=marker_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
