#!/usr/bin/env python3
"""Read a shell command with tree-sitter-bash and return its simple commands.

The project's Bash guards ask one question of a command line: which programs
does it run, with which words? A hand-written reader gets ordinary bash wrong
(a `cd` inside `( ... )` changing the directory of later commands, `if git push
-f …; then` read as a command named `if`, a heredoc body read as commands).
tree-sitter-bash is the parser Claude Code and the Codex CLI use; this module
walks its tree and hands each simple command back as its words.

Heredoc bodies are taken out of the command line before it is parsed, by
bash's own rules, and each `<<DELIMITER` stands in the parse as a plain input
redirection; everything else is read from tree-sitter-bash's nodes, which
handle the few groupings the grammar gets wrong.

simple_commands collects what it can, from an incomplete or invalid command
too, so a guard can refuse what it finds. Nothing it returns proves a command
safe: words keep expansions such as `$HOME` as written, and a command built at
run time, by `eval` or a variable holding a program name, is not seen.

tree-sitter and tree-sitter-bash are compiled libraries, installed per user
from compiled-python-libraries-pinned-requirements.txt beside this file. When
they are missing, the first use installs them. ShellParserUnavailable means
the install failed: the guard lets the command through and says so with
parser_unavailable_hook_output, which asks for the user to be told.
ShellCommandUnreadable, a kind of it, means this module failed on the command;
simple_commands raises no other error, and the guard lets the command through
and says the reader failed on it. When the
install succeeds but this process still holds a copy it could not use,
the command is read in a new Python process, which loads the installed copy. A failed
install is tried again after ten minutes, so that each command does not wait
for its own failing install.

Load it by path, under the snake_case form of its file name:

    spec = importlib.util.spec_from_file_location(
        "shell_command_tree_sitter_bash_reader_common", <path>)
"""

# Deferred annotations let the module load on the Mac's system Python 3.9.
from __future__ import annotations

import codecs
import collections
import importlib
import json
import os
import re
import site
import socket
import subprocess
import sys
import time
from pathlib import Path

REQUIREMENTS_FILE = Path(__file__).resolve().with_name(
    "compiled-python-libraries-pinned-requirements.txt")
# The Bash guards run in parallel with a 30-second hook timeout; a cached wheel installs in about a second.
INSTALL_TIMEOUT_SECONDS = 8
INSTALL_RETRY_SECONDS = 600
STATE_DIRECTORY = Path.home() / ".cache" / "nedschorus-shell-command-reader"
INSTALL_LOCK_FILE_NAME = "install.lock"
INSTALL_FAILURE_FILE_NAME = "last-install-failure.txt"

RECURSION_LIMIT_FOR_DEEP_NESTING = 100_000

# Nodes whose commands run in a child shell, so a cd inside them stays inside.
CHILD_SHELL_NODE_TYPES = {"command_substitution", "process_substitution", "subshell"}
# Nodes that are a command name followed by words, as a guard reads them.
SIMPLE_COMMAND_NODE_TYPES = {"command", "declaration_command", "unset_command"}
REDIRECT_NODE_TYPES = {"file_redirect", "heredoc_redirect", "herestring_redirect"}
# Nodes that only group commands; tree-sitter-bash's grouping of these is not trusted.
SEQUENCE_NODE_TYPES = {"pipeline", "list", "redirected_statement", "negated_command"}
PIPE_OPERATORS = {"|", "|&"}
# Characters a backslash keeps literal inside double quotes; before any other, the backslash stays.
DOUBLE_QUOTE_ESCAPABLE = set('"\\$`')


# A decoded $'...' word may hold bytes that are not UTF-8, and text from a JSON payload may
# hold lone surrogates. This handler keeps both through every decode and encode in this
# module: a byte that is not UTF-8 stands as U+DC80 to U+DCFF, as surrogateescape writes
# it, and any other surrogate as surrogatepass writes it.
SHELL_TEXT_ERRORS = "nedschorus-shell-command-text"


def _shell_text_errors(error):
    if isinstance(error, UnicodeEncodeError):
        out = bytearray()
        for character in error.object[error.start:error.end]:
            point = ord(character)
            out += (bytes([point - 0xDC00]) if 0xDC80 <= point <= 0xDCFF
                    else character.encode("utf-8", "surrogatepass"))
        return bytes(out), error.end
    surrogate = error.object[error.start:error.start + 3]
    # U+DC80 to U+DCFF stand for single bytes, so their own three bytes stay three bytes.
    if len(surrogate) == 3 and surrogate[0] == 0xED and 0xA0 <= surrogate[1] <= 0xBF \
            and 0x80 <= surrogate[2] <= 0xBF and not 0xB2 <= surrogate[1] <= 0xB3:
        return surrogate.decode("utf-8", "surrogatepass"), error.start + 3
    return chr(0xDC00 + error.object[error.start]), error.start + 1


codecs.register_error(SHELL_TEXT_ERRORS, _shell_text_errors)


class ShellParserUnavailable(Exception):
    """tree-sitter-bash could not be imported, and installing it failed.

    install_output holds what the install printed, or why it did not run.
    """

    def __init__(self, install_output):
        super().__init__(install_output)
        self.install_output = install_output


class ShellCommandUnreadable(ShellParserUnavailable):
    """This module failed on the command; install_output says how.

    A kind of ShellParserUnavailable, so a guard that lets a command through
    when the parser is missing does the same here.
    """


class ShellParserInstalledForANewProcess(ShellParserUnavailable):
    """The install succeeded, but this process still holds the unusable copy it loaded first.

    A compiled module cannot be replaced inside a running process; a new
    process loads the installed copy, so simple_commands reads the command
    there.
    """


class Heredoc:
    """One heredoc: its body as written, and whether the shell expands it."""

    def __init__(self, body, expanded, delimiter=""):
        self.body = body
        self.expanded = expanded
        self.delimiter = delimiter

    def __repr__(self):
        return f"Heredoc({self.body!r}, expanded={self.expanded})"


SUBSTITUTION = "substitution"
PIPELINE_STAGE = "pipeline stage"
SUBSHELL = "subshell"


class ChildShell(collections.namedtuple(
        "ChildShell", "offset kind shell_pipeline_first_stage_byte_offset", defaults=(None,))):
    """One child shell a command runs in.

    offset is where it starts in the text read. kind is SUBSTITUTION for a
    command or process substitution, whose output becomes words of another
    command, PIPELINE_STAGE for a stage of a pipeline of two or more, and
    SUBSHELL for ( ... ). For a pipeline stage,
    shell_pipeline_first_stage_byte_offset is where its pipeline's first stage
    starts, the same for every stage of one pipeline, and first_stage says
    whether the stage is that first one. Two child shells are the same only
    when all three fields agree, so a stage and the subshell that starts it are
    different child shells.
    """

    __slots__ = ()

    @property
    def first_stage(self):
        return (self.kind == PIPELINE_STAGE
                and self.offset == self.shell_pipeline_first_stage_byte_offset)

    def placed(self, place):
        """Return this child shell with each of its offsets passed through place."""
        first = self.shell_pipeline_first_stage_byte_offset
        return ChildShell(place(self.offset), self.kind, None if first is None else place(first))


class SimpleCommand(list):
    """The words of one simple command, assignments first, redirections left out.

    child_shell holds the enclosing child shells, outermost first, as ChildShell
    values: offsets, each with its kind; () is the command line's own shell. A
    command whose child_shell starts with another's runs inside it, so it sees
    that shell's cd but its own cd does not leak out. redirects holds
    (operator, target) pairs, heredocs the heredocs fed to this command or to
    the pipeline that starts on its heredoc line.
    """

    def __init__(self, words, child_shell, redirects, heredocs):
        super().__init__(words)
        self.child_shell = child_shell
        self.redirects = redirects
        self.heredocs = heredocs

    def inside_substitution(self):
        """Return whether the command runs inside a command or process substitution."""
        return any(shell.kind == SUBSTITUTION for shell in self.child_shell)


def is_program(word, name):
    """Return whether word runs the program name, given bare or by path."""
    return word == name or word.endswith("/" + name)


ENVIRONMENT_ASSIGNMENT_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")


class Wrapper:
    """A program that runs the command written after it.

    options_with_a_value are the options, short or long, that take the next word
    as their value; operands is how many words, such as timeout's duration or
    flock's lock file, come after the options and before the command;
    passes_standard_input says whether the command reads the wrapper's standard
    input: xargs reads that input itself, as the arguments it adds.
    """

    def __init__(self, options_with_a_value=(), operands=0, passes_standard_input=True):
        self.options_with_a_value = set(options_with_a_value)
        self.operands = operands
        self.passes_standard_input = passes_standard_input


# flock's -c and env's -S take a command line as their value; the command they run is not
# found, and the words after the value are taken as the program.
WRAPPERS = {
    # sudo's -h takes a host only when attached, as in -hhost; alone it asks for help.
    "sudo": Wrapper({"-u", "-g", "-C", "-U", "-D", "-p", "-r", "-t", "-R", "-T", "-c", "-a",
                     "--user", "--group", "--close-from", "--other-user", "--chdir", "--host",
                     "--prompt", "--role", "--type", "--chroot", "--command-timeout"}),
    "env": Wrapper({"-u", "-C", "-S", "-a", "-f", "-P", "--unset", "--chdir", "--split-string",
                    "--argv0", "--file"}),
    "timeout": Wrapper({"-s", "-k", "--signal", "--kill-after"}, operands=1),
    "nice": Wrapper({"-n", "--adjustment"}),
    "stdbuf": Wrapper({"-i", "-o", "-e", "--input", "--output", "--error"}),
    "nohup": Wrapper(),
    "exec": Wrapper({"-a"}),
    "command": Wrapper(),
    "time": Wrapper({"-f", "-o", "--format", "--output"}),
    "setsid": Wrapper(),
    "flock": Wrapper({"-w", "-E", "-c", "--timeout", "--wait", "--conflict-exit-code",
                      "--command"}, operands=1),
    "caffeinate": Wrapper({"-t", "-w"}),
    "xargs": Wrapper({"-a", "-d", "-E", "-I", "-J", "-L", "-n", "-P", "-R", "-s", "-S", "--arg-file",
                      "--delimiter", "--max-lines", "--max-args", "--max-procs",
                      "--max-chars", "--process-slot-var"}, passes_standard_input=False),
}


def simple_command_program_index_skipping_wrappers(words):
    """Return (index, receives_standard_input) for the program a simple command runs.

    The program is the first word after environment assignments and after
    wrappers such as sudo, timeout and xargs with their options and operands;
    a later word, such as the file of `tee /tmp/bash`, is not the program.
    index is None when no word is left to be the program. receives_standard_input
    is false when a wrapper, such as xargs, keeps its standard input from the
    program.
    """
    index, receives_standard_input, _ = _wrappers_read(words)
    return index, receives_standard_input


def simple_command_wrapper_options_and_values_parsed_from_words(words):
    """Return (wrapper, option, value) for each option given to the wrappers before the program.

    wrapper is the wrapper's name without its directory, as in ("env", "-C",
    "/w") for `env -u X -C /w git push`. value is None for an option that takes
    none, and an option written --name=value is split at the =.
    """
    return _wrappers_read(words)[2]


def _wrappers_read(words):
    index, receives_standard_input, options = 0, True, []
    while index < len(words):
        word = words[index]
        if ENVIRONMENT_ASSIGNMENT_PATTERN.match(word):
            index += 1
            continue
        name = word.rsplit("/", 1)[-1]
        wrapper = WRAPPERS.get(name)
        if wrapper is None:
            return index, receives_standard_input, options
        receives_standard_input = receives_standard_input and wrapper.passes_standard_input
        index = _index_after_options(words, index + 1, name, wrapper, options)
        if wrapper.operands:
            # Options may follow the operand too, as in timeout 60 --signal=KILL.
            index = _index_after_options(words, index + wrapper.operands, name, wrapper, options)
    return None, receives_standard_input, options


def _index_after_options(words, index, name, wrapper, options):
    while index < len(words) and words[index].startswith("-"):
        option = words[index]
        if option in wrapper.options_with_a_value:
            options.append((name, option, words[index + 1] if index + 1 < len(words) else None))
            index += 2
            continue
        if option.startswith("--") and "=" in option:
            options.append((name, *option.split("=", 1)))
        else:
            options.append((name, option, None))
        index += 1
    return index


def install_compiled_libraries(runner=subprocess.run):
    """Install the pinned requirements per user; return what pip printed, or raise ShellParserUnavailable."""
    command = [sys.executable, "-m", "pip", "install", "--user", "--break-system-packages",
               "--disable-pip-version-check", "--quiet", "-r", str(REQUIREMENTS_FILE)]
    try:
        completed = runner(command, capture_output=True, text=True, timeout=INSTALL_TIMEOUT_SECONDS,
                           stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError) as error:
        raise ShellParserUnavailable(f"`{' '.join(command)}` did not finish: {error}") from error
    printed = (completed.stdout + completed.stderr).strip()
    if completed.returncode != 0:
        raise ShellParserUnavailable(
            f"`{' '.join(command)}` exited {completed.returncode}: {printed or '(no output)'}")
    return printed


def import_tree_sitter_bash():
    """Return (tree_sitter, tree_sitter_bash), raising ImportError when either is missing or unusable."""
    try:
        import tree_sitter
        import tree_sitter_bash
        # A copy at another version can import and still fail here; installing the pinned one fixes it.
        tree_sitter.Parser(tree_sitter.Language(tree_sitter_bash.language()))
    except ImportError:
        raise
    except Exception as error:
        raise ImportError(f"tree-sitter-bash is installed but cannot be used: {error!r}") from error
    return tree_sitter, tree_sitter_bash


FRESH_PROCESS_IMPORT_CHECK = (
    "import tree_sitter, tree_sitter_bash; "
    "tree_sitter.Parser(tree_sitter.Language(tree_sitter_bash.language()))")


def imports_in_a_fresh_process(runner=subprocess.run):
    """Return whether a new Python process can import and use tree-sitter-bash."""
    try:
        completed = runner([sys.executable, "-c", FRESH_PROCESS_IMPORT_CHECK], capture_output=True,
                           timeout=INSTALL_TIMEOUT_SECONDS, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        return False
    return completed.returncode == 0


def load_parser(importer=import_tree_sitter_bash, installer=install_compiled_libraries,
                clock=time.time, fresh_process_check=imports_in_a_fresh_process):
    """Return a tree-sitter Parser for bash, installing the libraries when they are missing."""
    try:
        tree_sitter, tree_sitter_bash = importer()
    except ImportError:
        tree_sitter, tree_sitter_bash = _install_then_import(importer, installer, clock,
                                                             fresh_process_check)
    return tree_sitter.Parser(tree_sitter.Language(tree_sitter_bash.language()))


def _forget_loaded_copies():
    # A copy that imported but could not be used stays cached and would be returned again.
    for name in [name for name in sys.modules
                 if name.split(".")[0] in ("tree_sitter", "tree_sitter_bash")]:
        del sys.modules[name]


def _install_then_import(importer, installer, clock, fresh_process_check):
    # The guards run in parallel on each command, so they take turns, and only the first installs.
    try:
        STATE_DIRECTORY.mkdir(parents=True, exist_ok=True)
        lock = open(STATE_DIRECTORY / INSTALL_LOCK_FILE_NAME, "w")
    except OSError as error:
        raise ShellParserUnavailable(f"could not open the install lock in {STATE_DIRECTORY}: {error}") \
            from error
    with lock:
        try:
            import fcntl
            fcntl.flock(lock, fcntl.LOCK_EX)
        except (ImportError, OSError):
            pass  # Without the lock, two installs may run; each installs the same pinned files.
        # Another guard may have installed into a user site this process did not have at start-up.
        _refresh_import_paths()
        _forget_loaded_copies()
        try:
            return importer()
        except ImportError:
            pass
        failure_record = STATE_DIRECTORY / INSTALL_FAILURE_FILE_NAME
        try:
            if clock() - failure_record.stat().st_mtime < INSTALL_RETRY_SECONDS:
                # Each guard on each command would otherwise wait for its own failing install.
                raise ShellParserUnavailable(failure_record.read_text(encoding="utf-8"))
        except OSError:
            pass
        try:
            installer()
            _refresh_import_paths()
            _forget_loaded_copies()
            try:
                modules = importer()
            except ImportError as error:
                if fresh_process_check():
                    raise ShellParserInstalledForANewProcess(
                        f"the install finished; this process still holds the copy it could not "
                        f"use: {error}") from error
                raise ShellParserUnavailable(
                    f"the install finished but importing still fails: {error}") from error
        except ShellParserInstalledForANewProcess:
            _forget_failure(failure_record)
            raise
        except ShellParserUnavailable as error:
            try:
                failure_record.write_text(error.install_output, encoding="utf-8")
            except OSError:
                pass
            raise
        _forget_failure(failure_record)
        return modules


def _forget_failure(failure_record):
    try:
        failure_record.unlink()
    except OSError:
        pass


def _refresh_import_paths():
    # A user site that did not exist at start-up is not on sys.path yet.
    site.addsitedir(site.getusersitepackages())
    importlib.invalidate_caches()


_parser = None


def parser():
    global _parser
    if _parser is None:
        _parser = load_parser()
    return _parser


def _session_unattended(environment):
    return bool(environment.get("NEDSCHORUS_SESSION_REINCARNATION_OWNED_BY_CALLER")
                or environment.get("CLAUDE_CODE_SESSION_ATTENDED") == "0")


def parser_unavailable_hook_output(guard_name, error, environment=os.environ):
    """Return the PreToolUse JSON that lets the command through and says it was not checked."""
    host = socket.gethostname().split(".")[0]
    if isinstance(error, ShellCommandUnreadable):
        report = (
            f"in these words: \"{guard_name} let a command through unchecked on {host}, because "
            f"the shell command reader failed on it ({error.install_output}).\" Quote the "
            f"command after those words, then say whether it did what {guard_name} exists to "
            f"stop, what you undid, and what you could not undo.")
        if _session_unattended(environment):
            tell = (f"If you are a subagent, tell the agent that dispatched you, {report}\n"
                    f"No user attends this agent-session, so do not tell the user; if you are "
                    f"not a subagent, go on with your task.")
        else:
            tell = (f"Tell the user, or, if you are a subagent, the agent that dispatched you, "
                    f"{report}")
        message = (
            f"{guard_name} let this command through without checking it, and the command has "
            f"run: the shell command reader ({Path(__file__).name}) failed on it on {host} "
            f"({error.install_output}).\n"
            f"Look at what the command did. If it did what {guard_name} exists to stop, undo "
            f"that now where you can.\n"
            f"{tell}")
        return json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": message,
        }})
    not_checked = (f"{guard_name} let this command through without checking it: the shell parser "
                   f"tree-sitter-bash is missing on {host}, and installing it failed.")
    if _session_unattended(environment):
        message = f"{not_checked}\nNo user attends this agent-session, so do not tell the user."
    else:
        install = f"python3 -m pip install --user --break-system-packages -r {REQUIREMENTS_FILE}"
        # The user sits at the Mac, and reaches ned-box over ssh.
        by_hand = (f"from your Mac, run: ssh nedlern@ned-box '{install}'" if host == "ned-box"
                   else f"run on {host}: {install}")
        message = (
            f"{not_checked}\n"
            f"Tell the user, or, if you are a subagent, the agent that dispatched you, in these "
            f"words: \"tree-sitter-bash is missing on {host} and could not be installed, so the "
            f"project's Bash guards are not checking commands there. To install it by hand, "
            f"{by_hand}\"\n"
            f"Then pass on what the install printed, quoted as it is: {error.install_output}\n"
            f"Later commands are let through unchecked too, each with this message, until an "
            f"install succeeds; the first command after {INSTALL_RETRY_SECONDS // 60} minutes "
            f"have passed tries the install again.")
    return json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "additionalContext": message,
    }})


def _text(node):
    return node.text.decode("utf-8", SHELL_TEXT_ERRORS)


def _unescape_unquoted(text, glob_markers):
    """Remove the shell's backslashes from unquoted text, marking the glob characters left unescaped."""
    out = []
    index = 0
    while index < len(text):
        char = text[index]
        if char == "\\":
            if text[index + 1:index + 2] == "\n":
                index += 2
                continue
            out.append(text[index + 1:index + 2])
            index += 2
            continue
        out.append(glob_markers.get(char, char) if glob_markers else char)
        index += 1
    return "".join(out)


def _unescape_double_quoted(text):
    out = []
    index = 0
    while index < len(text):
        char = text[index]
        if char == "\\" and index + 1 < len(text):
            following = text[index + 1]
            if following == "\n":
                index += 2
                continue
            if following in DOUBLE_QUOTE_ESCAPABLE:
                out.append(following)
                index += 2
                continue
        out.append(char)
        index += 1
    return "".join(out)


def word_value(node, glob_markers=None):
    """Return a word as the shell passes it, with quotes removed and expansions kept as written."""
    kind = node.type
    if kind == "raw_string":
        return _text(node)[1:-1]
    if kind == "ansi_c_string":
        return _ansi_c_decoded(_text(node)[2:-1])
    if kind in ("string", "translated_string"):
        string = node if kind == "string" else next(
            (child for child in node.children if child.type == "string"), None)
        if string is None:
            return _text(node)
        pieces = []
        # tree-sitter-bash leaves some characters, such as a newline, between its child nodes.
        position = string.start_byte + 1
        source = string.text
        for child in string.children:
            if child.type == '"':
                continue
            gap = source[position - string.start_byte:child.start_byte - string.start_byte]
            pieces.append(_unescape_double_quoted(gap.decode("utf-8", SHELL_TEXT_ERRORS)))
            if child.type == "string_content":
                pieces.append(_unescape_double_quoted(_text(child)))
            else:
                pieces.append(_text(child))
            position = child.end_byte
        closing = string.end_byte - 1
        pieces.append(_unescape_double_quoted(
            source[position - string.start_byte:closing - string.start_byte]
            .decode("utf-8", SHELL_TEXT_ERRORS)))
        return "".join(pieces)
    if kind == "concatenation":
        return "".join(word_value(child, glob_markers) for child in node.children)
    if kind in ("word", "number"):
        return _unescape_unquoted(_text(node), glob_markers)
    # Expansions and substitutions are kept as written; the shell decides their value at run time.
    return _text(node)


def _utf8_bytes_bash_writes(value):
    """Return the bytes bash writes for \\u or \\U with this value, in a UTF-8 locale.

    bash encodes any value below 2**31 in UTF-8's original form of up to six
    bytes, surrogates and values above 0x10FFFF included, and writes nothing
    for a larger one.
    """
    if value < 0x80:
        return bytes([value])
    for length, limit in ((2, 0x800), (3, 0x10000), (4, 0x200000), (5, 0x4000000),
                          (6, 0x80000000)):
        if value < limit:
            tail = []
            for _ in range(length - 1):
                tail.insert(0, 0x80 | (value & 0x3F))
                value >>= 6
            return bytes([((0xFF << (8 - length)) & 0xFF) | value] + tail)
    return b""


ANSI_C_SIMPLE_ESCAPES = {"a": "\a", "b": "\b", "e": "\x1b", "E": "\x1b", "f": "\f", "n": "\n",
                         "r": "\r", "t": "\t", "v": "\v", "\\": "\\", "'": "'", '"': '"', "?": "?"}
ANSI_C_NUMERIC_ESCAPE_PATTERN = re.compile(
    r"([0-7]{1,3})|x([0-9A-Fa-f]{1,2})|u([0-9A-Fa-f]{1,4})|U([0-9A-Fa-f]{1,8})")


def _ansi_c_decoded(text):
    """Return the text inside $'...' as bash decodes it; a decoded NUL ends the word.

    \\u and \\U are written as bash writes them in a UTF-8 locale; bytes that are
    not UTF-8 stay bytes, held as SHELL_TEXT_ERRORS holds them.
    """
    out = bytearray()
    index = 0
    while index < len(text):
        character = text[index]
        if character != "\\" or index + 1 >= len(text):
            out += character.encode("utf-8", SHELL_TEXT_ERRORS)
            index += 1
            continue
        escape = text[index + 1]
        numeric = ANSI_C_NUMERIC_ESCAPE_PATTERN.match(text, index + 1)
        if escape in "uU" and numeric and (numeric.group(3) or numeric.group(4)):
            out += _utf8_bytes_bash_writes(int(numeric.group(3) or numeric.group(4), 16))
            index = numeric.end()
        elif escape in ANSI_C_SIMPLE_ESCAPES:
            out += ANSI_C_SIMPLE_ESCAPES[escape].encode()
            index += 2
        elif escape == "c" and index + 2 < len(text):
            # \cX is the control character X; \c\\ is written with its backslash doubled.
            control = text[index + 2]
            out.append(0x7F if control == "?" else ord(control) & 0x1F)
            index += 4 if text[index + 2:index + 4] == "\\\\" else 3
        elif numeric and (numeric.group(1) or numeric.group(2)):
            out.append(int(numeric.group(1), 8) & 0xFF if numeric.group(1)
                       else int(numeric.group(2), 16))
            index = numeric.end()
        else:
            out += b"\\" + escape.encode("utf-8", SHELL_TEXT_ERRORS)
            index += 2
    return bytes(out).split(b"\0", 1)[0].decode("utf-8", SHELL_TEXT_ERRORS)


def _heredoc_of(node):
    start = next((child for child in node.children if child.type == "heredoc_start"), None)
    body = next((child for child in node.children if child.type == "heredoc_body"), None)
    delimiter = _text(start) if start is not None else ""
    body_text = _text(body) if body is not None else ""
    if any(child.type == "<<-" for child in node.children):
        body_text = "\n".join(line.lstrip("\t") for line in body_text.split("\n"))
    # Any quoting in the delimiter stops the shell expanding the body.
    return Heredoc(body_text, not any(mark in delimiter for mark in "'\"\\"), delimiter)


def _redirect_destinations(node):
    return node.children_by_field_name("destination") or [
        child for child in node.named_children if child.type != "file_descriptor"][:1]


def _redirect_parts(node, glob_markers, limit=None):
    """Return ((operator, target), words after the target) for one file redirect.

    limit, when given, is how many of its destination nodes belong to it.
    """
    operator = _descriptor_written_before(node) + "".join(
        _text(child) for child in node.children
        if child.type in ("file_descriptor",) or not child.is_named)
    destinations = _redirect_destinations(node)[:limit]
    # tree-sitter-bash reads the words after a redirect's target as more targets; bash
    # passes them to the command as arguments. It also splits a target such as
    # `$X/push$i.log` after its last `$`; a part that touches the one before it is the same word.
    words = []
    for destination in destinations:
        value = word_value(destination, glob_markers)
        if words and destination.start_byte == previous_end:
            words[-1] += value
        else:
            words.append(value)
        previous_end = destination.end_byte
    return (operator, words[0] if words else ""), words[1:]


def _descriptor_written_before(node):
    """Return the descriptor tree-sitter-bash read as a number just before a redirect, as in 0<f, or ""."""
    previous = node.prev_sibling
    while previous is not None and previous.type != "number" and previous.children \
            and previous.end_byte == node.start_byte:
        previous = previous.children[-1]
    if previous is not None and previous.type == "number" and previous.end_byte == node.start_byte:
        return _text(previous)
    return ""


class _Collector:
    def __init__(self, glob_markers, source, heredocs_taken_out):
        self.glob_markers = glob_markers
        self.source = source
        self.heredocs_taken_out = heredocs_taken_out
        self.commands = []

    def visit(self, node, child_shell, heredocs=()):
        kind = node.type
        if kind == "comment":
            return
        if kind == "command_substitution" and self.follows_process_id(node):
            return
        if kind == "command_substitution" and node.children and node.children[0].type == "`" \
                and b"\\`" in node.text:
            # tree-sitter-bash reads a backticked command's \` as text; bash reads a nested
            # backticked command there, once one level of backslashes is removed.
            inner = re.sub(r"\\([$`\\])", r"\1", _text(node)[1:-1])
            self.adopt(simple_commands(inner, self.glob_markers),
                       child_shell + (ChildShell(node.start_byte, SUBSTITUTION),))
            return
        if kind in CHILD_SHELL_NODE_TYPES:
            child_shell = child_shell + (ChildShell(
                node.start_byte, SUBSHELL if kind == "subshell" else SUBSTITUTION),)
        if kind in SEQUENCE_NODE_TYPES or kind in SIMPLE_COMMAND_NODE_TYPES:
            self.sequence(node, child_shell, heredocs)
            return
        if kind == "expansion":
            for child in node.children:
                if child.type == "word" and any(mark in _text(child) for mark in ("`", "<(", ">(")):
                    # tree-sitter-bash leaves a backtick or a process substitution in a
                    # ${name:-...} default as one word; bash runs it.
                    found = simple_commands("echo " + _text(child), self.glob_markers)
                    self.adopt([command for command in found if command.inside_substitution()],
                               child_shell + (ChildShell(child.start_byte, SUBSTITUTION),))
        for child in node.children:
            self.visit(child, child_shell, heredocs)

    def expanded_heredoc_body(self, taken, child_shell):
        """Collect the commands an unquoted heredoc body runs as the shell expands it.

        Only its $( ) and backticked substitutions run, in the order written. Each
        substitution is a child shell of its own, apart from every other body's.
        """
        for command in _heredoc_body_substitution_commands(taken.body, self.glob_markers):
            identity = tuple(shell.placed(
                lambda offset: -1 - offset - taken.number * BODY_IDENTITY_STRIDE)
                for shell in command.child_shell)
            self.commands.append(SimpleCommand(list(command), child_shell + identity,
                                               command.redirects, command.heredocs))

    def adopt(self, commands, child_shell):
        """Add commands read from a second parse, inside the child shell they run in."""
        for command in commands:
            self.commands.append(SimpleCommand(list(command), child_shell + command.child_shell,
                                               command.redirects, command.heredocs))

    def follows_process_id(self, node):
        return _follows_process_id(self.source, node.start_byte)

    def visit_inside(self, node, child_shell):
        """Visit the commands inside one word or redirect of a command."""
        self.visit(node, child_shell)

    def sequence(self, node, child_shell, heredocs):
        """Visit commands joined by |, |&, &&, ||, ; and & as bash groups them.

        tree-sitter-bash groups some of these wrongly: it reads
        `cd a && ls 2>/dev/null | head` as `(cd a && ls 2>/dev/null) | head`,
        joins a redirected command on the next line onto the last stage of a
        long pipeline, and puts `| bash` after `cat <<EOF` inside the heredoc.
        So the commands, operators and redirections are taken in the order
        they are written, and the pipelines are the commands joined by | or |&,
        the operators bash splits pipelines on. Each stage of a pipeline of two
        or more runs in a child shell.
        """
        items = []
        self._flatten(node, items)
        pipelines, current, joined = [], None, False
        for item in items:
            if item[0] == "unit":
                if current is None or not joined:
                    current = []
                    pipelines.append(current)
                current.append({"node": item[1], "children": item[2], "redirects": []})
                joined = False
            elif item[0] == "pipe":
                joined = True
            else:
                # A redirection belongs to the command written just before it.
                current[-1]["redirects"].append(item[1:])
        for pipeline in pipelines:
            shared_heredocs = list(heredocs)
            pipeline_start = (pipeline[0]["children"][0] if pipeline[0]["children"]
                              else pipeline[0]["node"]).start_byte
            for position, unit in enumerate(pipeline):
                first = unit["children"][0] if unit["children"] else unit["node"]
                unit_shell = (child_shell + (ChildShell(first.start_byte, PIPELINE_STAGE,
                                                        pipeline_start),)
                              if len(pipeline) > 1 else child_shell)
                redirects, trailing_words = [], []
                for redirect, limit in unit["redirects"]:
                    shared_heredocs.extend(
                        self.redirect(redirect, unit_shell, redirects, trailing_words, limit))
                if unit["children"] is not None:
                    self.simple_command(unit["node"], unit["children"], unit_shell,
                                        list(shared_heredocs), redirects, trailing_words)
                else:
                    self.visit(unit["node"], unit_shell, list(shared_heredocs))

    def _flatten(self, node, items):
        """Append node's commands, operators and redirections to items, in the order written."""
        kind = node.type
        if kind == "redirected_statement" and node.child_by_field_name("body") is None:
            # A statement that is only a redirection is a command with no words: it ends a
            # pipeline as any command does, and its target's substitutions run.
            items.append(("unit", node, []))
        if kind in SEQUENCE_NODE_TYPES:
            for child in node.children:
                if child.type == "comment":
                    continue
                if child.type in REDIRECT_NODE_TYPES:
                    self._flatten_redirect(child, items)
                elif child.is_named:
                    self._flatten(child, items)
                elif child.type in PIPE_OPERATORS:
                    items.append(("pipe",))
            return
        if kind in SIMPLE_COMMAND_NODE_TYPES:
            # tree-sitter-bash joins the next line's command onto the last stage of a pipeline
            # of three or more when that command has a redirection; bash runs two commands.
            part, previous_end = [], None
            for child in node.children:
                if previous_end is not None and part and _separates_commands(
                        self.source[previous_end:child.start_byte]):
                    items.append(("unit", node, part))
                    part = []
                part.append(child)
                previous_end = child.end_byte
            items.append(("unit", node, part))
            return
        items.append(("unit", node, None))

    def _flatten_redirect(self, node, items):
        """Append a redirection, and the commands tree-sitter-bash folded into it from later lines.

        tree-sitter-bash reads the words on the lines after a long pipeline's
        redirection as more of its targets, as in `a | b | head` followed by
        `cat > f` and `cd /x`; bash runs each line as a command.
        """
        destinations = _redirect_destinations(node) if node.type == "file_redirect" else []
        groups, previous_end = [[]], None
        for destination in destinations:
            if previous_end is not None and _separates_commands(
                    self.source[previous_end:destination.start_byte]):
                groups.append([])
            groups[-1].append(destination)
            previous_end = destination.end_byte
        items.append(("redirect", node, len(groups[0]) if len(groups) > 1 else None))
        for group in groups[1:]:
            items.append(("unit", node, group))

    def redirect(self, node, child_shell, redirects, trailing_words, limit=None):
        """Add one redirection to a command's redirects; return the heredocs it feeds."""
        if limit is None:
            self.visit_inside(node, child_shell)
        else:
            for destination in _redirect_destinations(node)[:limit]:
                self.visit_inside(destination, child_shell)
        if node.type == "heredoc_redirect":
            # A heredoc left in the tree, past the most taken out or kept to read a body's
            # substitutions, is data here; its substitutions were visited above.
            heredoc = _heredoc_of(node)
            redirects.append(("<<", heredoc.body))
            return [heredoc]
        pair, extra = _redirect_parts(node, self.glob_markers, limit)
        trailing_words.extend(extra)
        return self.heredoc_or_redirect(pair, child_shell, redirects)

    def heredoc_or_redirect(self, pair, child_shell, redirects):
        """Add pair to redirects, as the heredoc it stands for when its target is one taken out."""
        taken = self.heredocs_taken_out.get(pair[1])
        if taken is None:
            redirects.append(pair)
            return []
        body = taken.body.decode("utf-8", SHELL_TEXT_ERRORS)
        redirects.append(("<<", body))
        if taken.expanded:
            self.expanded_heredoc_body(taken, child_shell)
        return [Heredoc(body, taken.expanded, taken.delimiter_as_written)]

    def simple_command(self, node, children, child_shell, heredocs, redirects, trailing_words):
        words, own_redirects, own_heredocs = [], [], []
        for child in children:
            self._read_command_part(child, child_shell, words, own_redirects, own_heredocs)
        words.extend(trailing_words)
        if words:
            self.commands.append(SimpleCommand(words, child_shell, own_redirects + list(redirects),
                                               own_heredocs + list(heredocs)))

    def _read_command_part(self, child, child_shell, words, redirects, heredocs):
        """Add one child node of a command to its words, its redirections or its heredocs."""
        # Substitutions anywhere in the command run before it.
        self.visit_inside(child, child_shell)
        if child.type in REDIRECT_NODE_TYPES:
            pair, extra = _redirect_parts(child, self.glob_markers)
            heredocs.extend(self.heredoc_or_redirect(pair, child_shell, redirects))
            words.extend(extra)
        elif child.type == "variable_assignment":
            name = next((part for part in child.children if part.type == "variable_name"), None)
            value = next((part for part in child.named_children if part.type != "variable_name"),
                         None)
            operator = "+=" if any(part.type == "+=" for part in child.children) else "="
            words.append((_text(name) if name is not None else "") + operator
                         + (word_value(value, self.glob_markers) if value is not None else ""))
        elif (child.type == "number" and self.source[child.end_byte:child.end_byte + 1] in (b"<", b">")
              and self.source[child.end_byte + 1:child.end_byte + 2] != b"("):
            # tree-sitter-bash reads the 0 of 0<f as a number; it is the redirect's descriptor.
            pass
        elif child.type == "command_name":
            target = child.named_children[0] if child.named_children else child
            words.append(word_value(target, self.glob_markers))
        elif child.is_named and child.type != "comment":
            words.append(word_value(child, self.glob_markers))
        elif not child.is_named and kind_is_keyword(child):
            words.append(_text(child))


def _separates_commands(gap):
    """Return whether the text between two parts of one command holds a line end bash stops at."""
    return b"\n" in gap.replace(b"\\\n", b"")


def kind_is_keyword(node):
    # declaration_command and unset_command name their program as an anonymous keyword node.
    return node.type in ("export", "declare", "local", "readonly", "typeset", "unset", "unsetenv")


def simple_commands(command_text, glob_markers=None):
    """Return every simple command in command_text, in the order the shell runs them.

    glob_markers maps glob characters to marker strings; each glob character
    outside quotes and not escaped is replaced by its marker, so a caller can
    tell which ones the shell would expand. Raises ShellParserUnavailable, or
    ShellCommandUnreadable when this module fails on the command; it raises
    nothing else, so a guard is never stopped by an error it does not expect.
    """
    try:
        return _simple_commands_read(command_text, glob_markers)
    except ShellParserUnavailable:
        raise
    except Exception as error:
        raise ShellCommandUnreadable(f"{type(error).__name__}: {error}") from error


def _simple_commands_read(command_text, glob_markers):
    if _read_in_a_new_process:
        return _simple_commands_in_a_new_process(command_text, glob_markers)
    try:
        parser()
    except ShellParserInstalledForANewProcess:
        _use_a_new_process()
        return _simple_commands_in_a_new_process(command_text, glob_markers)
    original = command_text.encode("utf-8", SHELL_TEXT_ERRORS)
    text, source, tree, taken_out = _source_with_case_terminators_repaired(original, TEXT_NODE_TYPES)
    commands = _with_heredocs_put_back_into_commands(
        _collect(tree.root_node, glob_markers, source, taken_out), taken_out)
    if text != original:
        for command in commands:
            _words_put_back_as_written(command, command_text)
    for command in commands:
        command[:] = [_text_rejoined(word) for word in command]
        command.redirects = [(operator, _text_rejoined(target))
                             for operator, target in command.redirects]
    return commands


def _text_rejoined(text):
    """Return text with a character's bytes, decoded in separate pieces, decoded together again.

    tree-sitter-bash can split a word inside a character it cannot read, such as a lone
    surrogate's three bytes, and each piece then decodes to escaped bytes.
    """
    if not any("\ud800" <= character <= "\udfff" for character in text):
        return text
    return text.encode("utf-8", SHELL_TEXT_ERRORS).decode("utf-8", SHELL_TEXT_ERRORS)


def _source_with_case_terminators_repaired(text, text_node_types, keep_first=False):
    """Return (text, source, tree, taken) for text with its heredocs taken out and its cases repaired.

    tree-sitter-bash rejects a last case branch ended by ;;& or ;&, and loses
    every command after the case, a heredoc's included; before esac they act as
    ;; does. The earliest one outside text_node_types is written as ;; in the
    text, where the bodies already taken out cannot be mistaken for commands, and
    the text is read again, until the parse holds no error or no such one is left.
    """
    edits = []
    source, tree, taken = _source_with_heredoc_bodies_taken_out(text, keep_first, edits)
    # A match found with a body taken out may span that body, so the rounds count terminators.
    for _ in range(len(CASE_TERMINATOR_PATTERN.findall(text))):
        if not tree.root_node.has_error:
            break
        match = next((found for found in LAST_CASE_TERMINATOR_PATTERN.finditer(source)
                      if not _inside_text(tree.root_node, found.start(), text_node_types)), None)
        start = None if match is None else _offset_before_edits(match.start(), edits)
        if start is None:
            break
        # Only the terminator is replaced: what follows it in source may lie elsewhere in text.
        text = text[:start] + b";;" + text[start + match.start(1) - match.start():]
        edits = []
        source, tree, taken = _source_with_heredoc_bodies_taken_out(text, keep_first, edits)
    return text, source, tree, taken


def _words_put_back_as_written(command, command_text):
    """Put each ;; the case repair wrote in a command's words back as written.

    Words carry no offsets, so each is found in the text as written, with any ;;
    allowed to be ;;& or ;&, after the word before it; a word quote removal
    changed is not found and stays as read.
    """
    position = 0
    for index, word in enumerate(command):
        if ";;" not in word:
            continue
        pattern = "(?:;;&|;&|;;)".join(re.escape(part) for part in word.split(";;"))
        written = re.compile(pattern).search(command_text, position)
        if written is not None:
            command[index] = written.group(0)
            position = written.end()


def _with_heredocs_put_back_into_commands(commands, taken_out):
    if taken_out:
        for command in commands:
            command[:] = [_with_heredocs_put_back(word, taken_out) for word in command]
            command.redirects = [(operator, _with_heredocs_put_back(target, taken_out))
                                 for operator, target in command.redirects]
    return commands


def _offset_before_edits(offset, edits):
    """Return where offset of the edited text was before edits, or None inside an inserted part."""
    for at, removed, inserted in reversed(edits):
        if offset >= at + inserted:
            offset += removed - inserted
        elif offset >= at:
            return None
    return offset


def _heredoc_body_substitution_commands(body, glob_markers):
    """Return the commands in the substitutions of an unquoted heredoc body, in the order written.

    tree-sitter-bash reads an unquoted body's $( ), $(( )) and ${ } as nodes, so
    the body is parsed once, as the body of a heredoc whose delimiter starts none
    of its lines; heredocs inside it are taken out first. Its backticked commands
    stay text in that parse, so the body is then walked as bash expands it: from
    left to right, each backtick or node owns what it encloses. A body bash
    rejects is still read: a guard reading too much refuses a command bash would
    not run, and reading too little lets one through.
    """
    delimiter = b"NEDSCHORUS_BODY_END"
    while any(line.startswith(delimiter) for line in body.split(b"\n")):
        delimiter += b"_"
    prefix = b"cat <<" + delimiter + b"\n"
    probe = prefix + body + delimiter + b"\n"
    # In the probe, the body is the code, so only quoted text and comments are not repaired.
    _, source, tree, taken = _source_with_case_terminators_repaired(
        probe, TEXT_NODE_TYPES - {"heredoc_body"}, keep_first=True)
    # tree-sitter-bash reads a body's $(( )) as a substitution holding a subshell; bash reads
    # $(( as arithmetic when its inner ( closes right before the final ), and only
    # substitutions run in arithmetic.
    arithmetic = {node.start_byte for node in _nodes_of_type(tree.root_node, "command_substitution")
                  if _arithmetic_written(node.text)}
    commands = [command for command in _collect(tree.root_node, glob_markers, source, taken)
                if command.inside_substitution() and _runs_outside_arithmetic(command, arithmetic)]
    # The body's own extent, which tree-sitter-bash sometimes puts outside its heredoc_body node.
    start, end = len(prefix), len(source) - len(delimiter) - 1
    expansions = {}
    for node in _nodes_of_type(tree.root_node, *BODY_EXPANSION_NODE_TYPES):
        if start <= node.start_byte < end:
            expansions.setdefault(node.start_byte, node)
    index = start
    while index < end:
        node = expansions.get(index)
        if node is not None and not (node.type == "expansion" and b"`" in node.text):
            index = node.end_byte
        elif node is not None:
            # tree-sitter-bash splits a backticked command inside ${ }; the walk reads it there.
            index += 1
        elif source[index:index + 1] == b"\\":
            index += 2
        elif source[index:index + 1] == b"`":
            closing = index + 1
            while closing < end and source[closing:closing + 1] != b"`":
                closing += 2 if source[closing:closing + 1] == b"\\" else 1
            if closing >= end:
                break
            # Inside backticks a backslash keeps $, ` and \ literal.
            inner = re.sub(r"\\([$`\\])", r"\1",
                           source[index + 1:closing].decode("utf-8", SHELL_TEXT_ERRORS))
            commands = _commands_read_again(commands, index, closing + 1, inner, glob_markers)
            index = closing + 1
        else:
            index += 1
    commands.sort(key=lambda command: command.child_shell[0].offset)
    return _with_heredocs_put_back_into_commands(commands, taken)


def _commands_read_again(commands, start, end, text, glob_markers):
    """Return commands with those found from start to end replaced by text's commands, read whole."""
    kept = [command for command in commands
            if not any(start <= shell.offset < end for shell in command.child_shell)]
    for command in simple_commands(text, glob_markers):
        command.child_shell = (ChildShell(start, SUBSTITUTION),) + command.child_shell
        kept.append(command)
    return kept


BODY_EXPANSION_NODE_TYPES = {"command_substitution", "expansion", "arithmetic_expansion"}


def _arithmetic_written(text):
    """Return whether a $(( ... )) is arithmetic as bash reads it: its inner ( closes just before the last )."""
    depth = 0
    for index in range(2, len(text)):
        depth += {b"("[0]: 1, b")"[0]: -1}.get(text[index], 0)
        if depth == 0:
            return index == len(text) - 2 and text.endswith(b"))")
    return False


def _runs_outside_arithmetic(command, arithmetic):
    """Return whether a command runs, given the offsets of the $(( )) it may sit in."""
    inside = [index for index, shell in enumerate(command.child_shell)
              if shell.kind == SUBSTITUTION and shell.offset in arithmetic]
    return not inside or any(shell.kind == SUBSTITUTION
                             for shell in command.child_shell[inside[-1] + 1:])


def _nodes_of_type(node, *kinds):
    """Yield the nodes of the given types under node, in the order written."""
    stack = [node]
    while stack:
        current = stack.pop()
        if current.type in kinds:
            yield current
        stack.extend(reversed(current.children))


_read_in_a_new_process = False


def _use_a_new_process():
    global _read_in_a_new_process
    _read_in_a_new_process = True


def _simple_commands_in_a_new_process(command_text, glob_markers, runner=subprocess.run):
    """Return simple_commands(command_text) as read by a new Python process running this file."""
    request = json.dumps({"command": command_text, "glob_markers": glob_markers},
                         ensure_ascii=False)
    try:
        completed = runner([sys.executable, str(Path(__file__).resolve()), NEW_PROCESS_READ_FLAG],
                           input=request.encode("utf-8", SHELL_TEXT_ERRORS), capture_output=True,
                           timeout=INSTALL_TIMEOUT_SECONDS)
    except (OSError, subprocess.SubprocessError) as error:
        raise ShellParserUnavailable(f"reading the command in a new process failed: {error}") \
            from error
    if completed.returncode != 0:
        raise ShellParserUnavailable(
            "reading the command in a new process failed: "
            + (completed.stderr.decode("utf-8", "replace").strip() or f"exit {completed.returncode}"))
    read = json.loads(completed.stdout.decode("utf-8", SHELL_TEXT_ERRORS))
    if isinstance(read, dict):
        raise ShellCommandUnreadable(read["unreadable"])
    return [SimpleCommand(found["words"],
                          tuple(ChildShell(*shell) for shell in found["child_shell"]),
                          [tuple(pair) for pair in found["redirects"]],
                          [Heredoc(*heredoc) for heredoc in found["heredocs"]])
            for found in read]


NEW_PROCESS_READ_FLAG = "--read-command-on-standard-input"


def _read_command_on_standard_input():
    request = json.loads(sys.stdin.buffer.read().decode("utf-8", SHELL_TEXT_ERRORS))
    try:
        found = simple_commands(request["command"], request["glob_markers"])
    except ShellCommandUnreadable as error:
        sys.stdout.buffer.write(json.dumps({"unreadable": error.install_output}).encode())
        return
    sys.stdout.buffer.write(json.dumps([
        {"words": list(command),
         "child_shell": [list(shell) for shell in command.child_shell],
         "redirects": command.redirects,
         "heredocs": [(heredoc.body, heredoc.expanded, heredoc.delimiter)
                      for heredoc in command.heredocs]}
        for command in found], ensure_ascii=False).encode("utf-8", SHELL_TEXT_ERRORS))


def _collect(root, glob_markers, source, heredocs_taken_out):
    collector = _Collector(glob_markers, source, heredocs_taken_out)
    # The walk recurses once per nesting level; a deeply nested command must not crash a guard.
    limit = sys.getrecursionlimit()
    sys.setrecursionlimit(max(limit, RECURSION_LIMIT_FOR_DEEP_NESTING))
    try:
        collector.visit(root, ())
    finally:
        sys.setrecursionlimit(limit)
    return collector.commands


def _heredoc_starts(node):
    stack, found = [node], []
    while stack:
        current = stack.pop()
        if current.type == "heredoc_start":
            found.append(current)
        stack.extend(current.children)
    return sorted(found, key=lambda start: start.start_byte)


class _HeredocTakenOut:
    """A heredoc taken out of a command line: what was written, and its body."""

    def __init__(self, written, delimiter_as_written, body, expanded, ending, number):
        self.written = written
        self.delimiter_as_written = delimiter_as_written
        self.body = body
        self.expanded = expanded
        self.ending = ending
        self.number = number


HEREDOC_PLACEHOLDER_PREFIX = "NEDSCHORUS_HEREDOC_"
HEREDOC_START_WITH_DESCRIPTOR_PATTERN = re.compile(rb"([0-9]+)(<<-?)")
# Each heredoc taken out costs a parse; real commands hold far fewer.
MAX_HEREDOCS_TAKEN_OUT = 256


def _source_with_heredoc_bodies_taken_out(source, keep_first=False, edits=None):
    """Return (source, tree, {placeholder: _HeredocTakenOut}) with every heredoc's body taken out.

    bash reads a heredoc's body in its lexer, line by line, after the line
    that opens it, and ends it at a line that is exactly its delimiter.
    tree-sitter-bash ends a body at a line that only starts with the
    delimiter, misreads what follows the delimiter on its line, and puts the
    commands after the body inside the heredoc. Once a body is misplaced,
    every node after it is wrong, so no reading of the tree can repair it.
    So the bodies are taken out first, as bash's lexer takes them: the
    earliest heredoc operator in the parse is placed right, since nothing
    before it is a heredoc; its delimiter word and body are found by bash's
    rules; `<<DELIMITER` becomes `<PLACEHOLDER`, a plain redirection
    tree-sitter-bash reads correctly, and the body lines are removed; then
    the next one, until none is left. keep_first leaves the earliest heredoc in
    place. edits, when given, gets (offset, length removed, length inserted) for
    each change, in the order made.
    """
    taken = {}
    original = source
    tree = parser().parse(source)
    for index in range(MAX_HEREDOCS_TAKEN_OUT):
        start = next(iter(_heredoc_starts(tree.root_node)[1 if keep_first else 0:]), None)
        operator = start.prev_sibling if start is not None else None
        if operator is None or operator.type not in ("<<", "<<-"):
            break
        operator_start, delimiter_start, dashed = (operator.start_byte, start.start_byte,
                                                   operator.type == "<<-")
        # tree-sitter-bash reads the 0 of 0<<EOF into the delimiter, after an empty operator.
        descriptor = HEREDOC_START_WITH_DESCRIPTOR_PATTERN.match(source, start.start_byte)
        if descriptor:
            operator_start, delimiter_start = descriptor.start(2), descriptor.end()
        delimiter_end, delimiter = _delimiter_word(source, delimiter_start)
        body_start = _heredoc_body_start(source, delimiter_end)
        body_end, resume = _heredoc_body_end(source, body_start, delimiter, dashed,
                                             _inside_substitution(start))
        body = source[body_start:body_end]
        if dashed:
            body = b"\n".join(line.lstrip(b"\t") for line in body.split(b"\n"))
        placeholder = f"{HEREDOC_PLACEHOLDER_PREFIX}{index}"
        while placeholder.encode() in original:
            placeholder += "_"
        written = source[operator_start:delimiter_end]
        delimiter_as_written = source[delimiter_start:delimiter_end]
        taken[placeholder] = _HeredocTakenOut(
            written.decode("utf-8", SHELL_TEXT_ERRORS),
            delimiter_as_written.decode("utf-8", SHELL_TEXT_ERRORS), body,
            not any(mark in delimiter_as_written for mark in (b"'", b'"', b"\\")),
            source[body_end:resume].decode("utf-8", SHELL_TEXT_ERRORS), index)
        replacement = b"<" + placeholder.encode()
        if edits is not None:
            edits.append((operator_start, delimiter_end - operator_start, len(replacement)))
            edits.append((body_start - (delimiter_end - operator_start) + len(replacement),
                          resume - body_start, 0))
        source = (source[:operator_start] + replacement
                  + source[delimiter_end:body_start] + source[resume:])
        tree = parser().parse(source)
    return source, tree, taken


def _delimiter_word(source, position):
    """Return (end, delimiter) for the heredoc delimiter word at position, by bash's rules.

    The word ends at an unquoted blank or operator character; the delimiter is
    the word with its quotes and backslashes removed.
    """
    word, index = bytearray(), position
    while index < len(source):
        character = source[index:index + 1]
        if character == b"\\":
            word += source[index + 1:index + 2]
            index += 2
        elif character == b"'":
            closing = source.find(character, index + 1)
            closing = len(source) if closing == -1 else closing
            word += source[index + 1:closing]
            index = closing + 1
        elif character == b'"':
            # Inside double quotes a backslash keeps ", \\, $ and ` literal.
            index += 1
            while index < len(source) and source[index:index + 1] != b'"':
                if source[index:index + 1] == b"\\" and source[index + 1:index + 2] in b'"\\$`':
                    index += 1
                word += source[index:index + 1]
                index += 1
            index += 1
        elif character in b" \t\n;&|()<>":
            break
        else:
            word += character
            index += 1
    return index, bytes(word)


def _inside_substitution(node):
    parent = node.parent
    while parent is not None:
        if parent.type in ("command_substitution", "process_substitution"):
            return True
        parent = parent.parent
    return False


def _heredoc_body_end(source, position, delimiter, dashed, inside_substitution):
    """Return (body end, where the command line resumes) for a body starting at position.

    The body ends at a line that is exactly its delimiter, after leading tabs
    for <<-; inside a substitution, bash also ends it at the delimiter
    followed by the substitution's ). A body that never ends runs to the end.
    """
    while position < len(source):
        line_end = source.find(b"\n", position)
        line_end = len(source) if line_end == -1 else line_end
        line = source[position:line_end]
        compared = line.lstrip(b"\t") if dashed else line
        if compared == delimiter:
            return position, min(line_end + 1, len(source))
        if inside_substitution and compared.startswith(delimiter + b")"):
            return position, position + len(line) - len(compared) + len(delimiter)
        position = line_end + 1
    return len(source), len(source)


def _heredoc_body_start(source, delimiter_end):
    """Return where a heredoc's body starts: after the line that opens it.

    That line ends at the first line end outside quotes, substitutions and
    backslash continuations, as in `cat <<EOF && git commit -m "two` with the
    message's second line next. The rest of the command line is parsed on its
    own to find it; what follows that line end does not change how the text
    before it is read.
    """
    probe = b": " + source[delimiter_end:]
    stack, inside, comments = [parser().parse(probe).root_node], [], []
    while stack:
        node = stack.pop()
        if node.type == "comment":
            comments.append((node.start_byte, node.end_byte))
            continue
        if node.type in ("string", "raw_string", "ansi_c_string", "translated_string",
                         "command_substitution", "process_substitution", "expansion",
                         "arithmetic_expansion"):
            inside.append((node.start_byte, node.end_byte))
            continue
        stack.extend(node.children)
    position = 2
    while True:
        line_end = probe.find(b"\n", position)
        if line_end == -1:
            return len(source)
        # A backslash continues a line, except at the end of a comment.
        continued = (len(probe[:line_end]) - len(probe[:line_end].rstrip(b"\\"))) % 2 == 1 \
            and not any(begin <= line_end - 1 < end for begin, end in comments)
        if not any(begin < line_end < end for begin, end in inside) and not continued:
            return delimiter_end + line_end - 2 + 1
        position = line_end + 1


def _with_heredocs_put_back(text, taken_out):
    """Return text with each heredoc taken out of it put back as written, body included."""
    for placeholder in reversed(list(taken_out)):
        taken = taken_out[placeholder]
        mark = "<" + placeholder
        index = text.find(mark)
        while index != -1:
            text = text[:index] + taken.written + text[index + len(mark):]
            line_end = text.find("\n", index + len(taken.written))
            if line_end != -1:
                text = (text[:line_end + 1] + taken.body.decode("utf-8", SHELL_TEXT_ERRORS)
                        + taken.ending + text[line_end + 1:])
            index = text.find(mark, index + len(taken.written))
    return text


BODY_IDENTITY_STRIDE = 1 << 32


def _follows_process_id(source, offset):
    """Return whether bash reads the $( at offset as $$, the process id, followed by a parenthesis."""
    # tree-sitter-bash reads $$(x) as $ and $(x); bash pairs the dollars from the left.
    dollars = 0
    index = offset - 1
    while index >= 0 and source[index:index + 1] == b"$":
        dollars += 1
        index -= 1
    return source[offset:offset + 2] == b"$(" and dollars % 2 == 1


# A comment may come between the terminator and esac.
LAST_CASE_TERMINATOR_PATTERN = re.compile(rb";;?&((?:\s|#[^\n]*\n)*esac\b)")
CASE_TERMINATOR_PATTERN = re.compile(rb";;?&")


TEXT_NODE_TYPES = {"raw_string", "string", "ansi_c_string", "heredoc_body", "comment"}


def _inside_text(root, byte, text_node_types):
    """Return whether byte lies in a node of one of text_node_types, such as a quoted string."""
    node = root.descendant_for_byte_range(byte, byte + 1)
    while node is not None:
        if node.type in text_node_types:
            return True
        node = node.parent
    return False


if __name__ == "__main__" and sys.argv[1:] == [NEW_PROCESS_READ_FLAG]:
    _read_command_on_standard_input()
