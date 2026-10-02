#!/usr/bin/env python3
"""Decide whether an empty search result is evidence of absence."""

import argparse
import glob
import itertools
import json
import os
import pathlib
import re
import shlex
import subprocess
import sys
import tempfile

PROGRAM = "unvalidated-negative-result-check"

EXIT_QUIET = 0
EXIT_FIRED = 1
EXIT_BAD_INVOCATION = 2

FIXTURES_DIRECTORY_NAME = "unvalidated-negative-result-check-fixtures"

SEARCH_PROGRAMS = frozenset({
    "grep", "egrep", "fgrep", "zgrep", "rg", "ripgrep", "ag", "ack", "fd",
    "find", "ugrep",
})

# find and fd can execute actions, so replaying them could modify the corpus.
CONTROL_PROGRAMS = SEARCH_PROGRAMS - {"find", "fd"}

OPTION_THAT_RUNS_ANOTHER_PROGRAM = re.compile(
    r"^(?:--pre(?:=|$)|--filter(?:=|$)|--open-files-in-pager|-[A-Za-z]*O)")

# Use lookahead, not a word boundary: compact flags such as -c1 have no boundary after c.
TRUNCATING_STAGE = re.compile(
    r"^(?:cut\s+(?:[^|]*\s)?-[cb](?=[\d\s'\"-])"
    r"|(?:head|tail)\s+(?:[^|]*\s)?-[cn](?=[\d\s'\"+])"
    r"|(?:head|tail)\s+-\d"
    r"|(?:head|tail)\s*$"
    r"|fold\s+(?:[^|]*\s)?-w(?=[\d\s'\"]))")

# Ignore quoted redirects: a pattern containing 2>/dev/null does not discard stderr.
STDERR_DISCARDED = re.compile(r"2>\s*/dev/null|2>&-|2>\s*&\s*-")

QUOTED_SPAN = re.compile(r"'[^']*'|\"(?:[^\"\\]|\\.)*\"")

# grep exit 1 means no match, not failure.
ERROR_EXIT_STATUSES = frozenset({2, 126, 127, 255})

EXIT_STATUS_PROGRAM_NOT_FOUND = 127

# Missing-path errors do not mean the search program is missing.
PROGRAM_NOT_FOUND = re.compile(
    r"(?:^|[\s:])(?P<named_before>[^\s:]+):\s*command not found\s*$"
    r"|command not found:\s*(?P<named_after>\S+)",
    re.IGNORECASE | re.MULTILINE)

# Nonzero transcript results merge stderr into stdout; diagnostic-only output is still empty.
# Anchor diagnostics at the start so matched text quoting errors remains a result.
DIAGNOSTIC_LINE = re.compile(
    r"^(?:\(eval\)(?::\w+)?:\d+"
    r"|(?:[^\s:]*/)?(?:zsh|bash|sh|dash|ksh)(?::\d+)?"
    r"|[^\s:]+: line \d+"
    r"|(?:[^\s:]*/)?[^\s:/.\d][^\s:/.]*):\s[^\n]*?"
    r"(?:command not found|No such file or directory|Permission denied"
    r"|Is a directory|cannot open|unrecognized option|invalid option"
    r"|unknown option|Connection refused|Could not resolve hostname"
    r"|Operation timed out)"
    r"|^(?:fatal|usage): ", re.IGNORECASE)


def split_diagnostics(text):
    """Return (results, diagnostics)."""
    results = []
    diagnostics = []
    for line in (text or "").splitlines():
        (diagnostics if DIAGNOSTIC_LINE.match(line) else results).append(line)
    return "\n".join(results), "\n".join(diagnostics)

COUNT_LINE = re.compile(r"^(?P<path>.*):(?P<count>\d+)$")

# Harness stderr notices are not errors from the search.
HARNESS_NOTE_ON_STDERR = re.compile(r"^\s*Shell cwd was reset to \S+\s*$")

# A swallowed status alone cannot disprove a no-match when captured stderr is empty.
CORROBORATING_ONLY = "search-exit-status-discarded-by-a-later-stage"

REGEX_ELEMENT = re.compile(r"\[[^\]]+\]|\\\+|\\\*|\\\{|\.\*|\.\+|\\d|\\w|\\s|\+|\*")

SHELL_PUNCTUATION_THAT_REFUSES_A_CONTROL = re.compile(r"[|;&<>`]|\$\(")


class Verdict:
    """The decision about one command and its result."""

    def __init__(self, applicable, empty_kind=None, signals=None,
                 instructions=None, control=None, reason=None,
                 corroboration=None):
        self.applicable = applicable
        self.empty_kind = empty_kind
        self.signals = signals or []
        self.instructions = instructions or []
        self.control = control
        self.reason = reason
        self.corroboration = corroboration or []

    @property
    def fires(self):
        return bool(self.signals)

    def as_dict(self):
        return {
            "applicable": self.applicable,
            "empty_kind": self.empty_kind,
            "signals": list(self.signals),
            "instructions": list(self.instructions),
            "control": self.control,
            "reason": self.reason,
            "corroboration": list(self.corroboration),
        }



def split_on_top_level(text, separators):
    """Split on separators outside quotes."""
    # Heredocs and command substitutions are not parsed; these are not bare searches.
    parts = []
    current = []
    quote = None
    index = 0
    while index < len(text):
        character = text[index]
        if quote:
            current.append(character)
            if character == "\\" and quote == '"' and index + 1 < len(text):
                index += 1
                current.append(text[index])
            elif character == quote:
                quote = None
            index += 1
            continue
        if character in "'\"":
            quote = character
            current.append(character)
            index += 1
            continue
        matched = None
        for separator in separators:
            if text.startswith(separator, index):
                matched = separator
                break
        if matched:
            parts.append("".join(current))
            current = []
            index += len(matched)
            continue
        current.append(character)
        index += 1
    parts.append("".join(current))
    return parts


REMOTE_COMMAND = re.compile(r"""(?:^|\s)(?:'([^']*)'|"((?:[^"\\]|\\.)*)")""")


def remote_command_of(stage):
    """Return the remote command in an ssh stage."""
    if stage_program(stage) != "ssh":
        return None
    quoted = [group for match in REMOTE_COMMAND.finditer(stage)
              for group in match.groups() if group]
    if not quoted:
        return None
    return max(quoted, key=len)


def pipelines_of(command, _depth=0):
    """Return local and remote Pipeline records in command order."""
    segments = split_on_top_level(command, ["&&", "||", ";", "\n"])
    stage_lists = []
    for segment in segments:
        stages = [stage.strip() for stage in split_on_top_level(segment, ["|"])
                  if stage.strip()]
        if stages:
            stage_lists.append(stages)
    pipelines = []
    for position, stages in enumerate(stage_lists):
        last = position == len(stage_lists) - 1
        pipelines.append({"stages": stages, "last": last, "carrier": None,
                          "carrier_stages": None, "carrier_index": None,
                          "carrier_last": None})
        if _depth:
            continue
        for index, stage in enumerate(stages):
            remote = remote_command_of(stage)
            if not remote:
                continue
            for inner in pipelines_of(remote, _depth=1):
                pipelines.append({"stages": inner["stages"],
                                  "last": inner["last"], "carrier": stage,
                                  "carrier_stages": stages,
                                  "carrier_index": index,
                                  "carrier_last": last})
    return pipelines


def stage_program(stage):
    """Return the program, skipping env assignments and sudo."""
    tokens = stage.split()
    for token in tokens:
        if "=" in token and not token.startswith("-") and "/" not in token.split("=")[0]:
            continue
        if token in ("sudo", "command", "env", "nohup", "exec", "time", "then",
                     "do", "!", "{", "("):
            continue
        return token.lstrip("(").rstrip(")")
    return ""


def search_stages_of(command, pipelines=None):
    """Yield (pipeline index, stage index, text, program) for each search."""
    if pipelines is None:
        pipelines = pipelines_of(command)
    found = []
    for pipeline_index, pipeline in enumerate(pipelines):
        for stage_index, stage in enumerate(pipeline["stages"]):
            program = stage_program(stage)
            base = os.path.basename(program)
            if base in SEARCH_PROGRAMS:
                found.append((pipeline_index, stage_index, stage, base))
            elif base == "git" and re.search(
                    # Attached patterns such as -Sneedle have no word boundary after the flag.
                    r"\bgit\s+(?:-[^\s]+\s+)*(?:grep\b|log\b[^|]*\s(?:--grep|-S|-G))",
                    stage):
                found.append((pipeline_index, stage_index, stage, "git"))
    return found


def outside_quotes(text):
    """Remove quoted spans so patterns are not mistaken for shell syntax."""
    return QUOTED_SPAN.sub("", text)


def exit_status_is_the_searchs(command, pipelines, search):
    # A command reports its last pipeline's status; without pipefail, a pipeline reports its last stage's.
    pipeline_index, stage_index, _stage, _program = search
    pipeline = pipelines[pipeline_index]
    pipefail = "pipefail" in command
    if not pipeline["last"]:
        return False
    if stage_index != len(pipeline["stages"]) - 1 and not pipefail:
        return False
    if pipeline["carrier"] is None:
        return True
    return pipeline["carrier_last"] and (
        pipeline["carrier_index"] == len(pipeline["carrier_stages"]) - 1
        or pipefail)


def programs_feeding_a_search(pipelines, searches):
    """Return program names from search pipelines, including their ssh carriers."""
    programs = set()
    for pipeline_index, _, _, _ in searches:
        pipeline = pipelines[pipeline_index]
        stages = list(pipeline["stages"]) + list(pipeline["carrier_stages"] or [])
        programs.update(os.path.basename(stage_program(stage)) for stage in stages)
    programs.discard("")
    return programs


def programs_reported_not_found(output):
    return {os.path.basename(match.group("named_before")
                             or match.group("named_after"))
            for match in PROGRAM_NOT_FOUND.finditer(output or "")}



def empty_shape_of(stdout):
    """Return the empty-result shape, or None for a nonempty result."""
    text = (stdout or "").strip()
    if not text:
        return "no-output"
    if text == "0":
        return "zero-count"
    lines = [line for line in text.splitlines() if line.strip()]
    matches = [COUNT_LINE.match(line) for line in lines]
    if matches and all(matches) and any(int(m.group("count")) == 0 for m in matches):
        return "zero-count-lines"
    return None


def zero_counted_inputs(stdout):
    paths = []
    for line in (stdout or "").splitlines():
        match = COUNT_LINE.match(line.strip())
        if match and int(match.group("count")) == 0:
            paths.append(match.group("path"))
    return paths



def weaken_pattern(pattern):
    """Yield weaker patterns, strongest first, with their names."""
    weakenings = []
    stripped = pattern
    if "/" in stripped and not stripped.endswith("/"):
        # Runtime-composed references may omit the directory.
        last_segment = stripped.rsplit("/", 1)[1]
        if last_segment and last_segment != stripped:
            weakenings.append(("last path segment", last_segment))
    unanchored = stripped
    if unanchored.startswith("^"):
        unanchored = unanchored[1:]
    if unanchored.endswith("$") and not unanchored.endswith("\\$"):
        unanchored = unanchored[:-1]
    if unanchored != stripped and unanchored:
        weakenings.append(("unanchored", unanchored))
    element = REGEX_ELEMENT.search(unanchored)
    if element and element.start() > 0:
        tail = unanchored[element.start():]
        if tail and tail != unanchored:
            weakenings.append(("literal head dropped", tail))
    return weakenings


def search_pattern_and_rest(stage):
    """Return (pattern, tokens) for a parseable search, otherwise (None, None)."""
    try:
        tokens = shlex.split(stage)
    except ValueError:
        return None, None
    if not tokens:
        return None, None
    start = 1
    if os.path.basename(tokens[0]) == "git":
        if len(tokens) < 2 or tokens[1] != "grep":
            return None, None
        start = 2
    elif os.path.basename(tokens[0]) not in SEARCH_PROGRAMS:
        return None, None
    index = start
    while index < len(tokens):
        token = tokens[index]
        if token == "--":
            index += 1
            break
        if token in ("-e", "--regexp", "--include", "--exclude", "-f", "--file",
                     "--glob", "-g", "-m", "--max-count", "-A", "-B", "-C",
                     "--type", "-t"):
            if token in ("-e", "--regexp") and index + 1 < len(tokens):
                return tokens[index + 1], tokens
            index += 2
            continue
        if token.startswith("-") and token != "-":
            index += 1
            continue
        return token, tokens
    return None, None


def control_refusal(stage):
    """Return the reason a control run is refused, or None."""
    if SHELL_PUNCTUATION_THAT_REFUSES_A_CONTROL.search(stage):
        return "the stage carries shell punctuation"
    try:
        tokens = shlex.split(stage)
    except ValueError:
        return "the stage does not parse"
    if not tokens:
        return "the stage is empty"
    program = os.path.basename(tokens[0])
    if program == "git":
        if len(tokens) < 2 or tokens[1] != "grep":
            return "git runs no search here but grep"
    elif program not in CONTROL_PROGRAMS:
        return f"{program} is never re-run"
    if any(OPTION_THAT_RUNS_ANOTHER_PROGRAM.match(token) for token in tokens[1:]):
        return "an option runs another program"
    return None


def control_candidates(pipelines, searches):
    """Return [(stage, pattern)] for a repeatable search, otherwise []."""
    # Piped input and preceding commands cannot be reproduced by searching the corpus alone.
    if len(pipelines) != 1 or len(pipelines[0]["stages"]) != 1:
        return []
    if not searches or searches[0][:2] != (0, 0):
        return []
    stage = pipelines[0]["stages"][0]
    if control_refusal(stage):
        return []
    pattern, _tokens = search_pattern_and_rest(stage)
    if not pattern:
        return []
    return [(stage, pattern)]


def shell_words_marking_globs(stage):
    """Return (word, glob pattern or None) pairs, or None if parsing fails."""
    # shlex.split loses the quoting that determines whether the shell expands a glob.
    words = []
    word, pattern, globbed, in_word = [], [], False, False
    quote = None
    index = 0
    while index < len(stage):
        character = stage[index]
        if quote == "'":
            if character == "'":
                quote = None
            else:
                word.append(character)
                pattern.append(glob.escape(character))
        elif quote == '"':
            if character == '"':
                quote = None
            elif character == "\\" and stage[index + 1:index + 2] in \
                    ('"', "\\", "$", "`"):
                index += 1
                word.append(stage[index])
                pattern.append(glob.escape(stage[index]))
            else:
                word.append(character)
                pattern.append(glob.escape(character))
        elif character in "'\"":
            quote = character
            in_word = True
        elif character == "\\" and index + 1 < len(stage):
            index += 1
            word.append(stage[index])
            pattern.append(glob.escape(stage[index]))
            in_word = True
        elif character.isspace():
            if in_word:
                words.append(("".join(word),
                              "".join(pattern) if globbed else None))
            word, pattern, globbed, in_word = [], [], False, False
        else:
            word.append(character)
            pattern.append(character)
            in_word = True
            globbed = globbed or character in "*?["
        index += 1
    if quote:
        return None
    if in_word:
        words.append(("".join(word), "".join(pattern) if globbed else None))
    return words


def expand_like_the_shell(glob_pattern, corpus_root):
    """Return matching paths relative to corpus_root, or []."""
    if os.path.isabs(glob_pattern):
        return sorted(glob.glob(glob_pattern))
    expanded = sorted(glob.glob(
        os.path.join(glob.escape(corpus_root), glob_pattern)))
    return [os.path.relpath(path, corpus_root) for path in expanded]


# Claude Code wraps bare grep with ugrep, skipping VCS directories, binaries, and ignored files.
# Explicit grep paths, egrep, and fgrep still run the system programs.
AGENTS_GREP_SKIPPED_DIRECTORIES = (".git", ".svn", ".hg", ".bzr", ".jj", ".sl")


def as_the_agents_shell_runs_it(control_tokens):
    """Return control argv with the skips used by the agent's grep."""
    if control_tokens[0] != "grep":
        return control_tokens
    return (["grep", "-I"]
            + [f"--exclude-dir={name}" for name in AGENTS_GREP_SKIPPED_DIRECTORIES]
            + control_tokens[1:])


def file_an_output_line_names(line, corpus_root):
    """Return the file named by an output line, or None."""
    # Try the longest path first: hyphens in filenames can also look like context separators.
    if os.path.isfile(os.path.join(corpus_root, line)):
        return line
    for separator in reversed(list(re.finditer(r"[:-]", line))):
        head = line[:separator.start()]
        if head and os.path.isfile(os.path.join(corpus_root, head)):
            return head
    return None


def path_is_at_or_below(path, directory):
    return path == directory or path.startswith(directory.rstrip(os.sep) + os.sep)


def gitignore_rules_ignoring(relative_paths, search_root):
    """Return paths ignored by .gitignore files at or below search_root."""
    # ugrep reads .gitignore rules regardless of tracked status or repository boundaries.
    # Use an empty index and exclude global rules to match that behavior.
    environment = {key: value for key, value in os.environ.items()
                   if not key.startswith("GIT_")}
    environment.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
    try:
        with tempfile.TemporaryDirectory(prefix=f"{PROGRAM}-") as empty:
            subprocess.run(["git", "init", "-q", "--bare", empty],
                           env=environment, capture_output=True, check=True,
                           timeout=60)
            finished = subprocess.run(
                ["git", f"--git-dir={empty}", f"--work-tree={search_root}",
                 "check-ignore", "--no-index", "--verbose", "--stdin", "-z"],
                cwd=search_root, env=environment,
                input="\0".join(relative_paths) + "\0",
                capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return set()
    fields = finished.stdout.split("\0")
    ignored = set()
    for index in range(0, len(fields) - 3, 4):
        source, _line, pattern, path = fields[index:index + 4]
        if pattern.startswith("!") or os.path.isabs(source) or \
                os.path.basename(source) != ".gitignore":
            continue
        ignored.add(path)
    return ignored


GREP_SHORT_OPTIONS_TAKING_AN_ARGUMENT = frozenset("efmABCdD")
GREP_LONG_OPTIONS_TAKING_AN_ARGUMENT = frozenset({
    "--regexp", "--file", "--max-count", "--after-context", "--before-context",
    "--context", "--directories", "--devices", "--include", "--exclude",
    "--exclude-dir", "--exclude-from", "--label", "--binary-files"})


def grep_flags_and_file_operands(control_tokens):
    """Return (flags, file operands) from grep argv."""
    # Option arguments and the search pattern are not file operands, even when they name directories.
    flags = []
    operands = []
    pattern_given_by_an_option = False
    index = 1
    while index < len(control_tokens):
        token = control_tokens[index]
        index += 1
        if token == "--":
            operands.extend(control_tokens[index:])
            break
        if token.startswith("--"):
            name = token.split("=", 1)[0]
            flags.append(token if "=" in token else name)
            if name in ("--regexp", "--file"):
                pattern_given_by_an_option = True
            if name in GREP_LONG_OPTIONS_TAKING_AN_ARGUMENT and "=" not in token:
                if name == "--directories" and index < len(control_tokens):
                    flags.append(f"--directories={control_tokens[index]}")
                index += 1
            continue
        if token.startswith("-") and token != "-":
            for position, letter in enumerate(token[1:], start=1):
                flags.append(letter)
                if letter in "ef":
                    pattern_given_by_an_option = True
                if letter in GREP_SHORT_OPTIONS_TAKING_AN_ARGUMENT:
                    argument = token[position + 1:]
                    if not argument and index < len(control_tokens):
                        argument = control_tokens[index]
                        index += 1
                    if letter == "d":
                        flags.append(f"--directories={argument}")
                    break
            continue
        operands.append(token)
    if not pattern_given_by_an_option and operands:
        operands = operands[1:]
    return flags, operands


def lines_the_agents_grep_could_read(lines, corpus_root, control_tokens):
    """Return output lines from files the agent's grep could read."""
    # ugrep applies .gitignore rules below each directory operand, even to tracked files.
    # Without filename output, matched text that spells a path must not be filtered as that file.
    flags, operands = grep_flags_and_file_operands(control_tokens)
    root = os.path.abspath(corpus_root)
    recursive = any(flag in ("r", "R", "--recursive", "--dereference-recursive",
                             "--directories=recurse") for flag in flags)
    directories = [operand for operand in operands
                   if os.path.isdir(os.path.join(root, operand))]
    if not recursive or (operands and not directories):
        return lines
    names_files = True
    for flag in flags:
        if flag in ("h", "--no-filename"):
            names_files = False
        elif flag in ("H", "--with-filename"):
            names_files = True
    if any(flag in ("l", "L", "--files-with-matches", "--files-without-match")
           for flag in flags):
        names_files = True
    if not names_files:
        return lines
    search_roots = sorted(
        {os.path.normpath(os.path.join(root, directory))
         for directory in directories} or {root}, key=len, reverse=True)
    named = {line: file_an_output_line_names(line, corpus_root)
             for line in lines}
    explicit_files = set(operands) - set(directories)
    by_search_root = {}
    for path in {path for path in named.values()
                 if path and path not in explicit_files}:
        found_at = os.path.normpath(os.path.join(root, path))
        for search_root in search_roots:
            if path_is_at_or_below(found_at, search_root):
                # Overlapping search roots can print the same file under multiple spellings.
                by_search_root.setdefault(search_root, {}).setdefault(
                    os.path.relpath(found_at, search_root), set()).add(path)
                break
    skipped = set()
    for search_root, paths in by_search_root.items():
        for relative in gitignore_rules_ignoring(sorted(paths), search_root):
            skipped.update(paths.get(relative, ()))
    return [line for line in lines if named[line] not in skipped]


def run_control(stage, pattern, corpus_root, zero_inputs):
    """Run weakened searches and report the first that matches."""
    if control_refusal(stage):
        return None
    tokens = shlex.split(stage)
    if pattern not in tokens:
        return None
    words = shell_words_marking_globs(stage)
    if words is None or [word for word, _ in words] != tokens:
        return None
    for name, weaker in weaken_pattern(pattern):
        control_tokens = []
        for token, glob_pattern in words:
            if token == pattern:
                control_tokens.append(weaker)
            elif glob_pattern is not None:
                control_tokens.extend(
                    expand_like_the_shell(glob_pattern, corpus_root) or [token])
            else:
                control_tokens.append(token)
        control_tokens = as_the_agents_shell_runs_it(control_tokens)
        try:
            finished = subprocess.run(
                control_tokens, cwd=corpus_root, capture_output=True, text=True,
                timeout=60)
        except (OSError, subprocess.SubprocessError):
            continue
        control_shape = empty_shape_of(finished.stdout)
        if control_shape is None:
            matched = [line for line in finished.stdout.strip().splitlines()
                       if line.strip() and line.strip() != "--"]
            if control_tokens[0] == "grep":
                matched = lines_the_agents_grep_could_read(
                    matched, corpus_root, control_tokens)
            if not matched:
                continue
            return {
                "weakening": name,
                "pattern": weaker,
                "command": " ".join(control_tokens),
                "matched": matched[:5],
            }
        if control_shape == "zero-count-lines" and zero_inputs:
            # Compare files, not spellings: ugrep may print a.py where system grep prints ./a.py.
            control_counts = {}
            for line in finished.stdout.splitlines():
                match = COUNT_LINE.match(line.strip())
                if match:
                    control_counts[os.path.normpath(match.group("path"))] = \
                        int(match.group("count"))
            recovered = [path for path in zero_inputs
                         if control_counts.get(os.path.normpath(path), 0) > 0]
            if recovered:
                return {
                    "weakening": name,
                    "pattern": weaker,
                    "command": " ".join(control_tokens),
                    "matched": [f"{path}: counted 0 by the original, matched by "
                                f"the weakened search" for path in recovered[:5]],
                }
    return None



def meaningful_stderr(stderr):
    """Remove harness notices from stderr."""
    lines = [line for line in (stderr or "").splitlines()
             if line.strip() and not HARNESS_NOTE_ON_STDERR.match(line)]
    return "\n".join(lines)


def judge_command_result(command, exit_code=None, stdout="", stderr="",
                         control_corpus_root=None, stderr_was_captured=True):
    """Decide whether an empty result is evidence of absence."""
    pipelines = pipelines_of(command)
    searches = search_stages_of(command, pipelines)
    if not searches:
        return Verdict(False, reason="no search stage in the command")

    streams_were_merged = not stderr_was_captured and bool(exit_code)
    if streams_were_merged:
        results_text, merged_diagnostics = split_diagnostics(stdout)
    else:
        results_text, merged_diagnostics = stdout, ""
    empty_kind = empty_shape_of(results_text)
    if empty_kind is None:
        return Verdict(False, reason="the result is not empty")

    signals = []
    instructions = []
    combined_output = f"{stdout or ''}\n{stderr or ''}"

    for pipeline_index, stage_index, stage, program in searches:
        pipeline = pipelines[pipeline_index]
        stages = pipeline["stages"]
        carrier = pipeline["carrier"]

        if STDERR_DISCARDED.search(outside_quotes(stage)) or (
                carrier and STDERR_DISCARDED.search(outside_quotes(carrier))):
            signals.append("stderr-discarded-by-the-search-stage")
            instructions.append(
                "Re-run without `2>/dev/null` before reporting absence: the "
                "search's stderr was discarded, so an error and a clean "
                "no-match printed the same nothing.")

        for earlier in stages[:stage_index]:
            if TRUNCATING_STAGE.match(earlier):
                signals.append("truncating-stage-upstream-of-the-search")
                instructions.append(
                    f"Search the whole input before reporting absence: "
                    f"`{earlier.strip()}` cut the input down ahead of the "
                    f"search, so the search read a truncation.")
                break

        later_stages = list(stages[stage_index + 1:])
        if carrier is not None and not later_stages:
            # The remote search is last, so ssh carries the status the local pipeline swallows.
            later_stages = list(
                pipeline["carrier_stages"][pipeline["carrier_index"] + 1:])
        swallowed = bool(later_stages)
        if not swallowed:
            tail = command[command.find(stage) + len(stage):]
            if re.match(r"\s*(?:;|&&)\s*(?:echo|true|:)\b", tail) or \
                    re.match(r"\s*\|\|\s*(?:true|:|echo)\b", tail):
                swallowed = True
        if swallowed and "pipefail" not in command and "PIPESTATUS" not in command:
            signals.append("search-exit-status-discarded-by-a-later-stage")
            instructions.append(
                "Read the search's own exit status with `${PIPESTATUS[0]}` or "
                "`set -o pipefail`, then re-run: a later stage replaced it, and "
                "grep's 1 for no match and 2 for an error are now both 0.")

    status_is_the_searchs = any(
        exit_status_is_the_searchs(command, pipelines, search)
        for search in searches)
    if status_is_the_searchs and exit_code in ERROR_EXIT_STATUSES:
        signals.append("exit-status-reports-an-error-not-an-absence")
        instructions.append(
            f"Fix what exit status {exit_code} reports and re-run before "
            f"reporting absence: that status means the search failed, not that "
            f"it found nothing.")
    if (programs_reported_not_found(combined_output)
            & programs_feeding_a_search(pipelines, searches)) or (
            status_is_the_searchs
            and exit_code == EXIT_STATUS_PROGRAM_NOT_FOUND):
        signals.append("search-program-missing-on-this-machine")
        instructions.append(
            "Install the program the output says was not found, then re-run: a "
            "search whose program is missing prints the same nothing as a "
            "search that found nothing.")
    own_stderr = meaningful_stderr(stderr) or merged_diagnostics
    if (exit_code == 0 or exit_code is None) and own_stderr and \
            not (stdout or "").strip():
        signals.append("stderr-written-while-stdout-was-empty")
        instructions.append(
            "Read stderr before reporting absence: this search wrote to stderr "
            "and nothing to stdout, which is what an error looks like.")

    control = None
    if control_corpus_root is not None:
        for stage, pattern in control_candidates(pipelines, searches):
            control = run_control(stage, pattern, control_corpus_root,
                                  zero_counted_inputs(stdout))
            if control:
                signals.append("weakened-pattern-control-run-found-matches")
                instructions.append(
                    f"Search for `{control['pattern']}` and read what it "
                    f"returns before reporting absence: the same search "
                    f"weakened to that pattern matched where this one did not.")
                break

    ordered = []
    for signal in signals:
        if signal not in ordered:
            ordered.append(signal)
    seen_instructions = []
    for instruction in instructions:
        if instruction not in seen_instructions:
            seen_instructions.append(instruction)

    stderr_observable = (stderr_was_captured or "2>&1" in command
                         or streams_were_merged)
    if ordered == [CORROBORATING_ONLY] and stderr_observable and not own_stderr:
        return Verdict(True, empty_kind=empty_kind, signals=[],
                       corroboration=ordered,
                       reason="the search's exit status was swallowed, but its "
                              "stderr was empty, so it did not error")
    return Verdict(True, empty_kind=empty_kind, signals=ordered,
                   instructions=seen_instructions, control=control)



EXIT_CODE_IN_RESULT = re.compile(r"^Error: Exit code (\d+)\n?")
NOT_AN_EXECUTION = (
    "Error: Permission", "Error: Blocked:", "User rejected tool use",
    "InputValidationError:", "[Request interrupted", "Error: This session is",
    "Error: claude-",
)


def bash_pairs_in_transcript(path):
    """Yield (command, exit_code, stdout, stderr) for recorded Bash runs."""
    # toolUseResult is a dict with separate streams on success, but a string with merged streams on failure.
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
                    commands[block.get("id")] = (block.get("input") or {}).get(
                        "command", "")
                elif block.get("type") == "tool_result" and \
                        block.get("tool_use_id") in commands:
                    command = commands.pop(block["tool_use_id"])
                    result = record.get("toolUseResult")
                    if isinstance(result, dict):
                        if result.get("backgroundTaskId") or \
                                result.get("interrupted") or \
                                result.get("timedOutAfterMs"):
                            continue
                        yield (command, 0, result.get("stdout") or "",
                               result.get("stderr") or "")
                    elif isinstance(result, str):
                        if result.startswith(NOT_AN_EXECUTION):
                            continue
                        match = EXIT_CODE_IN_RESULT.match(result)
                        if not match:
                            continue
                        yield (command, int(match.group(1)),
                               result[match.end():], "")


def transcripts_under(directory):
    # Subagent transcripts live below session directories; stopping at the top level omits their searches.
    root = pathlib.Path(directory)
    if not root.is_dir():
        return []
    return sorted(root.rglob("*.jsonl"))


def bash_pairs_under(directories):
    """Yield (transcript, command, exit_code, stdout, stderr) for each recorded run."""
    for directory in directories:
        for transcript in transcripts_under(directory):
            for pair in bash_pairs_in_transcript(transcript):
                yield (transcript,) + pair


def measure_transcripts(directories, limit=None, top=10, out=sys.stdout):
    """Print the check's funnel and signal tally over recorded runs."""
    total = 0
    from_subagents = 0
    search_shaped = 0
    empty = 0
    control_derivable = 0
    fired = 0
    by_signal = {}
    by_signal_alone = {}
    by_command = {}
    by_empty_kind = {}
    examples = {}
    pairs = bash_pairs_under(directories)
    if limit is not None:
        pairs = itertools.islice(pairs, limit)
    for transcript, command, exit_code, stdout, stderr in pairs:
        total += 1
        if "subagents" in transcript.parts:
            from_subagents += 1
        if not search_stages_of(command):
            continue
        search_shaped += 1
        verdict = judge_command_result(
            command, exit_code=exit_code, stdout=stdout, stderr=stderr,
            control_corpus_root=None, stderr_was_captured=(exit_code == 0))
        if not verdict.applicable:
            continue
        empty += 1
        pipelines = pipelines_of(command)
        if control_candidates(pipelines, search_stages_of(command, pipelines)):
            control_derivable += 1
        if not verdict.fires:
            continue
        fired += 1
        by_empty_kind[verdict.empty_kind] = by_empty_kind.get(
            verdict.empty_kind, 0) + 1
        for signal in verdict.signals:
            by_signal[signal] = by_signal.get(signal, 0) + 1
            examples.setdefault(signal, []).append(command[:200])
        if len(verdict.signals) == 1:
            only = verdict.signals[0]
            by_signal_alone[only] = by_signal_alone.get(only, 0) + 1
        head = " ".join(command.split())[:80]
        by_command[head] = by_command.get(head, 0) + 1

    print(f"{PROGRAM}: measurement over recorded Bash pairs", file=out)
    print(f"  transcript directories : {len(directories)}", file=out)
    print(f"  pairs replayed         : {total}", file=out)
    print(f"    from subagents       : {from_subagents}", file=out)
    print(f"  with a search stage    : {search_shaped}", file=out)
    print(f"  and an empty result    : {empty}", file=out)
    print(f"    bare enough to control: {control_derivable}", file=out)
    print(f"  the check fired on     : {fired}", file=out)
    if empty:
        print(f"  firing rate over empty search results: "
              f"{100.0 * fired / empty:.1f}%", file=out)
    print("  empty shapes that fired:", file=out)
    for kind, count in sorted(by_empty_kind.items(), key=lambda kv: -kv[1]):
        print(f"    {count:6d}  {kind}", file=out)
    print("  signals (a pair can raise several):", file=out)
    for signal, count in sorted(by_signal.items(), key=lambda kv: -kv[1]):
        alone = by_signal_alone.get(signal, 0)
        print(f"    {count:6d}  ({alone} alone)  {signal}", file=out)
    print(f"  the {top} commands that fire most often:", file=out)
    for head, count in sorted(by_command.items(), key=lambda kv: -kv[1])[:top]:
        print(f"    {count:6d}  {head}", file=out)
    return {
        "pairs": total, "from_subagents": from_subagents,
        "search_shaped": search_shaped, "empty": empty,
        "control_derivable": control_derivable,
        "fired": fired, "by_signal": by_signal, "by_signal_alone": by_signal_alone,
        "by_command": by_command, "examples": examples,
        "by_empty_kind": by_empty_kind,
    }



def default_fixtures_directory():
    return pathlib.Path(__file__).resolve().with_name(FIXTURES_DIRECTORY_NAME)


def load_fixtures(directory):
    fixtures = []
    for path in sorted(pathlib.Path(directory).glob("*.json")):
        with open(path, encoding="utf-8") as handle:
            fixture = json.load(handle)
        fixture["fixture_path"] = str(path)
        fixtures.append(fixture)
    return fixtures


def replay_fixtures(directory, run_control=False, checkout_root=None, out=sys.stdout):
    """Judge fixtures and report whether each fires."""
    fixtures = load_fixtures(directory)
    if not fixtures:
        print(f"{PROGRAM}: no fixtures in {directory}", file=out)
        return [], False
    if checkout_root is None:
        checkout_root = pathlib.Path(__file__).resolve().parent.parent
    results = []
    every_one_fired = True
    for fixture in fixtures:
        corpus = None
        if run_control and fixture.get("control_corpus_root"):
            corpus = str(pathlib.Path(checkout_root) /
                         fixture["control_corpus_root"])
        verdict = judge_command_result(
            fixture["command"],
            exit_code=fixture.get("exit_code"),
            stdout=fixture.get("stdout", ""),
            stderr=fixture.get("stderr", ""),
            control_corpus_root=corpus)
        results.append((fixture, verdict))
        fired = verdict.fires
        if fixture.get("must_fire", True) and not fired:
            every_one_fired = False
        print(f"{'FIRED  ' if fired else 'SILENT '} {fixture['case']}", file=out)
        print(f"    command: {' '.join(fixture['command'].split())[:150]}", file=out)
        print(f"    result : exit={fixture.get('exit_code')} "
              f"stdout={_short(fixture.get('stdout', ''))} "
              f"stderr={_short(fixture.get('stderr', ''))}", file=out)
        print(f"    signals: {', '.join(verdict.signals) or '(none)'}", file=out)
        for instruction in verdict.instructions:
            print(f"      > {instruction}", file=out)
        if verdict.control:
            print(f"    control: {verdict.control['command']}", file=out)
            for line in verdict.control["matched"]:
                print(f"      + {line}", file=out)
        print("", file=out)
    print(f"{PROGRAM}: {sum(1 for _, v in results if v.fires)} of {len(results)} "
          f"fixtures fired", file=out)
    return results, every_one_fired


def _short(text, width=60):
    one_line = " ".join((text or "").split())
    if len(one_line) <= width:
        return repr(one_line)
    return repr(one_line[:width] + "...")



def main(argv=None):
    parser = argparse.ArgumentParser(
        prog=PROGRAM,
        description="Decide whether a search's empty result is evidence of absence.")
    parser.add_argument("--command")
    parser.add_argument("--exit-code", type=int)
    parser.add_argument("--stdout-file")
    parser.add_argument("--stderr-file")
    parser.add_argument("--stderr-not-captured", action="store_true",
                        help="stderr was not kept as its own stream, so an "
                             "empty one is no proof the search did not error")
    parser.add_argument("--run-control", action="store_true")
    parser.add_argument("--control-corpus-root")
    parser.add_argument("--replay-fixtures", nargs="?", const="",
                        metavar="DIR")
    parser.add_argument("--transcripts", action="append", default=[],
                        metavar="DIR")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument("--json", action="store_true")
    arguments = parser.parse_args(argv)

    modes = [bool(arguments.command), arguments.replay_fixtures is not None,
             bool(arguments.transcripts)]
    if sum(modes) != 1:
        print(f"{PROGRAM}: give exactly one of --command, --replay-fixtures, "
              f"--transcripts", file=sys.stderr)
        return EXIT_BAD_INVOCATION

    if arguments.transcripts:
        measure_transcripts(arguments.transcripts, limit=arguments.limit,
                            top=arguments.top)
        return EXIT_QUIET

    if arguments.replay_fixtures is not None:
        directory = arguments.replay_fixtures or default_fixtures_directory()
        if not pathlib.Path(directory).is_dir():
            print(f"{PROGRAM}: {directory} is not a directory", file=sys.stderr)
            return EXIT_BAD_INVOCATION
        _results, every_one_fired = replay_fixtures(
            directory, run_control=arguments.run_control,
            checkout_root=arguments.control_corpus_root)
        return EXIT_QUIET if every_one_fired else EXIT_FIRED

    stdout = _read_or_empty(arguments.stdout_file)
    stderr = _read_or_empty(arguments.stderr_file)
    corpus = None
    if arguments.run_control:
        corpus = arguments.control_corpus_root or os.getcwd()
    verdict = judge_command_result(
        arguments.command, exit_code=arguments.exit_code, stdout=stdout,
        stderr=stderr, control_corpus_root=corpus,
        stderr_was_captured=not arguments.stderr_not_captured)
    if arguments.json:
        print(json.dumps(verdict.as_dict(), indent=2))
    elif verdict.fires:
        print(f"{PROGRAM}: this empty result is not evidence of absence.")
        for instruction in verdict.instructions:
            print(instruction)
    else:
        print(f"{PROGRAM}: nothing to report "
              f"({verdict.reason or 'no signal fired'}).")
    return EXIT_FIRED if verdict.fires else EXIT_QUIET


def _read_or_empty(path):
    if not path:
        return ""
    with open(path, encoding="utf-8", errors="replace") as handle:
        return handle.read()


if __name__ == "__main__":
    sys.exit(main())
