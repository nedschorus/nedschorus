#!/usr/bin/env python3
"""Say when a search's empty result could not have found anything, for one of three causes.

The check reads a Bash command and its result. It speaks only when the command holds a
search, such as grep, rg or find, and the result is empty, and then only for these causes:

- An unquoted relative glob expanded to a name beginning with -, in the directory the
  command had cd'd into, before the -- that ends the options: the program read that name
  as an option.
- The agent's grep, which is ugrep, refuses the pattern of a bare grep with "exceeds
  complexity limits".
- A search program is not installed on the machine that ran it.

Each cause is a fact about the machine, which the command's output hides once the search's
stderr is discarded, so the check asks the machine: it lists a directory, asks whether a
program is installed, and runs the agent's ugrep with the agent's pattern on /dev/null. For
a command ssh runs elsewhere, it asks that machine over ssh, for the first and third causes.

It does not handle: a `2>/dev/null`, a swallowed exit status or a cut input, which are not
causes; a glob or a cd held in a variable, or one under bash -c; a remote command's
patterns, which no agent's grep reads; and an absolute glob, which cannot begin with -.
It answers for the machine as it is now, so over old transcripts a program installed since,
or a directory changed since, gives a different answer than it would have then.

It can fail when ssh, the directory listing or the agent's ugrep cannot run; it then says
which cause it could not check, and the command-line mode exits 3. It changes nothing on
any machine, and runs nothing of the agent's command but the grep pattern on /dev/null.
"""

import argparse
import collections
import fnmatch
import importlib.util
import itertools
import json
import os
import pathlib
import re
import shlex
import shutil
import subprocess
import sys

PROGRAM = "unvalidated-negative-result-check"

EXIT_QUIET = 0
EXIT_FIRED = 1
EXIT_BAD_INVOCATION = 2
EXIT_A_CAUSE_COULD_NOT_BE_CHECKED = 3

_shell_reader_spec = importlib.util.spec_from_file_location(
    "shell_command_tree_sitter_bash_reader_common",
    pathlib.Path(__file__).resolve().parents[1] / "nc-systems" / "general-tools"
    / "shell-command-tree-sitter-bash-reader-common.py")
shell_reader = importlib.util.module_from_spec(_shell_reader_spec)
_shell_reader_spec.loader.exec_module(shell_reader)

SEARCH_PROGRAMS = frozenset({
    "grep", "egrep", "fgrep", "zgrep", "rg", "ugrep", "ag", "ack", "fd", "find"})

GLOB_DASH_NAME = "glob-expanded-to-a-name-beginning-with-dash"
PATTERN_TOO_COMPLEX = "agents-grep-refused-the-search-pattern-as-too-complex"
PROGRAM_MISSING = "search-program-missing-on-the-machine-that-ran-it"

# Private-use characters mark the glob characters the shell would expand.
GLOB_MARKERS = {"*": "\ue000", "?": "\ue001", "[": "\ue002", "]": "\ue003"}
MARKED_GLOB_CHARACTERS = {marker: character for character, marker in GLOB_MARKERS.items()}

UNRESOLVABLE_DIRECTORY = re.compile(r"[$`]")

# Claude Code's grep shell function hands grep to its own binary run as ugrep, with these
# options first, except when an argument matches its pass-through list, below.
AGENTS_GREP_LEADING_OPTIONS = (
    "-G", "--ignore-files", "--hidden", "-I", "--exclude-dir=.git", "--exclude-dir=.svn",
    "--exclude-dir=.hg", "--exclude-dir=.bzr", "--exclude-dir=.jj", "--exclude-dir=.sl")
AGENTS_GREP_PASSES_TO_SYSTEM_GREP = (
    "-*-filter*", "-*-pager*", "-*-view*", "-*-format-open*", "-*-config*", "---*", "-@*",
    "-*-save-config*", "-[Zz]*", "-[!-]*[Zz]*", "--null", "--null-data")
AGENTS_GREP_REFUSAL = "exceeds complexity limits"

GREP_SHORT_OPTIONS_TAKING_A_VALUE = "efmABCdD"
GREP_LONG_OPTIONS_TAKING_A_VALUE = frozenset({
    "--regexp", "--file", "--max-count", "--after-context", "--before-context", "--context",
    "--directories", "--devices", "--include", "--exclude", "--exclude-dir", "--exclude-from",
    "--label", "--binary-files", "--group-separator"})

PROBE_TIMEOUT_SECONDS = 15
SSH_OPTIONS = ("-o", "BatchMode=yes", "-o", "ConnectTimeout=5")

COUNT_LINE = re.compile(r"^(?P<path>.*):(?P<count>\d+)$")

# A failed command's output holds stderr and stdout together; diagnostics are not results.
DIAGNOSTIC_LINE = re.compile(
    r"^(?:\(eval\)(?::\w+)?:\d+"
    r"|(?:[^\s:]*/)?(?:zsh|bash|sh|dash|ksh)(?::\d+)?"
    r"|[^\s:]+: line \d+"
    r"|(?:[^\s:]*/)?[^\s:/.\d][^\s:/.]*):\s[^\n]*?"
    r"(?:not found|No such file or directory|Permission denied"
    r"|Is a directory|cannot open|unrecognized option|invalid option"
    r"|unknown option|Connection refused|Could not resolve hostname"
    r"|Operation timed out|exceeds complexity limits|error)"
    r"|^(?:fatal|usage): ", re.IGNORECASE)

EXIT_CODE_LINE = re.compile(r"^Exit code (\d+)\n?")


class MachineStateQueryGotNoAnswer(Exception):
    """A question to a machine got no answer, so its cause is unchecked."""


class Cause(collections.namedtuple("Cause", "signal instruction")):
    """One cause found, with what the agent does about it."""


class Verdict:
    """The check's answer about one command and its result."""

    def __init__(self, applicable, causes=(), unchecked=(), reason=None):
        self.applicable = applicable
        self.causes = list(causes)
        self.unchecked = list(unchecked)
        self.reason = reason

    @property
    def fires(self):
        return bool(self.causes)

    @property
    def signals(self):
        return [cause.signal for cause in self.causes]

    def as_dict(self):
        return {"applicable": self.applicable, "signals": self.signals,
                "instructions": [cause.instruction for cause in self.causes],
                "unchecked": self.unchecked, "reason": self.reason}


def ask(runner, argv, **keywords):
    try:
        return runner(argv, capture_output=True, text=True, stdin=subprocess.DEVNULL,
                      timeout=PROBE_TIMEOUT_SECONDS, **keywords)
    except (OSError, subprocess.SubprocessError) as error:
        raise MachineStateQueryGotNoAnswer(f"{argv[0]} could not run: {error}") from None


def remote_directory_spelling(directory):
    """Return directory as remote shell text, a leading ~ left for the remote shell."""
    if directory == "~":
        return '"$HOME"'
    if directory.startswith("~/"):
        return '"$HOME"/' + shlex.quote(directory[2:])
    return shlex.quote(directory)


class Machines:
    """Answers about the machine that ran a command, or the one ssh reached.

    host None is this machine. Answers are kept, so each question is asked once.
    """

    def __init__(self, runner=subprocess.run, environment=os.environ):
        self.runner = runner
        self.environment = environment
        self.answers = {}

    def _kept(self, key, find):
        if key not in self.answers:
            try:
                self.answers[key] = find()
            except MachineStateQueryGotNoAnswer as error:
                self.answers[key] = error
        if isinstance(self.answers[key], MachineStateQueryGotNoAnswer):
            raise self.answers[key]
        return self.answers[key]

    def directory_entries(self, host, directory):
        def find():
            if host is None:
                try:
                    return os.listdir(directory)
                except OSError as error:
                    raise MachineStateQueryGotNoAnswer(f"listing {directory} failed: {error}") from None
            finished = ask(self.runner, ["ssh", *SSH_OPTIONS, host,
                                         f"ls -A -- {remote_directory_spelling(directory)}"])
            if finished.returncode != 0:
                raise MachineStateQueryGotNoAnswer(f"listing {directory} on {host} over ssh exited "
                                  f"{finished.returncode}: {finished.stderr.strip()}")
            return finished.stdout.splitlines()
        return self._kept(("entries", host, directory), find)

    def program_installed(self, host, program):
        def find():
            if host is None:
                return shutil.which(program) is not None
            finished = ask(self.runner, ["ssh", *SSH_OPTIONS, host,
                                         f"command -v -- {shlex.quote(program)}"])
            # command -v exits 1 for a program it cannot find; ssh's own failure is 255.
            if finished.returncode not in (0, 1):
                raise MachineStateQueryGotNoAnswer(f"asking {host} over ssh whether {program} is installed "
                                  f"exited {finished.returncode}: {finished.stderr.strip()}")
            return finished.returncode == 0
        return self._kept(("installed", host, program), find)

    def agents_grep(self):
        # The same lookup as Claude Code's grep shell function.
        binary = self.environment.get("CLAUDE_CODE_EXECPATH") or ""
        if not os.access(binary, os.X_OK):
            binary = os.path.join(self.environment.get("HOME") or "/", ".local/bin/claude")
        if not os.access(binary, os.X_OK):
            raise MachineStateQueryGotNoAnswer("the agent's grep, the claude binary run as ugrep, was not found "
                              "at $CLAUDE_CODE_EXECPATH or ~/.local/bin/claude")
        return binary

    def agents_grep_refuses(self, options_and_patterns, directory):
        def find():
            finished = ask(self.runner,
                           ["ugrep", *AGENTS_GREP_LEADING_OPTIONS, *options_and_patterns,
                            os.devnull],
                           executable=self.agents_grep(),
                           # A transcript replayed on another machine names directories absent here.
                           cwd=directory if directory and os.path.isdir(directory) else None)
            # ugrep exits 1 for no match and 2 for an error; any other answer says nothing.
            if finished.returncode in (0, 1):
                return False
            if finished.returncode == 2 and AGENTS_GREP_REFUSAL in finished.stderr:
                return True
            raise MachineStateQueryGotNoAnswer(f"the agent's grep, run on the pattern {shlex.join(options_and_patterns)}, "
                                               f"exited {finished.returncode} without its "
                                               f"\"{AGENTS_GREP_REFUSAL}\" refusal: {finished.stderr.strip()}")
        return self._kept(("refuses", directory, tuple(options_and_patterns)), find)


def plain(word):
    return "".join(MARKED_GLOB_CHARACTERS.get(character, character) for character in word)


def fnmatch_pattern(marked):
    """Return an fnmatch pattern expanding only the marked glob characters."""
    return "".join(MARKED_GLOB_CHARACTERS[character] if character in MARKED_GLOB_CHARACTERS
                   else "[" + character + "]" if character in "*?[]" else character
                   for character in marked)


class Placed(collections.namedtuple("Placed", "host directory words program_index redirects")):
    """A simple command with the machine and directory it ran in; directory None is unknown.
    redirects holds only the command's own, not those of a { } or ( ) around it."""

    @property
    def program(self):
        if self.program_index is None:
            return ""
        return os.path.basename(plain(self.words[self.program_index]))


def split_into_simple_commands_with_the_machine_and_directory_each_runs_in(command, cwd, host=None):
    """Return every simple command in command, with where it ran, ssh's remote ones included."""
    placed = []
    directories = {(): cwd}  # A child shell's cd does not change its parent's directory.
    for words in shell_reader.simple_commands(command, glob_markers=GLOB_MARKERS):
        shell = words.child_shell
        enclosing = shell
        while enclosing not in directories:
            enclosing = enclosing[:-1]
        directory = directories[enclosing]
        index, _ = shell_reader.simple_command_program_index_skipping_wrappers(words)
        if index is not None and shell_reader.is_program(words[index], "cd"):
            target = words[index + 1] if index + 1 < len(words) else "~"
            if host is None:
                target = shell_reader.shell_word_tilde_prefix_expand_as_bash_would(target)
            target = str(target)
            if UNRESOLVABLE_DIRECTORY.search(target) or plain(target) != target:
                directories[shell] = None
            elif target.startswith(("/", "~")):
                directories[shell] = os.path.normpath(target)
            elif directory is not None:
                directories[shell] = os.path.normpath(os.path.join(directory, target))
            else:
                directories[shell] = None
            continue
        placed.append(Placed(host, directory, list(words), index, tuple(words.redirects)))
        if host is None and index is not None and shell_reader.is_program(words[index], "ssh"):
            arguments = [plain(word) for word in words[index + 1:]]
            remote = shell_reader.ssh_remote_command(arguments)
            destination = ssh_destination(arguments)
            if remote and destination:
                placed.extend(split_into_simple_commands_with_the_machine_and_directory_each_runs_in(remote, "~", host=destination))
    return placed


def ssh_destination(arguments):
    """Return the machine ssh connects to, read as ssh_remote_command reads the options."""
    index = 0
    while index < len(arguments):
        word = arguments[index]
        if word == "--":
            index += 1
            break
        if not word.startswith("-") or word == "-":
            break
        letters = word[1:]
        for position, letter in enumerate(letters):
            if letter in shell_reader.SSH_VALUE_LETTERS:
                index += position == len(letters) - 1
                break
        index += 1
    return arguments[index] if index < len(arguments) else None


def is_search(command):
    program = command.program
    if program in SEARCH_PROGRAMS:
        return True
    return program == "git" and "grep" in command.words[command.program_index + 1:]


def empty_shape_of(stdout):
    """Return the empty-result shape, or None for a result that is not empty."""
    text = (stdout or "").strip()
    if not text:
        return "no-output"
    if text == "0":
        return "zero-count"
    lines = [line for line in text.splitlines() if line.strip()]
    matches = [COUNT_LINE.match(line) for line in lines]
    if all(matches) and all(int(match.group("count")) == 0 for match in matches):
        return "zero-count-lines"
    return None


def without_diagnostics(text):
    return "\n".join(line for line in (text or "").splitlines()
                     if not DIAGNOSTIC_LINE.match(line))


def machine_name(host):
    return host if host else "this machine"


def names_a_word_expanded_to(command, word, machines, unchecked):
    """Return, sorted, the names that the first path component of word matches in the
    directory command ran in; or None, with one line in unchecked, when that directory could
    not be listed."""
    try:
        entries = machines.directory_entries(command.host, command.directory)
    except MachineStateQueryGotNoAnswer as error:
        line = (f"whether `{plain(word)}` expanded, in "
                f"{command.directory}, the directory the command ran in, "
                f"to a name beginning with -: {error}")
        if line not in unchecked:
            unchecked.append(line)
        return None
    pattern = fnmatch_pattern(word.split("/", 1)[0])
    return sorted(name for name in entries if fnmatch.fnmatchcase(name, pattern))


GREP_PROGRAMS = frozenset({"grep", "egrep", "fgrep", "zgrep", "ugrep"})


def grep_arguments_options_end_and_option_value_positions(arguments):
    """Return where grep's options end in arguments, and the positions before it of the
    words grep reads as an option's value. The end is the position of the -- that grep reads
    as their end, or len(arguments) when there is none."""
    values = set()
    index = 0
    while index < len(arguments):
        argument = arguments[index]
        index += 1
        if argument == "--":
            return index - 1, frozenset(values)
        if argument.startswith("--"):
            if argument in GREP_LONG_OPTIONS_TAKING_A_VALUE:
                values.add(index)
                index += 1
        elif argument.startswith("-") and argument != "-":
            for position, letter in enumerate(argument[1:], start=1):
                if letter in GREP_SHORT_OPTIONS_TAKING_A_VALUE:
                    if position == len(argument) - 1:
                        values.add(index)
                        index += 1
                    break
    return len(arguments), frozenset(value for value in values if value < len(arguments))


def glob_dash_name_causes(placed, machines, unchecked):
    causes = []
    for command in placed:
        if command.directory is None or command.program_index is None:
            continue
        words = command.words[command.program_index + 1:]
        arguments = [plain(word) for word in words]
        # Only grep's options that take a value are known; another program's options end at
        # its first --.
        options_end, option_values = (
            grep_arguments_options_end_and_option_value_positions(arguments)
            if command.program in GREP_PROGRAMS
            else (arguments.index("--") if "--" in arguments else len(arguments), frozenset()))
        for position, word in enumerate(words[:options_end]):
            first_component = word.split("/", 1)[0]
            if plain(first_component) == first_component or word.startswith(("/", "~")):
                continue
            names = names_a_word_expanded_to(command, word, machines, unchecked)
            if names is None:
                break
            # An option's value takes only the first name of its glob; grep reads the rest as
            # it reads any other word.
            dashed = [name for name in names[position in option_values:] if name.startswith("-")]
            if dashed:
                causes.append(Cause(GLOB_DASH_NAME, (
                    f"`{plain(word)}` expanded, in {command.directory} on "
                    f"{machine_name(command.host)}, to names beginning with -, such as "
                    f"`{dashed[0]}`, which {command.program} read as options, not as files, "
                    f"so the search did not read those files.\n"
                    f"Run the search again with ./ in front of the glob, as in "
                    f"`./{plain(word)}`, "
                    f"{REPORT_FROM_THE_NEW_SEARCH}.\n"
                    f"From now on, write ./ in front of every relative glob that names files.")))
                break
    return causes


def agents_grep_options_and_patterns_without_file_names(command, machines, unchecked):
    """Return the options and patterns of a grep that Claude Code's grep function hands to
    ugrep, its file names left out; or None for any other command. A word before -- that
    begins with - stays in when its expansion could not be checked: with one line in
    unchecked when the directory the command ran in could not be listed, and with none when
    that directory is not known."""
    # Only a bare grep run by this machine's shell reaches the function; a wrapper such as
    # xargs or timeout runs the system grep.
    if command.host is not None or command.program_index is None \
            or command.words[command.program_index] != "grep" \
            or any(not shell_reader.ENVIRONMENT_ASSIGNMENT_PATTERN.match(word)
                   for word in command.words[:command.program_index]):
        return None
    words = command.words[command.program_index + 1:]
    arguments = [plain(word) for word in words]
    if any(fnmatch.fnmatchcase(argument, rule) for argument in arguments
           for rule in AGENTS_GREP_PASSES_TO_SYSTEM_GREP):
        return None
    # A word that begins with - and holds an unquoted glob character names files only when
    # the shell expanded it, and glob_dash_name_causes judges those names; one that matched
    # nothing reached grep as written, as an option or an option's value such as
    # --include=*.md. After the -- that ends the options every word is a pattern or a file
    # name, whatever it begins with, and the loop below keeps at most the first.
    options_end, option_values = grep_arguments_options_end_and_option_value_positions(arguments)
    arguments = [argument for position, (word, argument) in enumerate(zip(words, arguments))
                 if not (position < options_end and position not in option_values
                         and argument.startswith("-") and plain(word) != word
                         and command.directory is not None
                         and names_a_word_expanded_to(command, word, machines, unchecked))]
    kept = []
    pattern_given = False
    index = 0
    while index < len(arguments):
        argument = arguments[index]
        index += 1
        if argument == "--":
            if not pattern_given and index < len(arguments):
                kept += ["--", arguments[index]]
            return kept
        if argument.startswith("--"):
            name = argument.split("=", 1)[0]
            kept.append(argument)
            pattern_given = pattern_given or name in ("--regexp", "--file")
            if name in GREP_LONG_OPTIONS_TAKING_A_VALUE and "=" not in argument \
                    and index < len(arguments):
                kept.append(arguments[index])
                index += 1
            continue
        if argument.startswith("-") and argument != "-":
            kept.append(argument)
            for position, letter in enumerate(argument[1:], start=1):
                if letter in GREP_SHORT_OPTIONS_TAKING_A_VALUE:
                    pattern_given = pattern_given or letter in "ef"
                    if position == len(argument) - 1 and index < len(arguments):
                        kept.append(arguments[index])
                        index += 1
                    break
            continue
        if not pattern_given:
            kept.append(argument)
            pattern_given = True
    return kept


REDIRECT_OPERATOR = re.compile(r"(\d*)(>>|>\||>&|<&|>|<>|<)(-?)")


def does_command_own_redirect_send_stderr_elsewhere_than_stdout(command):
    """Whether the command's own redirects, read in order as bash applies them, leave its stderr
    pointing anywhere but the stdout the command started with, which the agent is shown."""
    shown, closed = "shown", "closed"
    points_to = {1: shown, 2: shown}

    def file_destination(target):
        special = re.fullmatch(r"/dev/(?:std(out|err)|fd/(\d+))", target)
        if special:
            source = {"out": 1, "err": 2}.get(special.group(1)) or int(special.group(2))
            return points_to.get(source, closed)
        return ("file", target)

    for operator, target in command.redirects:
        descriptor = re.fullmatch(r"(\d+)(-?)", target)
        if operator in ("&>", "&>>") or operator == ">&" and not descriptor and target != "-":
            points_to[1] = points_to[2] = file_destination(target)
            continue
        match = REDIRECT_OPERATOR.fullmatch(operator)
        if not match:
            continue  # A here-document or here-string feeds stdin only.
        number, kind, dash = match.groups()
        fd = int(number) if number else (0 if kind.startswith("<") else 1)
        if kind in (">&", "<&"):
            if dash or target in ("-", ""):
                points_to[fd] = closed
            elif descriptor:
                source = int(descriptor.group(1))
                points_to[fd] = points_to.get(source, closed)
                if descriptor.group(2) and source != fd:
                    points_to[source] = closed  # A move, such as 2>&1-, closes its source.
            continue
        points_to[fd] = file_destination(target)
    return points_to[2] != shown


def pattern_too_complex_causes(placed, machines, unchecked, output=""):
    # A refusal the agent saw is not hidden, and the warning says it was. A refusal shown is
    # taken for that of each grep whose own redirect let it through.
    refusal_shown = AGENTS_GREP_REFUSAL in (output or "")
    causes = []
    for command in placed:
        if refusal_shown and not does_command_own_redirect_send_stderr_elsewhere_than_stdout(command):
            continue
        arguments = agents_grep_options_and_patterns_without_file_names(
            command, machines, unchecked)
        if not arguments:
            continue
        try:
            refused = machines.agents_grep_refuses(arguments, command.directory)
        except MachineStateQueryGotNoAnswer as error:
            unchecked.append(f"whether the agent's grep refuses the pattern of "
                             f"`{shlex.join(arguments)}`: {error}")
            continue
        if refused:
            causes.append(Cause(PATTERN_TOO_COMPLEX, (
                f"The agent's grep, which is ugrep, refuses the pattern of "
                f"`grep {shlex.join(arguments)}` with \"{AGENTS_GREP_REFUSAL}\", so that "
                f"grep searched nothing; its 2>/dev/null or a later stage of the pipe hid "
                f"the refusal.\n"
                f"Run the search again with rg, or with a grep pattern that holds no bounded "
                f"repeat such as .{{0,180}}, {REPORT_FROM_THE_NEW_SEARCH}.\n"
                f"From now on, search with rg when a pattern needs a bounded repeat.")))
    return causes


def not_found_error_shown(output, program):
    """Whether output holds the shell's "not found" line for program, which the agent saw."""
    name = os.path.basename(program)
    return any("not found" in line and re.search(rf"(?<![\w.-]){re.escape(name)}(?![\w.-])", line)
               for line in (output or "").splitlines())


def program_missing_causes(placed, machines, unchecked, output=""):
    causes = []
    asked = set()
    for command in placed:
        if not is_search(command):
            continue
        program = plain(command.words[command.program_index])
        if (command.host, program) in asked or not_found_error_shown(output, program):
            continue
        asked.add((command.host, program))
        try:
            installed = machines.program_installed(command.host, program)
        except MachineStateQueryGotNoAnswer as error:
            unchecked.append(f"whether {program} is installed on "
                             f"{machine_name(command.host)}: {error}")
            continue
        if not installed:
            causes.append(Cause(PROGRAM_MISSING, (
                f"{program} is not installed on {machine_name(command.host)}, so that search "
                f"ran nothing; its 2>/dev/null or a later stage of the pipe hid the "
                f"\"command not found\".\n"
                f"Run the search again on {machine_name(command.host)} with a program "
                f"installed there, such as grep -r, {REPORT_FROM_THE_NEW_SEARCH}.")))
    return causes


def judge_command_result(command, cwd, stdout="", exit_code=0, machines=None):
    """Decide whether the empty result of command, run in cwd, could not have found anything.

    stdout is the result as the agent saw it: for a command that exited nonzero, its stdout
    and stderr together. Raises shell_reader.ShellParserUnavailable when the command cannot
    be read.
    """
    if machines is None:
        machines = Machines()
    results = without_diagnostics(stdout) if exit_code else stdout
    if empty_shape_of(results) is None:
        return Verdict(False, reason="the result is not empty")
    placed = split_into_simple_commands_with_the_machine_and_directory_each_runs_in(command, cwd)
    if not any(is_search(command) for command in placed):
        return Verdict(False, reason="no search in the command")
    unchecked = []
    causes = (glob_dash_name_causes(placed, machines, unchecked)
              + pattern_too_complex_causes(placed, machines, unchecked, stdout)
              + program_missing_causes(placed, machines, unchecked, stdout))
    return Verdict(True, causes=causes, unchecked=unchecked,
                   reason=None if causes else "none of the three causes was found")


REPORT_FROM_THE_NEW_SEARCH = (
    "and report from that search instead: what it finds, or, if it finds nothing, that "
    "what you sought is absent")

UNCHECKED_NEXT_STEP = (
    "Before you report that what you sought is absent, run the search by itself, in the "
    "directory it ran in, with no 2>/dev/null and nothing piped after it, and read its "
    "stderr and its exit status.\n"
    "If it exits 1 and prints nothing on stderr, it found no match, and you may report "
    "that what you sought is absent.\n"
    "If it exits 2 or more, or prints an error, fix what the error names and run it again.")


def report_lines(verdict):
    lines = []
    if verdict.fires:
        lines.append(f"{PROGRAM}: the search in this command found nothing, but it could "
                     f"not have found anything, so its empty result does not show that what "
                     f"it sought is absent. Do not report absence from it.")
        lines += [cause.instruction for cause in verdict.causes]
        lines.append("If you already told someone that what you sought is absent, correct "
                     "that once the new search has run.")
    if verdict.unchecked:
        lines += [f"{PROGRAM} could not check {what}." for what in verdict.unchecked]
        lines.append(UNCHECKED_NEXT_STEP)
    return lines


def unvalidated_negative_result_warning_post_tool_use_hook(stdin, stdout, machines=None):
    """Read a PostToolUse or PostToolUseFailure payload for Bash; print a warning, if any."""
    try:
        payload = json.load(stdin)
    except ValueError:
        return EXIT_QUIET
    if not isinstance(payload, dict) or payload.get("tool_name") != "Bash":
        return EXIT_QUIET
    command = (payload.get("tool_input") or {}).get("command") or ""
    event = payload.get("hook_event_name") or "PostToolUse"
    if event == "PostToolUseFailure":
        error = payload.get("error") or ""
        match = EXIT_CODE_LINE.match(error)
        if not match or payload.get("is_interrupt"):
            return EXIT_QUIET
        exit_code, output = int(match.group(1)), error[match.end():]
    else:
        response = payload.get("tool_response") or {}
        if not isinstance(response, dict) or response.get("interrupted"):
            return EXIT_QUIET
        exit_code, output = 0, response.get("stdout") or ""
    cwd = payload.get("cwd") or os.getcwd()
    try:
        verdict = judge_command_result(command, cwd, output, exit_code, machines)
    except shell_reader.ShellParserUnavailable as error:
        lines = [f"{PROGRAM} could not read this command, so it did not check whether its "
                 f"empty result could have found anything: {error}", UNCHECKED_NEXT_STEP]
    else:
        lines = report_lines(verdict)
    if lines:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": event, "additionalContext": "\n".join(lines)}}), file=stdout)
    return EXIT_QUIET


def bash_pairs_in_transcript(path):
    """Yield (command, cwd, exit_code, output) for each Bash run a transcript records."""
    # toolUseResult is a dict on success, and a string holding both streams on failure.
    commands = {}
    try:
        handle = open(path, encoding="utf-8", errors="replace")
    except OSError:
        return
    with handle:
        for line in handle:
            try:
                record = json.loads(line)
            except ValueError:
                continue
            content = (record.get("message") or {}).get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "tool_use" and block.get("name") == "Bash":
                    commands[block.get("id")] = (
                        (block.get("input") or {}).get("command", ""), record.get("cwd") or "")
                elif block.get("type") == "tool_result" and block.get("tool_use_id") in commands:
                    command, cwd = commands.pop(block["tool_use_id"])
                    result = record.get("toolUseResult")
                    if isinstance(result, dict):
                        if result.get("backgroundTaskId") or result.get("interrupted"):
                            continue
                        yield command, cwd, 0, result.get("stdout") or ""
                    elif isinstance(result, str):
                        match = re.match(r"^Error: Exit code (\d+)\n?", result)
                        if match:
                            yield command, cwd, int(match.group(1)), result[match.end():]


def measure_transcripts(directories, limit=None, top=10, out=sys.stdout, machines=None):
    """Print how often the check fires over the Bash runs that transcripts record."""
    machines = machines or Machines()
    counts = collections.Counter()
    by_signal = collections.Counter()
    by_command = collections.Counter()
    pairs = ((transcript,) + pair for directory in directories
             for transcript in sorted(pathlib.Path(directory).rglob("*.jsonl"))
             for pair in bash_pairs_in_transcript(transcript))
    for transcript, command, cwd, exit_code, output in itertools.islice(pairs, limit):
        counts["pairs"] += 1
        try:
            verdict = judge_command_result(command, cwd, output, exit_code, machines)
        except shell_reader.ShellParserUnavailable:
            counts["unreadable"] += 1
            continue
        if not verdict.applicable:
            continue
        counts["empty searches"] += 1
        counts["unchecked"] += bool(verdict.unchecked)
        if verdict.fires:
            counts["fired"] += 1
            by_signal.update(set(verdict.signals))
            by_command[" ".join(command.split())[:100]] += 1
    print(f"{PROGRAM}: measurement over recorded Bash runs", file=out)
    for name in ("pairs", "unreadable", "empty searches", "unchecked", "fired"):
        print(f"  {name:16s}: {counts[name]}", file=out)
    for signal, count in by_signal.most_common():
        print(f"    {count:6d}  {signal}", file=out)
    print(f"  the {top} commands that fire most often:", file=out)
    for head, count in by_command.most_common(top):
        print(f"    {count:6d}  {head}", file=out)
    return counts, by_signal


def main(argv=None, stdin=sys.stdin, stdout=sys.stdout, machines=None):
    parser = argparse.ArgumentParser(
        prog=PROGRAM,
        description="Say when a search's empty result could not have found anything.")
    parser.add_argument("--command", help="the command that ran")
    parser.add_argument("--cwd", help="the directory it ran in; the default is this one")
    parser.add_argument("--exit-code", type=int, default=0)
    parser.add_argument("--output-file", help="what the command printed; for a nonzero "
                                              "exit, stdout and stderr together")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--transcripts", action="append", default=[], metavar="DIR")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument("--run-as-claude-code-post-tool-use-hook", action="store_true",
                        help="read a PostToolUse or PostToolUseFailure payload on stdin")
    arguments = parser.parse_args(argv)

    modes = [arguments.command is not None, bool(arguments.transcripts),
             arguments.run_as_claude_code_post_tool_use_hook]
    if sum(modes) != 1:
        print(f"{PROGRAM}: give exactly one of --command, --transcripts, "
              f"--run-as-claude-code-post-tool-use-hook", file=sys.stderr)
        return EXIT_BAD_INVOCATION
    if arguments.run_as_claude_code_post_tool_use_hook:
        return unvalidated_negative_result_warning_post_tool_use_hook(stdin, stdout, machines)
    if arguments.transcripts:
        measure_transcripts(arguments.transcripts, arguments.limit, arguments.top, stdout,
                            machines)
        return EXIT_QUIET
    output = ""
    if arguments.output_file:
        with open(arguments.output_file, encoding="utf-8", errors="replace") as handle:
            output = handle.read()
    try:
        verdict = judge_command_result(arguments.command, arguments.cwd or os.getcwd(),
                                       output, arguments.exit_code, machines)
    except shell_reader.ShellParserUnavailable as error:
        print(f"{PROGRAM}: could not read the command: {error}", file=sys.stderr)
        return EXIT_A_CAUSE_COULD_NOT_BE_CHECKED
    if arguments.json:
        print(json.dumps(verdict.as_dict(), indent=2), file=stdout)
    else:
        lines = report_lines(verdict) or [
            f"{PROGRAM}: nothing to report ({verdict.reason})."]
        print("\n".join(lines), file=stdout)
    if verdict.fires:
        return EXIT_FIRED
    if verdict.unchecked:
        return EXIT_A_CAUSE_COULD_NOT_BE_CHECKED
    return EXIT_QUIET


if __name__ == "__main__":
    sys.exit(main())
