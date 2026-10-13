#!/usr/bin/env python3
"""Read a shell command with tree-sitter-bash and return its simple commands.

The project's Bash guards ask one question of a command line: which programs
does it run, with which words? A hand-written reader gets ordinary bash wrong
(a `cd` inside `( ... )` changing the directory of later commands, `if git push
-f …; then` read as a command named `if`, a heredoc body read as commands).
tree-sitter-bash is the parser Claude Code and the Codex CLI use; this module
walks its tree and hands each simple command back as its words.

simple_commands collects what it can, from an incomplete or invalid command
too, so a guard can refuse what it finds. Nothing it returns proves a command
safe: words keep expansions such as `$HOME` as written, and a command built at
run time, by `eval` or a variable holding a program name, is not seen.

tree-sitter and tree-sitter-bash are compiled libraries, installed per user
from compiled-python-libraries-pinned-requirements.txt beside this file. When
they are missing, the first use installs them. ShellParserUnavailable means
the install failed: the guard lets the command through and says so with
parser_unavailable_hook_output, which asks for the user to be told once per
agent-session. A failed install is tried again after ten minutes.

Load it by path, under the snake_case form of its file name:

    spec = importlib.util.spec_from_file_location(
        "shell_command_tree_sitter_bash_reader_common", <path>)
"""

# Deferred annotations let the module load on the Mac's system Python 3.9.
from __future__ import annotations

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
# Characters a backslash keeps literal inside double quotes; before any other, the backslash stays.
DOUBLE_QUOTE_ESCAPABLE = set('"\\$`')


class ShellParserUnavailable(Exception):
    """tree-sitter-bash could not be imported, and installing it failed.

    install_output holds what the install printed, or why it did not run.
    """

    def __init__(self, install_output):
        super().__init__(install_output)
        self.install_output = install_output


class Heredoc:
    """One heredoc: its body as written, and whether the shell expands it."""

    def __init__(self, body, expanded, delimiter=""):
        self.body = body
        self.expanded = expanded
        self.delimiter = delimiter

    def __repr__(self):
        return f"Heredoc({self.body!r}, expanded={self.expanded})"


class SimpleCommand(list):
    """The words of one simple command, assignments first, redirections left out.

    child_shell names the enclosing command substitutions, subshells and
    pipeline stages, outermost first, by their start offsets; () is the
    command line's own shell. A command whose child_shell starts with another's
    runs inside it, so it sees that shell's cd but its own cd does not leak
    out. redirects holds (operator, target) pairs, heredocs the heredocs fed
    to this command or to the pipeline that starts on its heredoc line.
    """

    def __init__(self, words, child_shell, redirects, heredocs):
        super().__init__(words)
        self.child_shell = child_shell
        self.redirects = redirects
        self.heredocs = heredocs


def is_program(word, name):
    """Return whether word runs the program name, given bare or by path."""
    return word == name or word.endswith("/" + name)


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
    """Return (tree_sitter, tree_sitter_bash), raising ImportError when either is missing."""
    import tree_sitter
    import tree_sitter_bash
    return tree_sitter, tree_sitter_bash


def load_parser(importer=import_tree_sitter_bash, installer=install_compiled_libraries,
                clock=time.time):
    """Return a tree-sitter Parser for bash, installing the libraries when they are missing."""
    try:
        tree_sitter, tree_sitter_bash = importer()
    except ImportError:
        tree_sitter, tree_sitter_bash = _install_then_import(importer, installer, clock)
    return tree_sitter.Parser(tree_sitter.Language(tree_sitter_bash.language()))


def _install_then_import(importer, installer, clock):
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
            # A user site that did not exist at start-up is not on sys.path yet.
            site.addsitedir(site.getusersitepackages())
            importlib.invalidate_caches()
            try:
                modules = importer()
            except ImportError as error:
                raise ShellParserUnavailable(
                    f"the install finished but importing still fails: {error}") from error
        except ShellParserUnavailable as error:
            try:
                failure_record.write_text(error.install_output, encoding="utf-8")
            except OSError:
                pass
            raise
        try:
            failure_record.unlink()
        except OSError:
            pass
        return modules


_parser = None


def parser():
    global _parser
    if _parser is None:
        _parser = load_parser()
    return _parser


def _session_unattended(environment):
    return bool(environment.get("NEDSCHORUS_SESSION_REINCARNATION_OWNED_BY_CALLER")
                or environment.get("CLAUDE_CODE_SESSION_ATTENDED") == "0")


def _claim_telling_the_user(session_id):
    """Return True for the first guard in this agent-session to report the missing parser."""
    safe_key = re.sub(r"[^A-Za-z0-9_.-]", "_", str(session_id or "unknown-session"))[:200]
    try:
        STATE_DIRECTORY.mkdir(parents=True, exist_ok=True)
        with open(STATE_DIRECTORY / f"{safe_key}.shell-parser-unavailable-told", "x",
                  encoding="utf-8"):
            pass
    except FileExistsError:
        return False
    except OSError:
        return True  # Without the marker, telling twice beats never telling.
    return True


def parser_unavailable_hook_output(guard_name, error, payload, environment=os.environ):
    """Return the PreToolUse JSON that lets the command through and says it was not checked."""
    host = socket.gethostname().split(".")[0]
    not_checked = (f"{guard_name} let this command through without checking it: the shell parser "
                   f"tree-sitter-bash is missing on {host}, and installing it failed.")
    if _session_unattended(environment):
        message = f"{not_checked}\nNo user attends this agent-session, so do not tell the user."
    elif not _claim_telling_the_user(payload.get("session_id")):
        message = (f"{not_checked}\nAn earlier message in this agent-session asked for the user "
                   f"to be told; do not tell the user again.")
    else:
        install = f"python3 -m pip install --user --break-system-packages -r {REQUIREMENTS_FILE}"
        # The user sits at the Mac, and reaches ned-box over ssh.
        by_hand = (f"from your Mac, run: ssh nedlern@ned-box '{install}'" if host == "ned-box"
                   else f"run on {host}: {install}")
        message = (
            f"{not_checked}\n"
            f"Tell the user, in these words: \"tree-sitter-bash is missing on {host} and could not "
            f"be installed, so the project's Bash guards are not checking commands there. To "
            f"install it by hand, {by_hand}\"\n"
            f"Then give the user what the install printed, quoted as it is: {error.install_output}\n"
            f"If you are a subagent, pass the quoted sentences and what the install printed to "
            f"the agent that dispatched you instead.\n"
            f"Later commands are let through unchecked as well. The first command after "
            f"{INSTALL_RETRY_SECONDS // 60} minutes have passed tries the install again, and the "
            f"guards check commands again once it succeeds. You will not be asked to tell the user "
            f"again in this agent-session.")
    return json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "additionalContext": message,
    }})


def _text(node):
    return node.text.decode("utf-8", "surrogatepass")


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
        return _text(node)[2:-1].replace("\\'", "'")
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
            pieces.append(_unescape_double_quoted(gap.decode("utf-8", "surrogatepass")))
            if child.type == "string_content":
                pieces.append(_unescape_double_quoted(_text(child)))
            else:
                pieces.append(_text(child))
            position = child.end_byte
        closing = string.end_byte - 1
        pieces.append(_unescape_double_quoted(
            source[position - string.start_byte:closing - string.start_byte]
            .decode("utf-8", "surrogatepass")))
        return "".join(pieces)
    if kind == "concatenation":
        return "".join(word_value(child, glob_markers) for child in node.children)
    if kind in ("word", "number"):
        return _unescape_unquoted(_text(node), glob_markers)
    # Expansions and substitutions are kept as written; the shell decides their value at run time.
    return _text(node)


def _heredoc_of(node):
    start = next((child for child in node.children if child.type == "heredoc_start"), None)
    body = next((child for child in node.children if child.type == "heredoc_body"), None)
    delimiter = _text(start) if start is not None else ""
    body_text = _text(body) if body is not None else ""
    if any(child.type == "<<-" for child in node.children):
        body_text = "\n".join(line.lstrip("\t") for line in body_text.split("\n"))
    # Any quoting in the delimiter stops the shell expanding the body.
    return Heredoc(body_text, not any(mark in delimiter for mark in "'\"\\"), delimiter)


def _redirect_parts(node, glob_markers):
    """Return ((operator, target), words after the target) for one file redirect."""
    operator = "".join(_text(child) for child in node.children
                       if child.type in ("file_descriptor",) or not child.is_named)
    destinations = node.children_by_field_name("destination") or [
        child for child in node.named_children if child.type != "file_descriptor"][:1]
    target = word_value(destinations[0], glob_markers) if destinations else ""
    # tree-sitter-bash reads the words after a redirect's target as more targets; bash
    # passes them to the command as arguments.
    return (operator, target), [word_value(extra, glob_markers) for extra in destinations[1:]]


class _Collector:
    def __init__(self, glob_markers, source, skip_errors=False):
        self.glob_markers = glob_markers
        self.source = source
        self.skip_errors = skip_errors
        self.commands = []

    def visit(self, node, child_shell, heredocs=(), redirects=(), trailing_words=()):
        kind = node.type
        if kind == "comment":
            return
        if kind == "ERROR" and self.skip_errors:
            # Inside a body bash expands, only a substitution that closed runs.
            for child in node.children:
                if child.type in CHILD_SHELL_NODE_TYPES and child.children \
                        and child.children[-1].type in (")", "`"):
                    self.visit(child, child_shell)
            return
        if kind == "command_substitution" and self.follows_process_id(node):
            return
        if kind in CHILD_SHELL_NODE_TYPES:
            child_shell = child_shell + (node.start_byte,)
        if kind == "redirected_statement":
            self.redirected_statement(node, child_shell, heredocs)
            return
        if kind == "pipeline":
            stages = [child for child in node.named_children if child.type != "comment"]
            for child in node.children:
                # Each stage of a pipeline of two or more runs in its own child shell.
                inner = child_shell + (child.start_byte,) if len(stages) > 1 and child.is_named \
                    else child_shell
                self.visit(child, inner, heredocs)
            return
        if kind in SIMPLE_COMMAND_NODE_TYPES:
            self.simple_command(node, child_shell, heredocs, redirects, trailing_words)
            return
        if kind == "expansion":
            for child in node.children:
                if child.type == "word" and any(mark in _text(child) for mark in ("`", "<(", ">(")):
                    # tree-sitter-bash leaves a backtick or a process substitution in a
                    # ${name:-...} default as one word; bash runs it.
                    found = simple_commands("echo " + _text(child), self.glob_markers)
                    self.adopt([command for command in found if command.child_shell],
                               child_shell + (child.start_byte,))
        for child in node.children:
            self.visit(child, child_shell, heredocs)

    def expanded_heredoc_body(self, body, child_shell):
        """Collect the commands an unquoted heredoc body runs as the shell expands it."""
        text = bytearray(body.text)
        for child in body.named_children:
            if child.type != "heredoc_content":
                self.visit(child, child_shell)
                # What tree-sitter-bash read is not scanned again for backticks.
                start, end = child.start_byte - body.start_byte, child.end_byte - body.start_byte
                text[start:end] = b" " * (end - start)
        # tree-sitter-bash reads $( ) in a body but leaves backticks as text.
        for start, inner in backticked_commands(bytes(text).decode("utf-8", "surrogatepass")):
            self.adopt(simple_commands(inner, self.glob_markers),
                       child_shell + (body.start_byte + start,))

    def adopt(self, commands, child_shell):
        """Add commands read from a second parse, inside the child shell they run in."""
        for command in commands:
            self.commands.append(SimpleCommand(list(command), child_shell + command.child_shell,
                                               command.redirects, command.heredocs))

    def follows_process_id(self, node):
        """Return whether bash reads this $( as $$, the process id, followed by a parenthesis."""
        # tree-sitter-bash reads $$(x) as $ and $(x); bash pairs the dollars from the left.
        dollars = 0
        index = node.start_byte - 1
        while index >= 0 and self.source[index:index + 1] == b"$":
            dollars += 1
            index -= 1
        return self.source[node.start_byte:node.start_byte + 2] == b"$(" and dollars % 2 == 1

    def visit_inside(self, node, child_shell):
        """Visit the commands inside one word or redirect of a command."""
        self.visit(node, child_shell)

    def redirected_statement(self, node, child_shell, heredocs):
        heredocs = list(heredocs)
        redirects, trailing_words = [], []
        later = []
        for child in node.children_by_field_name("redirect"):
            if child.type == "heredoc_redirect":
                heredoc = _heredoc_of(child)
                heredocs.append(heredoc)
                redirects.append(("<<", heredoc.body))
                for inner in child.children:
                    if inner.type == "heredoc_body":
                        if heredoc.expanded:
                            self.expanded_heredoc_body(inner, child_shell)
                    elif inner.type in REDIRECT_NODE_TYPES:
                        pair, extra = _redirect_parts(inner, self.glob_markers)
                        redirects.append(pair)
                        trailing_words.extend(extra)
                    elif inner.is_named and inner.type not in ("heredoc_start", "heredoc_end"):
                        # A pipeline written after the heredoc's start shares the heredoc line.
                        later.append(inner)
            else:
                self.visit_inside(child, child_shell)
                pair, extra = _redirect_parts(child, self.glob_markers)
                redirects.append(pair)
                trailing_words.extend(extra)
        body = node.child_by_field_name("body")
        if body is not None:
            self.visit(body, child_shell, heredocs, redirects, trailing_words)
        for inner in later:
            self.visit(inner, child_shell, heredocs)

    def simple_command(self, node, child_shell, heredocs, redirects, trailing_words=()):
        words, redirects = [], list(redirects)
        for child in node.children:
            # Substitutions anywhere in the command run before it.
            self.visit_inside(child, child_shell)
            if child.type in REDIRECT_NODE_TYPES:
                pair, extra = _redirect_parts(child, self.glob_markers)
                redirects.append(pair)
                words.extend(extra)
            elif child.type == "variable_assignment":
                name = next((part for part in child.children if part.type == "variable_name"), None)
                value = next((part for part in child.named_children if part.type != "variable_name"),
                             None)
                operator = "+=" if any(part.type == "+=" for part in child.children) else "="
                words.append((_text(name) if name is not None else "") + operator
                             + (word_value(value, self.glob_markers) if value is not None else ""))
            elif child.type == "command_name":
                target = child.named_children[0] if child.named_children else child
                words.append(word_value(target, self.glob_markers))
            elif child.is_named and child.type != "comment":
                words.append(word_value(child, self.glob_markers))
            elif not child.is_named and kind_is_keyword(child):
                words.append(_text(child))
        words.extend(trailing_words)
        if words:
            self.commands.append(SimpleCommand(words, child_shell, redirects, list(heredocs)))


def backticked_commands(text):
    """Return (offset, command text) for each backticked command in heredoc text.

    Inside backticks a backslash keeps $, ` and \\ literal, and an unescaped
    backtick closes the command; one that never closes runs nothing.
    """
    found = []
    index = 0
    while index < len(text):
        if text[index] == "\\":
            index += 2
            continue
        if text[index] != "`":
            index += 1
            continue
        closing = index + 1
        while closing < len(text) and text[closing] != "`":
            closing += 2 if text[closing] == "\\" else 1
        if closing >= len(text):
            break
        found.append((index, re.sub(r"\\([$`\\])", r"\1", text[index + 1:closing])))
        index = closing + 1
    return found


def kind_is_keyword(node):
    # declaration_command and unset_command name their program as an anonymous keyword node.
    return node.type in ("export", "declare", "local", "readonly", "typeset", "unset", "unsetenv")


def simple_commands(command_text, glob_markers=None):
    """Return every simple command in command_text, in the order the shell runs them.

    glob_markers maps glob characters to marker strings; each glob character
    outside quotes and not escaped is replaced by its marker, so a caller can
    tell which ones the shell would expand. Raises ShellParserUnavailable.
    """
    source = command_text.encode("utf-8", "surrogatepass")
    tree = parser().parse(source)
    rewritten = _source_with_unique_heredoc_delimiters(source, tree)
    restore = []
    if rewritten is not None:
        (source, restore), tree = rewritten, parser().parse(rewritten[0])
    commands = None
    if tree.root_node.has_error:
        commands = _reread_with_heredoc_bodies_apart(source, tree, glob_markers)
    if commands is None:
        commands = _collect(tree.root_node, glob_markers, source)
    for command in commands:
        _restore_delimiters(command, restore)
    return commands


def _restore_delimiters(command, restore):
    """Put the command's own heredoc delimiters back into its words and heredocs."""
    def restored(text):
        for unique, original in restore:
            text = text.replace(unique, original)
        return text
    if restore:
        command[:] = [restored(word) for word in command]
        command.redirects = [(operator, restored(target)) for operator, target in command.redirects]
        for heredoc in command.heredocs:
            heredoc.delimiter = restored(heredoc.delimiter)


def _collect(root, glob_markers, source, skip_errors=False):
    collector = _Collector(glob_markers, source, skip_errors)
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


def _heredoc_delimiter(start):
    # Quoting in a delimiter only stops expansion; the line that ends the body is the bare word.
    return re.sub(rb"['\"\\\\]", b"", start.text)


def _source_with_unique_heredoc_delimiters(source, tree):
    """Return (source with unique heredoc delimiters, [(unique, original)]), or None.

    bash ends a heredoc only at a line that is exactly its delimiter;
    tree-sitter-bash ends it at any line that starts with the delimiter, such
    as EOF2 inside a body ended by EOF, and reads the rest of the body as
    commands. Renaming each delimiter, and the line that ends its body, to a
    word found nowhere in the command leaves bash's reading unchanged and
    lets tree-sitter-bash find the same end.
    """
    replacements = []  # (start, end, new bytes)
    body_resumes = 0
    for number, start in enumerate(_heredoc_starts(tree.root_node)):
        delimiter = _heredoc_delimiter(start)
        if not delimiter:
            continue
        dashed = source[:start.start_byte].rstrip(b" \t").endswith(b"<<-")
        line_end = source.find(b"\n", start.end_byte)
        if line_end == -1:
            break
        unique = b"NEDSCHORUS_HEREDOC_END_%d" % number
        while unique in source:
            unique += b"_"
        quoted = start.text != delimiter
        replacements.append((start.start_byte, start.end_byte,
                             b"'" + unique + b"'" if quoted else unique))
        position = max(line_end + 1, body_resumes)
        while position < len(source):
            line_end = source.find(b"\n", position)
            if line_end == -1:
                line_end = len(source)
            line = source[position:line_end]
            compared = line.lstrip(b"\t") if dashed else line
            # Inside $( ... ), bash also ends the body at the delimiter followed by the closing ).
            if compared == delimiter or compared.startswith(delimiter + b")"):
                begin = position + len(line) - len(compared)
                replacements.append((begin, begin + len(delimiter), unique))
                body_resumes = line_end + 1 if compared == delimiter else begin + len(delimiter)
                break
            position = line_end + 1
    if not replacements:
        return None
    rewritten = bytearray(source)
    for begin, end, new in sorted(replacements, reverse=True):
        rewritten[begin:end] = new
    # Quoted forms first, so a bare unique word inside one is not restored on its own.
    restore = sorted({(new.decode(), source[begin:end].decode("utf-8", "surrogatepass"))
                      for begin, end, new in replacements}, key=lambda pair: -len(pair[0]))
    return bytes(rewritten), restore


def _reread_with_heredoc_bodies_apart(source, tree, glob_markers):
    """Return the commands of a command line whose unquoted heredoc bodies broke the parse, or None.

    tree-sitter-bash parses an unquoted heredoc body as text with substitutions,
    and a lone quote there, which bash only reports when it expands the body,
    can turn every command after the heredoc into an error. Quoting each such
    delimiter keeps the bodies apart from the commands; each body is then read
    on its own, so its error stays inside it.
    """
    starts = [start for start in _heredoc_starts(tree.root_node)
              if not any(mark in _text(start) for mark in "'\"\\")]
    if not starts:
        return None
    quoted = bytearray(source)
    for start in reversed(starts):
        quoted[start.start_byte:start.end_byte] = b"'" + start.text + b"'"
    commands = _collect(parser().parse(bytes(quoted)).root_node, glob_markers, bytes(quoted))
    quoted_here = {"'" + _text(start) + "'" for start in starts}
    bodies = []
    for command in commands:
        for heredoc in command.heredocs:
            if heredoc.delimiter in quoted_here:
                heredoc.expanded = True
                if heredoc.body not in bodies:
                    bodies.append(heredoc.body)
    for body in bodies:
        # A substitution bash cannot close runs nothing, so what the body's errors hold is left out.
        body_source = ("cat <<EOF\n" + body + "EOF\n").encode("utf-8", "surrogatepass")
        inside = _collect(parser().parse(body_source).root_node, glob_markers, body_source,
                          skip_errors=True)
        commands[:0] = [SimpleCommand(list(found), ("heredoc body",) + found.child_shell,
                                      found.redirects, found.heredocs)
                        for found in inside if found[:1] != ["cat"] or found.child_shell]
    return commands
