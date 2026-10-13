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
parser_unavailable_hook_output, which asks for the user to be told. When the
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
LIST_OPERATORS = {"&&", "||", ";", "&"}
# What redirect() reads inside a heredoc_redirect; every other node there is commands.
HEREDOC_PARTS_READ_BY_REDIRECT = REDIRECT_NODE_TYPES | {
    "heredoc_start", "heredoc_body", "heredoc_end", "file_descriptor", "ERROR", "comment"}
# Characters a backslash keeps literal inside double quotes; before any other, the backslash stays.
DOUBLE_QUOTE_ESCAPABLE = set('"\\$`')


class ShellParserUnavailable(Exception):
    """tree-sitter-bash could not be imported, and installing it failed.

    install_output holds what the install printed, or why it did not run.
    """

    def __init__(self, install_output):
        super().__init__(install_output)
        self.install_output = install_output


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


class ChildShell(int):
    """One child shell a command runs in: its start offset, and its kind.

    kind is SUBSTITUTION for a command or process substitution, whose output
    becomes words of another command, PIPELINE_STAGE for a stage of a pipeline
    of two or more, and SUBSHELL for ( ... ). first_stage says whether a
    pipeline stage is its pipeline's first.
    """

    def __new__(cls, offset, kind, first_stage=False):
        shell = super().__new__(cls, offset)
        shell.kind = kind
        shell.first_stage = first_stage
        return shell

    def __repr__(self):
        return f"ChildShell({int(self)}, {self.kind!r}, first_stage={self.first_stage})"


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


class _Collector:
    def __init__(self, glob_markers, source, skip_errors=False):
        self.glob_markers = glob_markers
        self.source = source
        self.skip_errors = skip_errors
        self.commands = []

    def visit(self, node, child_shell, heredocs=()):
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
                       child_shell + (ChildShell(body.start_byte + start, SUBSTITUTION),))

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
            elif current:
                # A redirection belongs to the command written just before it.
                current[-1]["redirects"].append(item[1])
            else:
                # A statement that is only a redirection still runs its target's substitutions.
                self.visit(item[1], child_shell)
        for pipeline in pipelines:
            shared_heredocs = list(heredocs)
            for position, unit in enumerate(pipeline):
                first = unit["children"][0] if unit["children"] else unit["node"]
                unit_shell = (child_shell + (ChildShell(first.start_byte, PIPELINE_STAGE,
                                                        position == 0),)
                              if len(pipeline) > 1 else child_shell)
                redirects, trailing_words = [], []
                for redirect in unit["redirects"]:
                    shared_heredocs.extend(
                        self.redirect(redirect, unit_shell, redirects, trailing_words))
                if unit["node"].type in SIMPLE_COMMAND_NODE_TYPES:
                    self.simple_command(unit["node"], unit["children"], unit_shell,
                                        list(shared_heredocs), redirects, trailing_words)
                else:
                    self.visit(unit["node"], unit_shell, list(shared_heredocs))

    def _flatten(self, node, items):
        """Append node's commands, operators and redirections to items, in the order written."""
        kind = node.type
        if kind in SEQUENCE_NODE_TYPES:
            for child in node.children:
                if child.type == "comment":
                    continue
                if child.type in REDIRECT_NODE_TYPES:
                    items.append(("redirect", child))
                    if child.type == "heredoc_redirect":
                        self._flatten_heredoc_line(child, items)
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

    def _flatten_heredoc_line(self, heredoc_redirect, items):
        """Append what tree-sitter-bash puts after a heredoc's delimiter, other than the heredoc's own parts.

        tree-sitter-bash puts the rest of the heredoc's line, such as `| bash` or
        `|| { … }`, inside the heredoc_redirect. Every node there is read as
        commands, except the parts redirect() reads as the heredoc's.
        """
        arguments = heredoc_redirect.children_by_field_name("argument")
        for inner in heredoc_redirect.children:
            if inner.type in PIPE_OPERATORS:
                items.append(("pipe",))
            elif inner.is_named and inner not in arguments \
                    and inner.type not in HEREDOC_PARTS_READ_BY_REDIRECT:
                self._flatten(inner, items)

    def redirect(self, node, child_shell, redirects, trailing_words):
        """Add one redirection to a command's redirects; return the heredocs it feeds."""
        self.visit_inside_redirect(node, child_shell)
        if node.type != "heredoc_redirect":
            pair, extra = _redirect_parts(node, self.glob_markers)
            redirects.append(pair)
            trailing_words.extend(extra)
            return []
        heredoc = _heredoc_of(node)
        redirects.append(("<<", heredoc.body))
        arguments = node.children_by_field_name("argument")
        for inner in node.children:
            if inner.type == "heredoc_body":
                if heredoc.expanded:
                    self.expanded_heredoc_body(inner, child_shell)
            elif inner.type in REDIRECT_NODE_TYPES:
                self.visit_inside(inner, child_shell)
                pair, extra = _redirect_parts(inner, self.glob_markers)
                redirects.append(pair)
                trailing_words.extend(extra)
            elif inner in arguments:
                # A word after the delimiter on the heredoc's line is the command's word.
                self.visit_inside(inner, child_shell)
                trailing_words.append(word_value(inner, self.glob_markers))
            elif inner.type == "ERROR":
                self.visit_inside(inner, child_shell)
        return [heredoc]

    def visit_inside_redirect(self, node, child_shell):
        """Visit the substitutions in a file redirection's target."""
        if node.type != "heredoc_redirect":
            self.visit_inside(node, child_shell)

    def simple_command(self, node, children, child_shell, heredocs, redirects, trailing_words):
        words, own_redirects = [], []
        for child in children:
            self._read_command_part(child, child_shell, words, own_redirects)
        words.extend(trailing_words)
        if words:
            self.commands.append(SimpleCommand(words, child_shell, own_redirects + list(redirects),
                                               list(heredocs)))

    def _read_command_part(self, child, child_shell, words, redirects):
        """Add one child node of a command to its words or its redirections."""
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


def _separates_commands(gap):
    """Return whether the text between two parts of one command holds a line end bash stops at."""
    return b"\n" in gap.replace(b"\\\n", b"")


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
    if _read_in_a_new_process:
        return _simple_commands_in_a_new_process(command_text, glob_markers)
    try:
        parser()
    except ShellParserInstalledForANewProcess:
        _use_a_new_process()
        return _simple_commands_in_a_new_process(command_text, glob_markers)
    source = _source_with_heredoc_delimiters_ended(command_text.encode("utf-8", "surrogatepass"))
    rewritten = _source_with_unique_heredoc_delimiters(source)
    restore = []
    if rewritten is None:
        tree = parser().parse(source)
    else:
        source, restore, tree = rewritten
    source, tree = _source_with_heredoc_operators_after_their_words(source, tree)
    commands = None
    if tree.root_node.has_error:
        source, tree = _source_with_last_case_terminators_plain(source, tree)
    if tree.root_node.has_error:
        commands = _reread_with_heredoc_bodies_apart(source, tree, glob_markers)
    if commands is None:
        commands = _collect(tree.root_node, glob_markers, source)
    for command in commands:
        _restore_delimiters(command, restore)
    return commands


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
                           input=request.encode("utf-8", "surrogatepass"), capture_output=True,
                           timeout=INSTALL_TIMEOUT_SECONDS)
    except (OSError, subprocess.SubprocessError) as error:
        raise ShellParserUnavailable(f"reading the command in a new process failed: {error}") \
            from error
    if completed.returncode != 0:
        raise ShellParserUnavailable(
            "reading the command in a new process failed: "
            + (completed.stderr.decode("utf-8", "replace").strip() or f"exit {completed.returncode}"))
    return [SimpleCommand(found["words"],
                          tuple(ChildShell(*shell) for shell in found["child_shell"]),
                          [tuple(pair) for pair in found["redirects"]],
                          [Heredoc(*heredoc) for heredoc in found["heredocs"]])
            for found in json.loads(completed.stdout.decode("utf-8", "surrogatepass"))]


NEW_PROCESS_READ_FLAG = "--read-command-on-standard-input"


def _read_command_on_standard_input():
    request = json.loads(sys.stdin.buffer.read().decode("utf-8", "surrogatepass"))
    found = simple_commands(request["command"], request["glob_markers"])
    sys.stdout.buffer.write(json.dumps([
        {"words": list(command),
         "child_shell": [(int(shell), shell.kind, shell.first_stage)
                         for shell in command.child_shell],
         "redirects": command.redirects,
         "heredocs": [(heredoc.body, heredoc.expanded, heredoc.delimiter)
                      for heredoc in command.heredocs]}
        for command in found], ensure_ascii=False).encode("utf-8", "surrogatepass"))


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
            heredoc.body = restored(heredoc.body)


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


def _inside_heredoc_body(node):
    """Return whether tree-sitter-bash itself placed node inside a heredoc body.

    Such a heredoc start is inside a substitution in a body bash expands, so
    bash reads it as a heredoc of its own.
    """
    parent = node.parent
    while parent is not None:
        if parent.type == "heredoc_body":
            return True
        parent = parent.parent
    return False


UNIQUE_DELIMITER_PREFIX = b"NEDSCHORUS_HEREDOC_END_"
# Each pass corrects the heredocs the previous parse misplaced; real commands nest far less.
MAX_HEREDOC_RENAMING_PASSES = 8


def _source_with_heredoc_delimiters_ended(source):
    """Return source with a space after each heredoc delimiter that an operator follows directly.

    bash ends a delimiter word at ;, &, |, (, ), < or >, as in `cat <<EOF; ls`;
    tree-sitter-bash takes everything up to a space as the delimiter.
    """
    tree = parser().parse(source)
    ends = []
    for start in _heredoc_starts(tree.root_node):
        text, index, quote = start.text, 0, None
        while index < len(text):
            character = text[index:index + 1]
            if quote:
                quote = None if character == quote else quote
            elif character == b"\\":
                index += 1
            elif character in (b"'", b'"'):
                quote = character
            elif character in b";&|()<>":
                ends.append(start.start_byte + index)
                break
            index += 1
    if not ends:
        return source
    spaced = bytearray(source)
    for end in reversed(ends):
        spaced[end:end] = b" "
    return bytes(spaced)


def _heredoc_delimiter(start):
    """Return the word that ends a heredoc's body: the delimiter with bash's quote removal."""
    text, word, index = start.text, bytearray(), 0
    while index < len(text):
        character = text[index:index + 1]
        if character == b"\\":
            word += text[index + 1:index + 2]
            index += 2
        elif character == b"'":
            closing = text.find(b"'", index + 1)
            closing = len(text) if closing == -1 else closing
            word += text[index + 1:closing]
            index = closing + 1
        elif character == b'"':
            index += 1
            while index < len(text) and text[index:index + 1] != b'"':
                if text[index:index + 1] == b"\\" and text[index + 1:index + 2] in b'"\\$`':
                    index += 1
                word += text[index:index + 1]
                index += 1
            index += 1
        else:
            word += character
            index += 1
    return bytes(word)


def _source_with_unique_heredoc_delimiters(source):
    """Return (source with unique heredoc delimiters, [(unique, original)], tree), or None.

    bash ends a heredoc only at a line that is exactly its delimiter;
    tree-sitter-bash ends it at any line that starts with the delimiter, such
    as EOF2 inside a body ended by EOF, and reads the rest of the body as
    commands. Renaming each delimiter, and the line that ends its body, to a
    word found nowhere in the command leaves bash's reading unchanged and
    lets tree-sitter-bash find the same end. A heredoc start that a misread
    parse found inside another heredoc's body is part of that body, so it is
    left alone; each pass reparses, until no start is left to rename.
    """
    original = source
    replacements_made = []  # (unique word, delimiter as written, delimiter after quote removal)
    tree = parser().parse(source)
    for _pass in range(MAX_HEREDOC_RENAMING_PASSES):
        replacements = []  # (start, end, new bytes, original bytes)
        bodies = []  # (first byte, byte after the end line) of each body placed in this pass
        body_resumes = 0
        for start in _heredoc_starts(tree.root_node):
            nested = any(first <= start.start_byte < after for first, after in bodies)
            if nested and not _inside_heredoc_body(start):
                continue
            delimiter = _heredoc_delimiter(start)
            if not delimiter:
                continue
            dashed = source[:start.start_byte].rstrip(b" \t").endswith(b"<<-")
            line_end = _logical_line_end(source, start.end_byte)
            if line_end == -1:
                break
            renamed = delimiter.startswith(UNIQUE_DELIMITER_PREFIX)
            if renamed:
                unique = delimiter
            else:
                unique = UNIQUE_DELIMITER_PREFIX + b"%d" % len(replacements_made)
                while unique in original or unique in source:
                    unique += b"_"
                quoted = start.text != delimiter
                replacements.append((start.start_byte, start.end_byte,
                                     b"'" + unique + b"'" if quoted else unique, start.text))
                replacements_made.append((unique, start.text, delimiter))
            # A heredoc in a substitution inside another's body starts on its own next line;
            # heredocs that share a command line take their bodies one after another.
            body_first = position = line_end + 1 if nested else max(line_end + 1, body_resumes)
            while position < len(source):
                line_end = source.find(b"\n", position)
                if line_end == -1:
                    line_end = len(source)
                line = source[position:line_end]
                compared = line.lstrip(b"\t") if dashed else line
                # Inside $( ... ), bash also ends the body at the delimiter followed by ).
                if compared == delimiter or compared.startswith(delimiter + b")"):
                    begin = position + len(line) - len(compared)
                    if not renamed:
                        replacements.append((begin, begin + len(delimiter), unique, delimiter))
                    body_resumes = (line_end + 1 if compared == delimiter
                                    else begin + len(delimiter))
                    break
                position = line_end + 1
            else:
                body_resumes = len(source)
            bodies.append((body_first, body_resumes))
        if not replacements:
            break
        rewritten = bytearray(source)
        for begin, end, new, _old in sorted(replacements, reverse=True):
            rewritten[begin:end] = new
        source = bytes(rewritten)
        tree = parser().parse(source)
    if not replacements_made:
        return None
    restore = []
    for unique, start_text, delimiter in replacements_made:
        quoted = start_text != delimiter
        if quoted:
            restore.append(("'" + unique.decode() + "'", start_text.decode("utf-8", "surrogatepass")))
        restore.append((unique.decode(), delimiter.decode("utf-8", "surrogatepass")))
    # Quoted forms first, so a bare unique word inside one is not restored on its own.
    restore.sort(key=lambda pair: -len(pair[0]))
    return source, restore, tree


def _source_with_heredoc_operators_after_their_words(source, tree):
    """Return (source, tree) with each heredoc's line rewritten so tree-sitter-bash reads it as bash does.

    tree-sitter-bash misreads what follows a heredoc's delimiter on its line.
    bash reads `git push <<EOF --force origin b | cat` as
    `git push --force origin b <<EOF | cat`, since a redirection may stand
    anywhere among a command's words, so the words and redirections after the
    delimiter are moved in front of the `<<DELIMITER`, up to what ends the
    command. tree-sitter-bash also misreads a `;` or `&` on a heredoc's line,
    so the commands after the first one are moved to the line after the
    heredoc's body, where bash runs them in the same order.
    """
    moved = bytearray(source)
    changed = False
    for start in reversed(_heredoc_starts(tree.root_node)):
        operator = start.prev_sibling
        line_end = _logical_line_end(source, start.end_byte)
        if operator is None or operator.type not in ("<<", "<<-") or line_end == -1 \
                or _inside_heredoc_body(start):
            continue
        # A file descriptor written before << goes with it, as in `3<<EOF`.
        opening = start.parent.start_byte if start.parent.type == "heredoc_redirect" \
            else operator.start_byte
        rest = source[start.end_byte:line_end]
        end, ended_by = _command_end(rest)
        stretch, after = rest[:end], rest[end:].lstrip(b" \t")
        # A heredoc in a substitution that closes on its own line stays inside the substitution.
        if ended_by == ")":
            continue
        # Two heredocs on one line take their bodies in order, so neither is moved.
        if b"<<" in stretch or (not stretch.strip() and after == rest.lstrip(b" \t")):
            continue
        words = stretch.strip() + b" " if stretch.strip() else b""
        moved[opening:line_end] = (b" " + words + source[opening:start.end_byte] + b" " + after)
        changed = True
    if changed:
        source = bytes(moved)
        tree = parser().parse(source)
    return _source_with_commands_after_heredoc_lines_moved_below_their_bodies(source, tree)


def _source_with_commands_after_heredoc_lines_moved_below_their_bodies(source, tree):
    for start in reversed(_heredoc_starts(tree.root_node)):
        line_end = _logical_line_end(source, start.end_byte)
        if line_end == -1 or _inside_heredoc_body(start):
            continue
        rest = source[start.end_byte:line_end]
        separator = _first_list_separator(rest)
        if separator is None or b"<<" in rest:
            continue
        later = rest[separator + 1:].strip()
        body_end = _heredoc_body_end(source, line_end + 1, _heredoc_delimiter(start),
                                     source[:start.start_byte].rstrip(b" \t").endswith(b"<<-"))
        if not later or body_end is None:
            continue
        source = (source[:start.end_byte] + rest[:separator] + source[line_end:body_end]
                  + later + b"\n" + source[body_end:])
        tree = parser().parse(source)
    return source, tree


def _first_list_separator(text):
    """Return the offset of the first ; or & that ends a command in text, outside any nesting, or None."""
    probe = b": " + text
    found = []
    stack = [parser().parse(probe).root_node]
    while stack:
        node = stack.pop()
        if node.type in CHILD_SHELL_NODE_TYPES or node.type in TEXT_NODE_TYPES \
                or node.type in ("expansion", "simple_expansion", "compound_statement",
                                 "if_statement", "while_statement", "for_statement",
                                 "case_statement", "c_style_for_statement"):
            continue
        if not node.is_named and node.type in (";", "&"):
            found.append(node.start_byte - 2)
        stack.extend(node.children)
    return min(found, default=None)


def _heredoc_body_end(source, position, delimiter, dashed):
    """Return the offset just after the line that ends a heredoc body starting at position, or None."""
    while position < len(source):
        line_end = source.find(b"\n", position)
        line_end = len(source) if line_end == -1 else line_end
        line = source[position:line_end]
        if (line.lstrip(b"\t") if dashed else line) == delimiter:
            return min(line_end + 1, len(source))
        position = line_end + 1
    return None


def _logical_line_end(source, position):
    """Return the offset of the line end at or after position that a backslash does not continue, or -1."""
    while True:
        line_end = source.find(b"\n", position)
        if line_end == -1:
            return -1
        backslashes = len(source[:line_end]) - len(source[:line_end].rstrip(b"\\"))
        if backslashes % 2 == 0:
            return line_end
        position = line_end + 1


def _command_end(text):
    """Return (offset, ended_by) for where the first command in text ends.

    ended_by is the operator, ), or "#" for a comment, that ends it, or None at the end of text.
    """
    probe = b": " + text
    ends = []
    stack = [parser().parse(probe).root_node]
    while stack:
        node = stack.pop()
        if node.type == "comment":
            ends.append((node.start_byte, "#"))
            continue
        if node.type in CHILD_SHELL_NODE_TYPES or node.type in TEXT_NODE_TYPES \
                or node.type in ("expansion", "simple_expansion"):
            continue
        if not node.is_named and (node.type in PIPE_OPERATORS or node.type in LIST_OPERATORS
                                  or node.type == ")"):
            ends.append((node.start_byte, node.type))
        stack.extend(node.children)
    end, ended_by = min(ends, default=(len(probe), None))
    return max(0, end - 2), ended_by


LAST_CASE_TERMINATOR_PATTERN = re.compile(rb";;?&(\s*esac\b)")


def _source_with_last_case_terminators_plain(source, tree):
    """Return (source, tree) with ;;& or ;& before esac read as ;;, when that clears the error.

    tree-sitter-bash rejects a last case branch ended by ;;& or ;&, and loses
    every command after the case; before esac they act as ;; does.
    """
    def plain_terminator(match):
        if _inside_text(tree.root_node, match.start()):
            return match.group(0)
        return (b";;" + b" " * (len(match.group(0)) - len(match.group(1)) - 2)
                + match.group(1))
    plain = LAST_CASE_TERMINATOR_PATTERN.sub(plain_terminator, source)
    if plain == source:
        return source, tree
    plain_tree = parser().parse(plain)
    return (plain, plain_tree) if not plain_tree.root_node.has_error else (source, tree)


TEXT_NODE_TYPES = {"raw_string", "string", "ansi_c_string", "heredoc_body", "comment"}


def _inside_text(root, byte):
    """Return whether byte lies in a quoted string, a heredoc body or a comment of the tree."""
    node = root.descendant_for_byte_range(byte, byte + 1)
    while node is not None:
        if node.type in TEXT_NODE_TYPES:
            return True
        node = node.parent
    return False


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
        wrapper = "NEDSCHORUS_BODY_END"
        while wrapper in body:
            wrapper += "_"
        body_source = (f"cat <<{wrapper}\n" + body + f"{wrapper}\n").encode("utf-8", "surrogatepass")
        inside = _collect(parser().parse(body_source).root_node, glob_markers, body_source,
                          skip_errors=True)
        # Only the substitutions in an unquoted body run.
        commands[:0] = [SimpleCommand(list(found), (ChildShell(-1, SUBSTITUTION),) + found.child_shell,
                                      found.redirects, found.heredocs)
                        for found in inside if found[:1] != ["cat"] or found.inside_substitution()]
    return commands


if __name__ == "__main__" and sys.argv[1:] == [NEW_PROCESS_READ_FLAG]:
    _read_command_on_standard_input()
