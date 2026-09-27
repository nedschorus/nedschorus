#!/usr/bin/env python3
"""empty-search-runs-locator-hook — an empty search quietly runs the locator.

When an agent's search for a file comes back empty, this hook runs
scripts/locate-file-copies-across-machines.py on the name the agent was
after, in the background, and records what the locator found. STAGE 1 IS
SILENT: the agent is told nothing, and the only product is the record.

WHY. Between 2026-08-23 and 2026-09-23 agents told the user fourteen times
that a file did not exist when it did. The research, at

    nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/merge-lane/lost-file-research-report-2026-09-23.md

found that none of the fourteen went through Glob or Grep: every search
that ran was a Bash `find`, `ls` or `git log`, often chained with `;` and
`echo` headers so that it exited 0 whatever it found. So this hook reads
what a search printed, not how it exited. The user proposed running the
locator automatically after an empty search (walk
"merge-lane-mac-helper-open-items-and-questions-2026-09-23", item 4.2), and
ruled "Y" on 2026-09-24 at 21:16Z to building it in two stages: this silent
stage for a week, then, on his word after the week's numbers, a second
stage in which the agent sees the locator's answer beside its empty result.
The estimate put to him, from the research's episode table and its counts of
empty results on the Mac's main sessions: about 470 fires a month, and 4 of
the 14 episodes catchable. The five in which no search ran before the claim
cannot be caught by any hook on a search.

THE THREE TRIGGERS, and nothing else fires:
  1. A Read of a file that is not there: the PostToolUseFailure event,
     tool Read, whose error opens "File does not exist".
  2. A Bash command whose output has a line saying "No such file or
     directory" for a path, in the forms ls, cat, head, find, bash, zsh and
     Python print on macOS and on Ubuntu. A line from `find` names a search
     root, not the file sought, so it is not a query: the find's own
     `-name` is, when it has one.
  3. A Bash `find ... -name X` (or -iname, -path, -ipath) or
     `git log ... -- X` whose output is empty, once the lines the command's
     own `echo` segments printed, and find's "Permission denied" and
     "Operation not permitted" lines, are taken away.
Measured 2026-09-24 with Claude Code 2.1.280, by a probe hook in a scratch
session: a Read of a missing file arrives as PostToolUseFailure with
`tool_input.file_path` and `error` "File does not exist. ..."; a Bash
command that exits non-zero arrives as PostToolUseFailure with its output
in `error` after an "Exit code N" line; a Bash command that exits 0 arrives
as PostToolUse with `tool_response.stdout` holding stdout and stderr
together; an empty Glob arrives as PostToolUse with no failure. The test
beside this file replays those payloads. Glob and Grep are not triggers:
the research found them in none of the fourteen, and the user ruled them
out on 2026-08-25.

WHAT IT DOES NOT CATCH, so a quiet week is not read as more than it is:
  - A claim made with no search before it, the largest class.
  - `git show <commit>:<path>` failing with "does not exist in": a real
    lost-file signal (episode E01), but not among the three triggers the
    user approved.
  - A search whose output is not empty because another search in the same
    command found something, or because it printed anything besides echo
    lines: the hook cannot tell which segment printed what.
  - A pattern too generic to be a name: fewer than three letters or digits
    once glob characters are taken off (`*.md`, `x`).
  - A search the agent ran through the locator or the backup search
    themselves, or a command that searches for the words "No such file".

WHERE THE RECORDS GO. Logs live in the log-store, never in the repository
(CLAUDE.md). This is a measurement the merge-lane seat commissioned, so its
records go beside the research, under the log-store's `seats/merge-lane/`
kind (docs/nedschorus-wiki/nedschorus-file-naming-and-location-standards.md:
`seats/` holds a seat's measurement output):
  - on ned-box, straight into
    /home/nedlern/nedschorus-logs/seats/merge-lane/empty-search-runs-locator-hook-fires-ned-box.jsonl;
  - on the Mac, into ~/.claude/empty-search-runs-locator-hook-fires-mac.jsonl,
    beside the Mac's other background logs there (transcript-mirror.log),
    because a hook must not wait on ssh. At the week's end it is shipped with
    `python3 scripts/seat-shared-file-ship.py --seat merge-lane <that file>`.
One JSON line per fire, written when the hook runs, and one per locator
answer, written by the background run when the locator finishes, joined by
`fire_id`. `--summarize FILE...` prints the week's counts from them.

A REPEAT is the same query from the same session within ten minutes: an
agent retrying an `ls`, or a Read after it. It is recorded, marked
`repeat_of`, and the locator is not run again.

Wired in .claude/settings.json as a PostToolUse hook on Bash and a
PostToolUseFailure hook on Bash and Read.
Input: the PostToolUse or PostToolUseFailure payload on stdin.
Output: nothing, ever, in stage 1.
Exit codes: always 0. The locator runs detached from the hook, so the hook
returns in a few tens of milliseconds and a tool call is never delayed or
failed by it.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import shlex
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path

PROGRAM = "empty-search-runs-locator-hook"
RECORD_VERSION = 1

LOCATOR_PATH = Path(__file__).resolve().with_name(
    "locate-file-copies-across-machines.py")
LOCATOR_ENVIRONMENT_VARIABLE = "EMPTY_SEARCH_RUNS_LOCATOR_HOOK_LOCATOR"
RECORD_FILE_ENVIRONMENT_VARIABLE = "EMPTY_SEARCH_RUNS_LOCATOR_HOOK_RECORD_FILE"

NED_BOX_HOSTNAME = "ned-box"
NED_BOX_RECORD_FILE = Path(
    "/home/nedlern/nedschorus-logs/seats/merge-lane/"
    "empty-search-runs-locator-hook-fires-ned-box.jsonl")
MAC_RECORD_FILE = (Path.home() / ".claude" /
                   "empty-search-runs-locator-hook-fires-mac.jsonl")

# The programs that already are the search: their output is their own
# report, and an agent running them is doing what the locator would.
SEARCH_PROGRAM_NAMES = ("locate-file-copies-across-machines",
                        "find-deleted-path-across-backups",
                        "empty-search-runs-locator-hook")

READ_MISSING_FILE_ERROR_PREFIX = "File does not exist"
NO_SUCH_FILE = "no such file or directory"
# A command holding these words is searching for them, in a log or a
# transcript, and what it prints is what it found, not a missing file.
NO_SUCH_FILE_WORDS = "no such file"

MAX_OUTPUT_CHARACTERS_SCANNED = 256 * 1024
MAX_QUERIES_PER_FIRE = 3
MIN_NAME_ALPHANUMERICS = 3
REPEAT_WINDOW_SECONDS = 600
REPEAT_SCAN_BYTES = 128 * 1024
LOCATOR_TIMEOUT_SECONDS = 180
MAX_LINES_KEPT_PER_LIST = 3
MAX_LINE_CHARACTERS_KEPT = 200
MAX_TEXT_KEPT = 500

PROGRAM_PREFIX = r"^(?P<program>[\w.+-]+): (?:line \d+: )?"
QUOTE_OPEN = "'‘\"`"
QUOTE_CLOSE = "'’\"`"
# The forms a missing path is reported in, most specific first. Each names
# the path in a group called `path`; `program` is the program that said it.
NO_SUCH_FILE_LINE_PATTERNS = [
    # GNU ls: ls: cannot access 'x': No such file or directory
    re.compile(PROGRAM_PREFIX + r"cannot access [" + QUOTE_OPEN +
               r"](?P<path>.+?)[" + QUOTE_CLOSE +
               r"]: No such file or directory$", re.IGNORECASE),
    # GNU head and tail: head: cannot open 'x' for reading: No such ...
    re.compile(PROGRAM_PREFIX + r"cannot open [" + QUOTE_OPEN +
               r"](?P<path>.+?)[" + QUOTE_CLOSE +
               r"] for reading: No such file or directory$", re.IGNORECASE),
    # GNU find and others that quote: find: 'x': No such file or directory
    re.compile(PROGRAM_PREFIX + r"[" + QUOTE_OPEN + r"](?P<path>.+?)[" +
               QUOTE_CLOSE + r"]: No such file or directory$", re.IGNORECASE),
    # zsh: zsh: no such file or directory: x
    re.compile(PROGRAM_PREFIX + r"no such file or directory: (?P<path>.+)$",
               re.IGNORECASE),
    # BSD ls, cat, head, wc, stat; GNU cat; bash: prog: x: No such ...
    re.compile(PROGRAM_PREFIX + r"(?P<path>.+?): No such file or directory$",
               re.IGNORECASE),
    # Python: can't open file 'x': [Errno 2] No such file or directory
    re.compile(r"can't open file (?P<quote>['\"])(?P<path>.+?)(?P=quote): "
               r"\[Errno 2\] No such file or directory"),
    # Python: FileNotFoundError: [Errno 2] No such file or directory: 'x'
    re.compile(r"\[Errno 2\] No such file or directory: "
               r"(?P<quote>['\"])(?P<path>.+?)(?P=quote)"),
]
# A missing directory the shell was told to change into is not a file.
PROGRAMS_NAMING_A_DIRECTORY = {"cd", "pushd"}

FIND_NAME_OPTIONS = {"-name", "-iname", "-path", "-ipath", "-wholename",
                     "-iwholename"}
FIND_NOISE_LINE = re.compile(
    r"^find: .*: (Permission denied|Operation not permitted)$")
GIT_OPTIONS_WITH_A_VALUE = {"-C", "-c", "--git-dir", "--work-tree",
                            "--namespace", "--exec-path"}
GLOB_CHARACTERS = re.compile(r"[*?\[\]{}]")
EXIT_CODE_LINE = re.compile(r"^Exit code \d+\s*$")
# The characters that separate one simple command from the next.
COMMAND_PUNCTUATION = ";&|()\n"


# --- which query, if any, a payload asks for --------------------------------

def is_name_worth_searching(name: str) -> bool:
    base = name.rstrip("/").rsplit("/", 1)[-1]
    return sum(character.isalnum() for character in base) \
        >= MIN_NAME_ALPHANUMERICS


def path_query(raw: str, directory: str):
    """The locator query for a path as a command printed it: absolute, made
    absolute from `directory`, or left to the locator when it starts with
    `~`. None when it is not a usable path."""
    path = raw.strip().strip(QUOTE_OPEN + QUOTE_CLOSE).rstrip("/")
    if (not path or len(path) > 400 or ": " in path or "\n" in path
            or any(quote in path for quote in QUOTE_OPEN + QUOTE_CLOSE)
            or path.startswith("-")):
        return None
    # "could not read file x": a phrase, not a path.
    if " " in path and "/" not in path:
        return None
    if GLOB_CHARACTERS.search(path):
        return name_query(path)
    if not is_name_worth_searching(path):
        return None
    if path.startswith("~") or os.path.isabs(path):
        return path
    return os.path.normpath(os.path.join(directory or "/", path))


def name_query(pattern: str):
    """The locator query for a find -name or a git pathspec with glob
    characters: the last component with its glob characters taken off, a
    bare name. None when too little is left to be a name."""
    base = pattern.strip().strip(QUOTE_OPEN + QUOTE_CLOSE).rstrip("/")
    base = base.rsplit("/", 1)[-1]
    base = GLOB_CHARACTERS.sub("", base)
    if not base or base.startswith("-") or not is_name_worth_searching(base):
        return None
    return base


def split_simple_commands(command: str):
    """The command's simple commands, each a list of words, or None when the
    shell text cannot be split (an unbalanced quote, a here-document)."""
    try:
        # An unquoted newline separates commands as `;` does, so it is
        # punctuation here rather than whitespace; a quoted one stays inside
        # its word.
        lexer = shlex.shlex(command, posix=True,
                            punctuation_chars=COMMAND_PUNCTUATION)
        lexer.whitespace = " \t\r"
        lexer.whitespace_split = True
        lexer.commenters = ""
        tokens = list(lexer)
    except ValueError:
        return None
    commands, current = [], []
    for token in tokens:
        if set(token) <= set(COMMAND_PUNCTUATION):
            if current:
                commands.append(current)
            current = []
        else:
            current.append(token)
    if current:
        commands.append(current)
    return commands


def find_name_arguments(words):
    """The values of a find's -name, -iname, -path and -ipath options."""
    return [words[index + 1] for index, word in enumerate(words[:-1])
            if word in FIND_NAME_OPTIONS]


def git_log_pathspecs(words):
    """The pathspecs after `--` of a `git ... log ...` simple command, with
    the directory git was pointed at by -C, or None when it is not one."""
    index, directory = 1, None
    while index < len(words) and words[index].startswith("-"):
        option = words[index]
        if option == "-C" and index + 1 < len(words):
            directory = words[index + 1]
        if option in GIT_OPTIONS_WITH_A_VALUE and "=" not in option:
            index += 2
        else:
            index += 1
    if index >= len(words) or words[index] != "log":
        return None
    rest = words[index + 1:]
    if "--" not in rest:
        return None
    return directory, [spec for spec in rest[rest.index("--") + 1:]
                       if not spec.startswith(":")]


def program_name(word: str) -> str:
    return word.rsplit("/", 1)[-1]


def echoed_lines(simple_commands):
    """The lines the command's own `echo` segments print, to be taken away
    from its output before the output is judged empty."""
    lines = set()
    for words in simple_commands:
        if not words or program_name(words[0]) != "echo":
            continue
        arguments = words[1:]
        while arguments and re.fullmatch(r"-[neE]+", arguments[0]):
            arguments = arguments[1:]
        for line in " ".join(arguments).split("\n"):
            lines.add(line.strip())
    return lines


def output_is_empty(output: str, simple_commands) -> bool:
    echoed = echoed_lines(simple_commands)
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped or stripped in echoed:
            continue
        if FIND_NOISE_LINE.match(stripped):
            continue
        return False
    return True


def bash_output(payload) -> str:
    if payload.get("hook_event_name") == "PostToolUseFailure":
        lines = str(payload.get("error") or "").splitlines()
        if lines and EXIT_CODE_LINE.match(lines[0]):
            lines = lines[1:]
        return "\n".join(lines)
    response = payload.get("tool_response") or {}
    if not isinstance(response, dict):
        return str(response)
    return "\n".join(str(response.get(key) or "")
                     for key in ("stdout", "stderr"))


def queries_from_bash(payload):
    command = str((payload.get("tool_input") or {}).get("command") or "")
    if not command:
        return []
    if any(name in command for name in SEARCH_PROGRAM_NAMES):
        return []
    directory = str(payload.get("cwd") or "")
    output = bash_output(payload)[:MAX_OUTPUT_CHARACTERS_SCANNED]
    simple_commands = split_simple_commands(command) or []
    finds = [words for words in simple_commands
             if words and program_name(words[0]) == "find"]
    queries = []

    if NO_SUCH_FILE_WORDS not in command.lower():
        for line in output.splitlines():
            if NO_SUCH_FILE not in line.lower():
                continue
            for pattern in NO_SUCH_FILE_LINE_PATTERNS:
                match = pattern.search(line.strip())
                if not match:
                    continue
                program = (match.groupdict().get("program") or "").lower()
                if program in PROGRAMS_NAMING_A_DIRECTORY:
                    break
                if program == "find":
                    # A search root that is missing: what was sought is the
                    # find's own -name.
                    for words in finds:
                        for value in find_name_arguments(words):
                            query = name_query(value)
                            if query:
                                queries.append(("no-such-file", value, query))
                    break
                query = path_query(match.group("path"), directory)
                if query:
                    queries.append(("no-such-file", match.group("path"), query))
                break

    if simple_commands and output_is_empty(output, simple_commands):
        for words in finds:
            for value in find_name_arguments(words):
                query = name_query(value)
                if query:
                    queries.append(("empty-find", value, query))
        for words in simple_commands:
            if not words or program_name(words[0]) != "git":
                continue
            found = git_log_pathspecs(words)
            if not found:
                continue
            git_directory, pathspecs = found
            base = directory
            if git_directory:
                base = os.path.join(directory or "/", git_directory)
            for spec in pathspecs:
                query = (name_query(spec) if GLOB_CHARACTERS.search(spec)
                         else path_query(spec, base))
                if query:
                    queries.append(("empty-git-log", spec, query))
    return queries


def queries_from_payload(payload):
    """[(trigger, raw text, locator query)] for a payload, at most
    MAX_QUERIES_PER_FIRE, each query once."""
    tool = payload.get("tool_name")
    event = payload.get("hook_event_name")
    queries = []
    if payload.get("is_interrupt"):
        return []
    if tool == "Read" and event == "PostToolUseFailure":
        error = str(payload.get("error") or "")
        if error.startswith(READ_MISSING_FILE_ERROR_PREFIX):
            raw = str((payload.get("tool_input") or {}).get("file_path") or "")
            query = path_query(raw, str(payload.get("cwd") or ""))
            if query:
                queries.append(("read-missing-file", raw, query))
    elif tool == "Bash" and event in ("PostToolUse", "PostToolUseFailure"):
        queries = queries_from_bash(payload)
    unique, seen = [], set()
    for trigger, raw, query in queries:
        if query in seen:
            continue
        seen.add(query)
        unique.append((trigger, raw, query))
    return unique[:MAX_QUERIES_PER_FIRE]


# --- records ----------------------------------------------------------------

def this_machine() -> str:
    return ("ned-box" if socket.gethostname().split(".")[0] == NED_BOX_HOSTNAME
            else "mac")


def record_file() -> Path:
    override = os.environ.get(RECORD_FILE_ENVIRONMENT_VARIABLE)
    if override:
        return Path(override)
    return NED_BOX_RECORD_FILE if this_machine() == "ned-box" \
        else MAC_RECORD_FILE


def utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def append_record(path: Path, record: dict) -> bool:
    """Append one JSON line. False when it could not be written; the caller
    carries on, because a record that cannot be kept must not fail a tool
    call."""
    line = (json.dumps(record, ensure_ascii=False) + "\n").encode("utf-8")
    try:
        descriptor = os.open(str(path), os.O_WRONLY | os.O_APPEND | os.O_CREAT,
                             0o644)
    except OSError:
        return False
    try:
        try:
            import fcntl
            fcntl.flock(descriptor, fcntl.LOCK_EX)
        except (ImportError, OSError):
            pass
        os.write(descriptor, line)
        return True
    except OSError:
        return False
    finally:
        os.close(descriptor)


def earlier_fire_of(path: Path, session_id: str, query: str):
    """The fire_id of a fire of this query from this session within the
    repeat window, or None."""
    try:
        with open(path, "rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - REPEAT_SCAN_BYTES))
            tail = handle.read().decode("utf-8", "replace")
    except OSError:
        return None
    now = time.time()
    for line in reversed(tail.splitlines()):
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if (record.get("kind") == "fire" and not record.get("repeat_of")
                and record.get("session_id") == session_id
                and record.get("query") == query
                and now - float(record.get("epoch", 0))
                < REPEAT_WINDOW_SECONDS):
            return record.get("fire_id")
    return None


def seat_of(project_directory: str):
    parts = Path(project_directory or "/").parts
    if "agents" in parts:
        index = parts.index("agents")
        if index + 1 < len(parts):
            return parts[index + 1]
    return None


def clipped(text, limit=MAX_TEXT_KEPT) -> str:
    text = str(text)
    return text if len(text) <= limit else text[:limit] + "..."


def start_locator(fire: dict, path: Path) -> bool:
    """Run the locator on the fire's query in a detached process that
    records its answer. False when it could not be started."""
    arguments = json.dumps({"fire_id": fire["fire_id"],
                            "query": fire["query"],
                            "record_file": str(path)})
    try:
        subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()),
             "--run-locator", arguments],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, close_fds=True,
            start_new_session=True, cwd="/")
        return True
    except OSError:
        return False


def handle_payload(payload) -> None:
    queries = queries_from_payload(payload)
    if not queries:
        return
    path = record_file()
    project_directory = os.environ.get("CLAUDE_PROJECT_DIR", "")
    session_id = str(payload.get("session_id") or "")
    command = (payload.get("tool_input") or {}).get("command")
    for trigger, raw, query in queries:
        fire = {
            "v": RECORD_VERSION, "kind": "fire",
            "fire_id": uuid.uuid4().hex[:12],
            "time": utc_now(), "epoch": round(time.time(), 3),
            "machine": this_machine(),
            "seat": seat_of(project_directory or str(payload.get("cwd") or "")),
            "cwd": payload.get("cwd"),
            "project_dir": project_directory or None,
            "session_id": session_id,
            "tool_use_id": payload.get("tool_use_id"),
            "event": payload.get("hook_event_name"),
            "tool": payload.get("tool_name"),
            "trigger": trigger,
            "raw": clipped(raw, MAX_LINE_CHARACTERS_KEPT),
            "query": query,
        }
        if command is not None:
            fire["command"] = clipped(command)
        earlier = earlier_fire_of(path, session_id, query)
        if earlier:
            fire["repeat_of"] = earlier
            append_record(path, fire)
            continue
        if not append_record(path, fire):
            continue
        start_locator(fire, path)


# --- the background run -----------------------------------------------------

def section_lines(text: str, heading_starts):
    """The entry lines under the first heading that starts with one of
    `heading_starts`, up to the next blank line: (entries, more_not_shown)."""
    entries, more, inside = [], 0, False
    for line in text.splitlines():
        if not inside:
            inside = any(line.startswith(start) for start in heading_starts)
            continue
        if not line.strip():
            break
        more_match = re.match(r"^  \.\.\. and (\d+) more not shown", line)
        if more_match:
            more = int(more_match.group(1))
        elif line.startswith("  ") and not line.startswith("   "):
            entries.append(line.strip())
    return entries, more


def summarize_answer(text: str, exit_code) -> dict:
    found, _ = section_lines(text, ("Same name (", "Same path ("))
    candidates, more = section_lines(text, ("Candidates only",))
    not_searched, _ = section_lines(text, ("NOT searched",))
    outcome = {0: "found", 1: "not-found", 2: "usage-error",
               3: "incomplete"}.get(exit_code, "error")
    return {
        "outcome": outcome,
        "found_count": len(found),
        "found": [clipped(line, MAX_LINE_CHARACTERS_KEPT)
                  for line in found[:MAX_LINES_KEPT_PER_LIST]],
        "candidates_count": len(candidates) + more,
        "candidates": [clipped(line, MAX_LINE_CHARACTERS_KEPT)
                       for line in candidates[:MAX_LINES_KEPT_PER_LIST]],
        "not_searched": [clipped(line, MAX_LINE_CHARACTERS_KEPT)
                         for line in not_searched[:MAX_LINES_KEPT_PER_LIST]],
    }


def locator_environment() -> dict:
    environment = dict(os.environ)
    for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE",
                 "GIT_COMMON_DIR", "GIT_OBJECT_DIRECTORY"):
        environment.pop(name, None)
    return environment


def run_locator(arguments: dict) -> None:
    locator = os.environ.get(LOCATOR_ENVIRONMENT_VARIABLE) or str(LOCATOR_PATH)
    started = time.monotonic()
    result = {"v": RECORD_VERSION, "kind": "result",
              "fire_id": arguments.get("fire_id"),
              "query": arguments.get("query")}
    if not os.path.isfile(locator):
        result.update({"exit_code": None, "outcome": "error",
                       "stderr_tail": f"no locator at {locator}"})
        result["duration_s"] = 0.0
        result["time"] = utc_now()
        append_record(Path(arguments.get("record_file") or record_file()),
                      result)
        return
    try:
        process = subprocess.run(
            [sys.executable, locator, "--", arguments["query"]],
            stdin=subprocess.DEVNULL, capture_output=True, text=True,
            errors="replace", timeout=LOCATOR_TIMEOUT_SECONDS, cwd="/",
            env=locator_environment())
        result["exit_code"] = process.returncode
        result.update(summarize_answer(process.stdout, process.returncode))
        if result["outcome"] in ("error", "usage-error"):
            result["stderr_tail"] = clipped(process.stderr[-MAX_TEXT_KEPT:])
    except subprocess.TimeoutExpired:
        result.update({"exit_code": None, "outcome": "timeout"})
    except (OSError, KeyError) as error:
        result.update({"exit_code": None, "outcome": "error",
                       "stderr_tail": clipped(repr(error))})
    result["duration_s"] = round(time.monotonic() - started, 2)
    result["time"] = utc_now()
    append_record(Path(arguments.get("record_file") or record_file()), result)


# --- the week's counts ------------------------------------------------------

def summarize_files(paths) -> str:
    fires, results = [], {}
    for path in paths:
        with open(path, encoding="utf-8", errors="replace") as handle:
            for line in handle:
                try:
                    record = json.loads(line)
                except ValueError:
                    continue
                if record.get("kind") == "fire":
                    fires.append(record)
                elif record.get("kind") == "result":
                    results[record.get("fire_id")] = record
    first = [fire for fire in fires if not fire.get("repeat_of")]
    lines = [f"{len(fires)} fires, {len(fires) - len(first)} of them repeats; "
             f"{len(first)} locator runs, {len(results)} answered"]

    def count(label, key):
        tally = {}
        for fire in first:
            value = key(fire)
            tally[value] = tally.get(value, 0) + 1
        lines.append(label + ": " + ", ".join(
            f"{value} {number}" for value, number in sorted(
                tally.items(), key=lambda item: (-item[1], str(item[0])))))

    count("by machine", lambda fire: fire.get("machine"))
    count("by trigger", lambda fire: fire.get("trigger"))
    count("by outcome", lambda fire: (results.get(fire.get("fire_id")) or {})
          .get("outcome", "no answer"))
    with_candidates = sum(
        1 for fire in first
        if (results.get(fire.get("fire_id")) or {}).get("outcome") != "found"
        and (results.get(fire.get("fire_id")) or {}).get("candidates_count"))
    lines.append(f"not found at the path asked, with candidates listed: "
                 f"{with_candidates}")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["--run-locator"]:
        try:
            run_locator(json.loads(argv[1]))
        except Exception:  # noqa: BLE001 -- a background run never raises
            pass
        return 0
    if argv[:1] == ["--summarize"]:
        parser = argparse.ArgumentParser(prog=PROGRAM)
        parser.add_argument("--summarize", nargs="+", metavar="RECORD_FILE",
                            required=True)
        sys.stdout.write(summarize_files(parser.parse_args(argv).summarize))
        return 0
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        if isinstance(payload, dict):
            handle_payload(payload)
    except Exception:  # noqa: BLE001 -- a hook that fails a turn is worse
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
