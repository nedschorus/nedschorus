#!/usr/bin/env python3
"""Search the log-store's records of past discussions for one pattern, newest first.

Usage:
  scripts/log-store-past-discussions-regex-search-newest-first.py PATTERN
      [--kind KIND]... [--seat SUBSTRING] [--machine {ned-box,mac}]
      [--since YYYY-MM-DD] [--until YYYY-MM-DD] [--context N] [--limit N] [--skip N] [--jobs N]
      [--include-own-session]

WHAT IT SEARCHES. Five kinds of record in the log-store,
/home/nedlern/nedschorus-logs/ on ned-box:

  walk               walk/: walk-documents, drafts, suggestions and walk-minutes
  cold-read-records  cold-read-records/
  analysis           analysis/: analyses and research
  session-dialogs    session-dialogs/<machine>/<project-key>/: each session's
                     complete filtered dialog, subagent tasks and reports included
  user-messages      the user's typed messages in the transcripts under
                     transcripts/<machine>/projects/<project-key>/*.jsonl

The transcripts' subagents/ directories and transcripts/recovered/ are not
searched. A user's message is usually found twice, once in his session's
dialog and once among user-messages; the user-messages hit carries the time
he sent it, and the session-dialogs hit the turns around it.

PATTERN is a regular expression, matched case-insensitively; one opening
with a dash goes after --, as in `-- -foo`. ripgrep matches
it in every kind; the user's messages are then read with the handoff
extractor's reader (scripts/handoff-extract-conversation.py) and matched again
with Python's re module, so the pattern must be one both read. ripgrep picks
the transcripts to read from their raw JSON, with the pattern's anchors (^, $,
\\A, \\z) removed, since there a message is one string inside a longer line.
JSON writes a line break, a tab, a quote mark and a backslash as escapes, so a
pattern that could match one of them (., a [class], \\s, \\W, \\b, a quote mark,
a backslash and the like) skips that step and every transcript is read.

WHAT EACH HIT SAYS. Its kind, date, machine and agent-seat where the record
shows them, its file and line, and the matching line with --context lines
either side (default 1); a user's message is shown as an excerpt around the
match. The date is the one in the file's name for walk, cold-read-records and
analysis, or the file's modification date when the name has none; the time
the user sent a message; and for a session dialog the time of the turn that
holds the matching line: a dialog's turns carry no time, so the line is found
in the session's transcript, and the first record that holds it gives the
time. A line shorter than TURN_LOOKUP_MINIMUM_CHARACTERS, or one no record
holds, is dated by the session's last activity, the last timestamp in its
transcript, and the hit says so. A walk file's agent-seat is
the one its header says ran the approval-walk. A session's agent-seat is read
from its project-key, the transcript folder Claude Code names after the
session's directory.

FILTERS. --kind limits the search to the kinds named. --seat keeps sessions
whose project-key contains SUBSTRING, and --machine those of one machine;
either one searches only session-dialogs and user-messages, the two kinds
that record a session. --since and --until bound the hit's date, inclusive,
in UTC; a session dialog's hit dated by the session's last activity is kept
when the session was active at any time in the window. The agent-session
running the search, which $CLAUDE_CODE_SESSION_ID names, is left out, its
dialog and its messages both, since its own hits only echo the search;
--include-own-session searches it too, and the closing lines say which. Hits
come newest first, hits with one date in file and line order; --limit (default 30) caps how many are
shown and --skip passes over the first N, so the closing line says how to see
the next ones.

SPEED. ripgrep searches the other kinds while it finds the transcripts that
hold the pattern. The program then reads those transcripts in --jobs
processes (default one per core), newest modification time first, and stops
once the page of hits is full and every unread transcript was last written
before the page's oldest hit, since no message in it could change the page.
The hits shown are the ones a full read would show; the closing line then
says older transcripts were not read, in place of the count of all hits.
--limit 0 reads every transcript.

FROM THE MAC. The whole log-store, the Mac's mirrored transcripts and session
dialogs included, is on ned-box. When the log-store is not on this machine
and this machine is not ned-box, the program runs ned-box's copy,
/home/nedlern/Projects/nedschorus/scripts/<this program>, over
`ssh nedlern@ned-box` with the same arguments, and passes the running
agent-session's identity, which ned-box's copy cannot see. Reading eleven gigabytes of
transcripts through the Mac's mount /Volumes/nedhome/nedschorus-logs would
be slow, and ripgrep is not reliably on the Mac's PATH.

FAILURES. A record that could not be searched prints a line opening FAILED,
naming what failed and what to do, after the hits found elsewhere: a missing
log-store or kind directory, a file ripgrep could not read, a transcript the
reader could not read, ripgrep missing, ned-box unreachable from the Mac.
After the FAILED lines, one closing line says what the failures mean for the
page: when hits were printed, that they are real matches but the page may lack
hits from the failed records; when none were, that a match may be in those
records. It then says what to tell the user about each FAILED line, what a
"Permission denied" line means, and which remedies to run.

Exit 0 when hits were found and everything was searched; 1 when nothing
matched and everything was searched; 2 when anything could not be searched,
or the arguments were wrong.

Environment, for the tests:
  LOG_STORE_PAST_DISCUSSIONS_SEARCH_LOG_STORE_ROOT_OVERRIDE  the log-store's root
  LOG_STORE_PAST_DISCUSSIONS_SEARCH_RIPGREP_PROGRAM_OVERRIDE  the rg program
  LOG_STORE_PAST_DISCUSSIONS_SEARCH_SSH_PROGRAM_OVERRIDE      the ssh program
  LOG_STORE_PAST_DISCUSSIONS_SEARCH_THIS_MACHINE_OVERRIDE     this machine's name
"""

import argparse
import collections
import concurrent.futures
import datetime
import heapq
import importlib.util
import itertools
import json
import os
import re
import shlex
import socket
import subprocess
import sys
from pathlib import Path

PROGRAM_FILE_NAME = "log-store-past-discussions-regex-search-newest-first.py"
DEFAULT_LOG_STORE_ROOT = Path("/home/nedlern/nedschorus-logs")
NED_BOX_HOSTNAME = "ned-box"
NED_BOX_SSH_TARGET = "nedlern@ned-box"
NED_BOX_PROGRAM_PATH = f"/home/nedlern/Projects/nedschorus/scripts/{PROGRAM_FILE_NAME}"
SSH_OPTIONS = ["-o", "BatchMode=yes", "-o", "ConnectTimeout=10"]
SSH_EXIT_CONNECTION_FAILED = 255

ENVIRONMENT_PREFIX = "LOG_STORE_PAST_DISCUSSIONS_SEARCH_"
ROOT_OVERRIDE = ENVIRONMENT_PREFIX + "LOG_STORE_ROOT_OVERRIDE"
RIPGREP_OVERRIDE = ENVIRONMENT_PREFIX + "RIPGREP_PROGRAM_OVERRIDE"
SSH_OVERRIDE = ENVIRONMENT_PREFIX + "SSH_PROGRAM_OVERRIDE"
THIS_MACHINE_OVERRIDE = ENVIRONMENT_PREFIX + "THIS_MACHINE_OVERRIDE"

EXIT_FOUND = 0
EXIT_NOTHING_FOUND = 1
EXIT_FAILED = 2
FAILURES_CLOSING_HITS_SHOWN = (
    "Each hit printed above is a real match, but the records the FAILED lines name were not searched or "
    "not dated, so the page may lack hits from them, newer ones included, and a hit dated \"date unknown\" "
    "may be out of order.")
FAILURES_CLOSING_NO_HITS_SHOWN = (
    "No hit was printed, but the records the FAILED lines name were not searched or not dated, so a match "
    "may be in them: do not say nothing matched.")
FAILURES_CLOSING_WHAT_TO_DO = (
    "Tell the user what each FAILED line names and why: a record not searched, a directory not searched, "
    "which leaves out everything under it, or a record not dated. A \"Permission denied\" line means the "
    "account running this search cannot read that path: tell the user the path, and do not change the "
    "path's permissions. Where a FAILED line names a remedy, run it if it reruns this search, and tell "
    "the user any other.")


def failures_closing_line(hits_shown):
    """The line printed after the FAILED lines; what it says about the hits depends on whether any printed."""
    said_about_hits = FAILURES_CLOSING_HITS_SHOWN if hits_shown else FAILURES_CLOSING_NO_HITS_SHOWN
    return f"{said_about_hits} {FAILURES_CLOSING_WHAT_TO_DO}"

FILE_KIND_DIRECTORIES = {
    "walk": "walk",
    "cold-read-records": "cold-read-records",
    "analysis": "analysis",
}
SESSION_DIALOGS = "session-dialogs"
USER_MESSAGES = "user-messages"
KINDS = list(FILE_KIND_DIRECTORIES) + [SESSION_DIALOGS, USER_MESSAGES]
MACHINES = ("ned-box", "mac")

DEFAULT_LIMIT = 30
EXCERPT_CHARACTERS = 300
CONTEXT_CHARACTERS = 200
WALK_HEADER_LINES = 10
DATE_IN_NAME = re.compile(r"\d{4}-\d{2}-\d{2}")
WALK_HEADER_SEAT = re.compile(r"\brun by ([A-Za-z0-9][A-Za-z0-9-]*) on\b")
SEAT_IN_PROJECT_KEY = re.compile(r"-agents-(.+?)(?:--claude-worktrees-.*|-worktrees-.*)?$")
DIALOG_FILE_SUFFIX = "-dialog-complete.md"
MODIFICATION_TIME_MARGIN_SECONDS = 2
TRANSCRIPT_TAIL_BYTES = 64 * 1024
# Shorter lines, such as "yes", occur in too many records to say which turn holds them.
TURN_LOOKUP_MINIMUM_CHARACTERS = 12
TURN_LOOKUP_MAXIMUM_CHARACTERS = 160
OWN_SESSION_VARIABLE = "CLAUDE_CODE_SESSION_ID"
NOT_FOUND_IN_TRANSCRIPT_NOTE = "session's last activity: its turn was not found in the transcript"


def load_handoff_extractor():
    path = Path(__file__).resolve().parent / "handoff-extract-conversation.py"
    spec = importlib.util.spec_from_file_location("handoff_extract_conversation", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def this_machine():
    return os.environ.get(THIS_MACHINE_OVERRIDE) or socket.gethostname().split(".")[0]


def run_on_ned_box_over_ssh(arguments):
    """Run ned-box's copy of this program with the same arguments; return its exit code."""
    ssh = os.environ.get(SSH_OVERRIDE) or "ssh"
    remote = "python3 " + shlex.join([NED_BOX_PROGRAM_PATH] + arguments)
    try:
        completed = subprocess.run([ssh, *SSH_OPTIONS, NED_BOX_SSH_TARGET, remote],
                                   stdin=subprocess.DEVNULL, stderr=subprocess.PIPE)
    except FileNotFoundError:
        print(f"FAILED: ssh is not installed on {this_machine()}, and the log-store is on ned-box.\n"
              f"Run this program on ned-box itself.", file=sys.stderr)
        return EXIT_FAILED
    said = completed.stderr.decode("utf-8", "replace")
    if completed.returncode == SSH_EXIT_CONNECTION_FAILED:
        print(f"FAILED: the log-store is on ned-box, and ned-box could not be reached "
              f"(ssh exited {SSH_EXIT_CONNECTION_FAILED}): {said.strip() or 'ssh said nothing'}\n"
              f"Check that ned-box is on and on the LAN, and that this machine's key reaches it: "
              f"ssh {NED_BOX_SSH_TARGET} true", file=sys.stderr)
        return EXIT_FAILED
    sys.stderr.write(said)
    return completed.returncode


def iso_date(text):
    try:
        datetime.date.fromisoformat(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a date of the form YYYY-MM-DD: {text!r}")
    return text


def utc_iso(seconds):
    return datetime.datetime.fromtimestamp(seconds, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def seat_from_project_key(key):
    match = SEAT_IN_PROJECT_KEY.search(key)
    return match.group(1) if match else ""


def session_parts(path, root):
    """Return (machine, project_key) for a path under session-dialogs/ or transcripts/."""
    parts = path.relative_to(root).parts
    if parts[0] == SESSION_DIALOGS:
        return parts[1], parts[2]
    return parts[1], parts[3]


def in_window(date, since, until):
    """Whether a hit dated `date` (any ISO prefix, or "" when unknown) is in the window."""
    if not date:
        return True
    day = date[:10]
    return (since is None or day >= since) and (until is None or day <= until)


def timestamp_of(line):
    try:
        stamp = json.loads(line).get("timestamp")
    except (ValueError, AttributeError):
        return ""
    return stamp if isinstance(stamp, str) else ""


def session_start(transcript):
    """The first timestamp in a transcript, or "" when it has none or there is no transcript.

    Raises OSError when the transcript is there but cannot be read.
    """
    try:
        with transcript.open("rb") as handle:
            for line in handle:
                stamp = timestamp_of(line)
                if stamp:
                    return stamp
    except FileNotFoundError:
        pass
    return ""


def session_last_activity(transcript):
    """The last timestamp in a transcript, or "" when it has none or there is no transcript.

    Raises OSError when the transcript is there but cannot be read. Reads backwards from the end in growing blocks, since a transcript can be hundreds of megabytes.
    """
    try:
        with transcript.open("rb") as handle:
            size = handle.seek(0, os.SEEK_END)
            block = TRANSCRIPT_TAIL_BYTES
            while True:
                start = max(0, size - block)
                handle.seek(start)
                lines = handle.read(size - start).splitlines()
                if start > 0:
                    lines = lines[1:]
                for line in reversed(lines):
                    stamp = timestamp_of(line)
                    if stamp:
                        return stamp
                if start == 0:
                    return ""
                block *= 4
    except FileNotFoundError:
        return ""


def walk_seat(path, failures):
    try:
        with path.open(errors="replace") as handle:
            header = "".join(handle.readline() for _ in range(WALK_HEADER_LINES))
    except OSError as error:
        failures.append(f"could not read the header of {path} for its agent-seat: {error}")
        return ""
    match = WALK_HEADER_SEAT.search(header)
    return match.group(1) if match else ""


def excerpt(text, start):
    """About EXCERPT_CHARACTERS of one line of text around position `start`."""
    begin = max(0, start - EXCERPT_CHARACTERS // 3)
    piece = text[begin:begin + EXCERPT_CHARACTERS]
    return ("…" if begin else "") + piece + ("…" if begin + EXCERPT_CHARACTERS < len(text) else "")


def ripgrep_command(arguments_before_pattern, pattern, paths):
    ripgrep = os.environ.get(RIPGREP_OVERRIDE) or "rg"
    return [ripgrep, "--no-ignore", "--hidden", "--ignore-case", *arguments_before_pattern,
            "-e", pattern, "--", *[str(path) for path in paths]]


def run_ripgrep(command, failures):
    """Run ripgrep; return its stdout, adding each error it printed to failures."""
    try:
        completed = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True)
    except FileNotFoundError:
        raise RipgrepMissing(command[0])
    for line in completed.stderr.decode("utf-8", "replace").splitlines():
        if line.strip():
            failures.append(f"ripgrep could not search everything: {line.strip()}")
    if completed.returncode not in (0, 1) and not completed.stderr.strip():
        failures.append(f"ripgrep exited {completed.returncode} and said nothing")
    return completed.stdout.decode("utf-8", "replace")


class RipgrepMissing(Exception):
    pass


def file_facts(path, root, failures):
    """The kind, machine, agent-seat and, where its name holds one, the date of one file's hits.

    None for a file in session-dialogs/ that is not a session dialog.
    """
    parts = path.relative_to(root).parts
    kind = parts[0]
    facts = {"kind": kind, "machine": "", "seat": ""}
    if kind == SESSION_DIALOGS:
        # The refresher keeps its own state files beside the machines' directories.
        if len(parts) != 4 or not parts[3].endswith(DIALOG_FILE_SUFFIX):
            return None
        facts["machine"], key = session_parts(path, root)
        facts["seat"] = seat_from_project_key(key)
        facts["project_key"] = key
    else:
        named = DATE_IN_NAME.search(str(path.relative_to(root / kind)))
        facts["date"] = named.group(0) if named else None
        if kind == "walk":
            facts["seat"] = walk_seat(path, failures)
    return facts


def file_hits(root, kinds, pattern, context, failures):
    """Hits from ripgrep over the file kinds and session-dialogs, each a dict."""
    directories = []
    for kind in kinds:
        if kind in FILE_KIND_DIRECTORIES:
            directories.append(root / FILE_KIND_DIRECTORIES[kind])
        elif kind == SESSION_DIALOGS:
            directories.append(root / SESSION_DIALOGS)
    present = []
    for directory in directories:
        if directory.is_dir():
            present.append(directory)
        else:
            failures.append(f"the log-store has no {directory}, so it was not searched")
    if not present:
        return []
    output = run_ripgrep(ripgrep_command(["--json", "--context", str(context)], pattern, present),
                         failures)
    lines_by_file = {}
    matches = []
    for raw in output.splitlines():
        try:
            message = json.loads(raw)
        except ValueError:
            continue
        if message.get("type") not in ("match", "context"):
            continue
        data = message["data"]
        path = data.get("path", {}).get("text")
        text = data.get("lines", {}).get("text")
        number = data.get("line_number")
        if path is None or text is None or number is None:
            continue
        text = text.rstrip("\n")
        lines_by_file.setdefault(path, {})[number] = text
        if message["type"] == "match":
            submatches = data.get("submatches") or []
            start_byte = submatches[0]["start"] if submatches else 0
            # ripgrep counts bytes; the excerpt counts characters.
            start = len(text.encode("utf-8")[:start_byte].decode("utf-8", "ignore"))
            matches.append((path, number, excerpt(text, start), text))
    hits = []
    facts_by_file = {}
    for path_text, number, shown, text in matches:
        if path_text not in facts_by_file:
            facts_by_file[path_text] = file_facts(Path(path_text), root, failures)
        if facts_by_file[path_text] is None:
            continue
        nearby = lines_by_file[path_text]
        hit = {"path": path_text, "line": number, "shown": shown, "text": text,
               "before": [(n, nearby[n][:CONTEXT_CHARACTERS]) for n in range(number - context, number)
                          if n in nearby],
               "after": [(n, nearby[n][:CONTEXT_CHARACTERS]) for n in range(number + 1, number + context + 1)
                         if n in nearby]}
        hit.update(facts_by_file[path_text])
        hits.append(hit)
    return hits


def session_transcript(root, hit):
    session_id = Path(hit["path"]).name[:-len(DIALOG_FILE_SUFFIX)]
    return root / "transcripts" / hit["machine"] / "projects" / hit["project_key"] / f"{session_id}.jsonl"


def turn_lookup_needle(line):
    """The text to find a dialog line's turn by in the raw transcript, or None when it is too short.

    A dialog line is a line of a message's text, which the transcript holds as a JSON string.
    """
    text = line.strip()
    if len(text) < TURN_LOOKUP_MINIMUM_CHARACTERS:
        return None
    return json.dumps(text[:TURN_LOOKUP_MAXIMUM_CHARACTERS], ensure_ascii=False)[1:-1]


def turn_times(transcript, needles, failures):
    """Map each needle to the timestamp of the first transcript record that holds it.

    A needle no record holds is left out. One ripgrep pass reads the transcript.
    """
    if not needles:
        return {}
    arguments = ["--no-filename", "--fixed-strings"]
    for needle in needles:
        arguments += ["-e", needle]
    ripgrep = os.environ.get(RIPGREP_OVERRIDE) or "rg"
    try:
        completed = subprocess.run([ripgrep, "--no-ignore", "--hidden", *arguments, "--", str(transcript)],
                                   stdin=subprocess.DEVNULL, capture_output=True)
    except FileNotFoundError:
        raise RipgrepMissing(ripgrep)
    said = completed.stderr.decode("utf-8", "replace").strip()
    if completed.returncode not in (0, 1) or said:
        failures.append(f"could not read the transcript {transcript} to date the session dialog's hits "
                        f"by their turns: {said or f'ripgrep exited {completed.returncode}'}")
    found = {}
    waiting = set(needles)
    for line in completed.stdout.decode("utf-8", "replace").splitlines():
        if not waiting:
            break
        stamp = timestamp_of(line)
        if not stamp:
            continue
        for needle in [n for n in waiting if n in line]:
            found[needle] = stamp
            waiting.discard(needle)
    return found


def session_id_of(path):
    name = Path(path).name
    if name.endswith(DIALOG_FILE_SUFFIX):
        return name[:-len(DIALOG_FILE_SUFFIX)]
    return Path(path).stem


def dialog_turn_dates(hits, root, failures):
    """Set each session-dialog hit's "turn_date": its own turn's timestamp, or "" when not found."""
    needles_by_transcript = {}
    for hit in hits:
        hit["needle"] = turn_lookup_needle(hit.get("text", ""))
        if hit["needle"]:
            needles_by_transcript.setdefault(session_transcript(root, hit), set()).add(hit["needle"])
    times = {}
    if needles_by_transcript:
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, len(needles_by_transcript))) as threads:
            futures = {transcript: threads.submit(turn_times, transcript, sorted(needles), failures)
                       for transcript, needles in needles_by_transcript.items() if transcript.is_file()}
            for transcript, future in futures.items():
                times[transcript] = future.result()
    for hit in hits:
        hit["turn_date"] = times.get(session_transcript(root, hit), {}).get(hit["needle"], "")


def dated_file_hits(hits, root, seat, machine, since, until, failures, own_session=""):
    """Fill in each hit's date and drop those outside the filters."""
    kept = []
    modification_dates = {}
    last_activities = {}
    starts = {}
    selected = []
    for hit in hits:
        if hit["kind"] == SESSION_DIALOGS:
            if machine and hit["machine"] != machine:
                continue
            if seat and seat not in hit["project_key"]:
                continue
            if own_session and session_id_of(hit["path"]) == own_session:
                continue
        selected.append(hit)
    dialog_turn_dates([hit for hit in selected if hit["kind"] == SESSION_DIALOGS], root, failures)
    for hit in selected:
        path = Path(hit["path"])
        if hit["kind"] == SESSION_DIALOGS and hit["turn_date"]:
            hit["date"] = hit["turn_date"]
            if not in_window(hit["date"], since, until):
                continue
            kept.append(hit)
            continue
        if hit["kind"] == SESSION_DIALOGS:
            if hit["path"] not in last_activities:
                transcript = session_transcript(root, hit)
                try:
                    last_activities[hit["path"]] = session_last_activity(transcript)
                except OSError as error:
                    failures.append(f"could not read the transcript {transcript} to date the session "
                                    f"dialog {path}: {error}")
                    last_activities[hit["path"]] = ""
            hit["date"] = last_activities[hit["path"]]
        elif hit.get("date") is None:
            if hit["path"] not in modification_dates:
                try:
                    modification_dates[hit["path"]] = utc_iso(path.stat().st_mtime)
                except OSError as error:
                    failures.append(f"could not read the date of {path}: {error}")
                    modification_dates[hit["path"]] = ""
            hit["date"] = modification_dates[hit["path"]]
        if hit["kind"] == SESSION_DIALOGS:
            if hit["date"]:
                hit["date_note"] = NOT_FOUND_IN_TRANSCRIPT_NOTE
            last = hit["date"][:10]
            if since and last and last < since:
                continue
            if until and last and last > until:
                if hit["path"] not in starts:
                    transcript = session_transcript(root, hit)
                    try:
                        starts[hit["path"]] = session_start(transcript)
                    except OSError as error:
                        failures.append(f"could not read the transcript {transcript} for the start of the "
                                        f"session dialog {path}: {error}")
                        starts[hit["path"]] = ""
                start = starts[hit["path"]][:10]
                if start and start > until:
                    continue
        elif not in_window(hit["date"], since, until):
            continue
        kept.append(hit)
    return kept


def pattern_without_anchors(pattern):
    """The pattern with its line and text anchors removed, for ripgrep to pick transcripts by.

    ripgrep reads a transcript's raw JSON records, where a message is one quoted string inside
    a longer line, so an anchor such as ^ or $ would miss it. Without its anchors the pattern
    matches wherever it matched before, and the user's messages are then matched with them.
    """
    kept = []
    in_class = False
    index = 0
    while index < len(pattern):
        character = pattern[index]
        if character == "\\" and index + 1 < len(pattern):
            if in_class or pattern[index + 1] not in "AzZ":
                kept.append(pattern[index:index + 2])
            index += 2
            continue
        if in_class:
            closing = pattern.find(":]", index + 2)
            if pattern.startswith("[:", index) and closing != -1:
                kept.append(pattern[index:closing + 2])
                index = closing + 2
                continue
            if character == "]":
                in_class = False
        elif character == "[":
            in_class = True
            kept.append("[")
            index += 1
            # A ] first in a class, or right after its ^, is a literal ].
            for opening in "^]":
                if pattern[index:index + 1] == opening:
                    kept.append(opening)
                    index += 1
            continue
        elif character in "^$":
            index += 1
            continue
        kept.append(character)
        index += 1
    return "".join(kept)


def raw_json_prefilter(pattern):
    """The pattern for ripgrep to pick transcripts by, or None when every transcript must be read.

    ripgrep reads a transcript's raw JSON, where a line break, a tab, a quote mark, a backslash
    and other control characters are each written as an escape of two or more characters. A
    pattern that could match one of those characters in a message could fail to match its
    escape, so it gets no prefilter. Anchors are dropped first, since in the JSON a message is
    one string inside a longer line.
    """
    pattern = pattern_without_anchors(pattern)
    index = 0
    while index < len(pattern):
        character = pattern[index]
        if character == "\\":
            following = pattern[index + 1:index + 2]
            # \w and \d match only characters JSON writes as themselves; every other escaped
            # letter or digit (\s, \S, \W, \D, \b, \n, \t, \x, \u, \p, back-references) may not.
            if following in ("\\", '"') or (following.isalnum() and following not in "wd"):
                return None
            index += 2
            continue
        if character in '.["' or ord(character) < 0x20:
            return None
        index += 1
    return pattern


def every_transcript(directories, failures):
    """Every <project-key>/<session>.jsonl under the given projects directories."""
    paths = []
    for directory in directories:
        try:
            keys = sorted(entry.path for entry in os.scandir(directory) if entry.is_dir())
        except OSError as error:
            failures.append(f"could not list the transcripts in {directory}: {error}")
            continue
        for key in keys:
            try:
                paths += [entry.path for entry in os.scandir(key)
                          if entry.name.endswith(".jsonl") and entry.is_file()]
            except OSError as error:
                failures.append(f"could not list the transcripts in {key}: {error}")
    return paths


def transcript_candidates(root, pattern, seat, machine, since, failures, own_session=""):
    """The transcripts ripgrep finds the pattern in, as (path, modification time), in path order.

    Returns None when Python cannot read the pattern, since then no transcript is read.
    """
    try:
        re.compile(pattern, re.IGNORECASE)
    except re.error as error:
        failures.append(f"the user's messages were not searched: Python's re module cannot read "
                        f"the pattern ({error}); give a pattern both ripgrep and Python read, "
                        f"or pass --kind to search the other kinds alone")
        return None
    directories = []
    for each in ([machine] if machine else MACHINES):
        directory = root / "transcripts" / each / "projects"
        if directory.is_dir():
            directories.append(directory)
        else:
            failures.append(f"the log-store has no {directory}, so {each}'s transcripts were not searched")
    if not directories:
        return []
    prefilter = raw_json_prefilter(pattern)
    if prefilter is None:
        paths = every_transcript(directories, failures)
    else:
        output = run_ripgrep(ripgrep_command(["--files-with-matches", "--max-depth", "2", "--glob", "*.jsonl"],
                                             prefilter, directories), failures)
        paths = output.splitlines()
    candidates = []
    for line in sorted(paths):
        path = Path(line)
        if seat and seat not in session_parts(path, root)[1]:
            continue
        if own_session and path.stem == own_session:
            continue
        try:
            modified = path.stat().st_mtime
        except OSError as error:
            candidates.append((path, None, f"could not read the transcript {path}: {error}"))
            continue
        if since and utc_iso(modified)[:10] < since:
            continue
        candidates.append((path, modified, None))
    return candidates


_extractor_in_this_process = None


def matching_user_messages(path_text, pattern, since, until):
    """Return (timestamp and excerpt of each matching user message, error or None) for one transcript.

    Runs in a worker process, so it takes and returns only plain values.
    """
    global _extractor_in_this_process
    if _extractor_in_this_process is None:
        _extractor_in_this_process = load_handoff_extractor()
    try:
        turns, _ = _extractor_in_this_process.read_dialog_turns(Path(path_text), drop_acknowledgements=False)
    except OSError as error:
        return [], f"could not read the transcript {path_text}: {error}"
    regex = re.compile(pattern, re.IGNORECASE)
    found_messages = []
    for turn in turns:
        if turn.get("voice") != "user":
            continue
        found = regex.search(turn["text"])
        if not found or not in_window(turn.get("timestamp", ""), since, until):
            continue
        flat = " ".join(turn["text"][:found.start()].split())
        whole = " ".join(turn["text"].split())
        found_messages.append((turn.get("timestamp", ""), "USER: " + excerpt(whole, len(flat))))
    return found_messages, None


def newest_first_results(paths, pattern, since, until, jobs):
    """Yield each transcript's result, newest transcript first, read by `jobs` processes."""
    arguments = [(str(path), pattern, since, until) for path in paths]
    if jobs <= 1 or len(arguments) <= 1:
        for each in arguments:
            yield matching_user_messages(*each)
        return
    executor = concurrent.futures.ProcessPoolExecutor(max_workers=min(jobs, len(arguments)))
    try:
        in_flight = collections.deque()
        upcoming = iter(arguments)
        for each in itertools.islice(upcoming, 2 * jobs):
            in_flight.append(executor.submit(matching_user_messages, *each))
        while in_flight:
            result = in_flight.popleft().result()
            for each in itertools.islice(upcoming, 1):
                in_flight.append(executor.submit(matching_user_messages, *each))
            yield result
    finally:
        executor.shutdown(wait=True, cancel_futures=True)


def user_message_hits(root, candidates, pattern, since, until, jobs, page_size, other_dates, failures):
    """Hits among the user's typed messages; and whether older transcripts were left unread.

    Transcripts are read newest first by modification time. Once page_size hits are in hand
    and the next transcript was last written before the page's oldest hit, no unread
    transcript can change the page, so reading stops. Hits and failures come back in path
    order, the order a full read gives them.
    """
    readable = sorted((c for c in candidates if c[1] is not None), key=lambda c: (-c[1], str(c[0])))
    results = {}
    page = [date or "" for date in other_dates]
    heapq.heapify(page)
    while page_size and len(page) > page_size:
        heapq.heappop(page)
    stopped_early = False
    reader = newest_first_results([c[0] for c in readable], pattern, since, until, jobs)
    try:
        for index, (found_messages, error) in enumerate(reader):
            results[readable[index][0]] = (found_messages, error)
            for date, _ in found_messages:
                if page_size:
                    if len(page) < page_size:
                        heapq.heappush(page, date or "")
                    elif (date or "") > page[0]:
                        heapq.heapreplace(page, date or "")
            if page_size and len(page) == page_size and index + 1 < len(readable):
                # Relies on no message being dated after its transcript's modification time: the
                # mirror copies each transcript with its source's modification time, the time of its
                # last write, kept only to the whole second, which MODIFICATION_TIME_MARGIN_SECONDS
                # covers. The loop below reports a transcript that breaks this.
                newest_unread = utc_iso(readable[index + 1][1] + MODIFICATION_TIME_MARGIN_SECONDS)
                if newest_unread < page[0]:
                    stopped_early = True
                    break
    finally:
        reader.close()
    hits = []
    for path, modified, stat_error in candidates:
        if stat_error:
            failures.append(stat_error)
            continue
        if path not in results:
            continue
        found_messages, error = results[path]
        if error:
            failures.append(error)
            continue
        transcript_machine, key = session_parts(path, root)
        latest = max((date for date, _ in found_messages), default="")
        if latest > utc_iso(modified + MODIFICATION_TIME_MARGIN_SECONDS) and (stopped_early or since):
            failures.append(f"the transcript {path} holds a message dated {latest}, after its modification "
                            f"time {utc_iso(modified)}, so --since or the early stop may have left out "
                            f"other transcripts' hits; rerun with --limit 0 and without --since")
        for date, shown in found_messages:
            hits.append({"kind": USER_MESSAGES, "path": str(path), "line": None,
                         "shown": shown, "before": [], "after": [],
                         "date": date, "machine": transcript_machine,
                         "seat": seat_from_project_key(key)})
    return hits, stopped_early


def print_hit(hit):
    date = hit["date"] or "date unknown"
    if hit.get("date_note"):
        date += f" ({hit['date_note']})"
    facts = [date, hit["kind"]] + [fact for fact in (hit["machine"], hit["seat"]) if fact]
    print("  ".join(facts))
    where = hit["path"] + (f":{hit['line']}" if hit["line"] else "")
    print(f"  {where}")
    for number, text in hit["before"]:
        print(f"    {number:>6}  {text}")
    if hit["line"]:
        print(f"  > {hit['line']:>6}  {hit['shown']}")
    else:
        print(f"    {hit['shown']}")
    for number, text in hit["after"]:
        print(f"    {number:>6}  {text}")


def argument_parser():
    parser = argparse.ArgumentParser(
        description="Search the log-store's walk files, cold-read-records, analyses, session dialogs "
                    "and the user's typed messages for one regular expression, newest first. "
                    "From the Mac it runs on ned-box over ssh.")
    parser.add_argument("pattern", metavar="PATTERN", help="a regular expression, matched case-insensitively")
    parser.add_argument("--kind", action="append", choices=KINDS, default=[],
                        help="search only this kind of record; repeat for several (default: all)")
    parser.add_argument("--seat", metavar="SUBSTRING", default="",
                        help="keep sessions whose project-key contains SUBSTRING; searches only "
                             "session-dialogs and user-messages")
    parser.add_argument("--machine", choices=MACHINES, default="",
                        help="keep one machine's sessions; searches only session-dialogs and user-messages")
    parser.add_argument("--since", type=iso_date, metavar="YYYY-MM-DD", help="leave out hits dated before this day (UTC)")
    parser.add_argument("--until", type=iso_date, metavar="YYYY-MM-DD", help="leave out hits dated after this day (UTC)")
    parser.add_argument("--context", type=int, default=1, metavar="N", help="lines shown either side of a hit (default 1)")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, metavar="N",
                        help=f"show at most N hits (default {DEFAULT_LIMIT})")
    parser.add_argument("--jobs", type=int, default=os.cpu_count() or 1, metavar="N",
                        help="read transcripts in N processes (default: one per core); 1 reads them in this one")
    parser.add_argument("--skip", type=int, default=0, metavar="N", help="pass over the newest N hits")
    parser.add_argument("--include-own-session", action="store_true",
                        help=f"also search the agent-session running this search, which ${OWN_SESSION_VARIABLE} "
                             f"names and which is left out by default")
    parser.add_argument("--own-session", metavar="SESSION_ID", default=None, help=argparse.SUPPRESS)
    return parser


def main(argv=None):
    arguments = sys.argv[1:] if argv is None else argv
    parsed = argument_parser().parse_args(arguments)
    root_override = os.environ.get(ROOT_OVERRIDE)
    root = Path(root_override) if root_override else DEFAULT_LOG_STORE_ROOT
    own_session = "" if parsed.include_own_session else (
        parsed.own_session if parsed.own_session is not None else os.environ.get(OWN_SESSION_VARIABLE, ""))
    if not root.is_dir():
        if this_machine() != NED_BOX_HOSTNAME:
            forwarded = list(arguments)
            if parsed.own_session is None and not parsed.include_own_session:
                # ned-box's copy cannot see this machine's environment.
                forwarded += ["--own-session", own_session]
            return run_on_ned_box_over_ssh(forwarded)
        print(f"FAILED: there is no log-store at {root} on {this_machine()}, so nothing was searched.\n"
              f"The log-store is on ned-box at {DEFAULT_LOG_STORE_ROOT}; run this program there.",
              file=sys.stderr)
        return EXIT_FAILED

    kinds = parsed.kind or KINDS
    if parsed.seat or parsed.machine:
        kinds = [kind for kind in kinds if kind in (SESSION_DIALOGS, USER_MESSAGES)]
    page_size = parsed.skip + parsed.limit if parsed.limit > 0 else 0
    file_failures, user_failures = [], []
    stopped_early = False
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as threads:
            file_search = threads.submit(
                lambda: dated_file_hits(
                    file_hits(root, kinds, parsed.pattern, max(0, parsed.context), file_failures),
                    root, parsed.seat, parsed.machine, parsed.since, parsed.until, file_failures,
                    own_session))
            transcript_search = (threads.submit(transcript_candidates, root, parsed.pattern, parsed.seat,
                                                parsed.machine, parsed.since, user_failures, own_session)
                                 if USER_MESSAGES in kinds else None)
            hits = file_search.result()
            candidates = transcript_search.result() if transcript_search else None
        if candidates:
            found, stopped_early = user_message_hits(
                root, candidates, parsed.pattern, parsed.since, parsed.until, parsed.jobs, page_size,
                [hit["date"] for hit in hits], user_failures)
            hits += found
    except RipgrepMissing as missing:
        print(f"FAILED: ripgrep ({missing}) is not installed on {this_machine()}, so nothing was searched.\n"
              f"Install it: sudo apt install ripgrep (on the Mac: brew install ripgrep).", file=sys.stderr)
        return EXIT_FAILED
    failures = file_failures + user_failures

    # Path and line break ties, so --skip pages through one fixed order.
    hits.sort(key=lambda hit: (hit["path"], hit["line"] or 0))
    hits.sort(key=lambda hit: hit["date"] or "", reverse=True)
    shown = hits[parsed.skip:parsed.skip + parsed.limit] if parsed.limit > 0 else hits[parsed.skip:]
    for hit in shown:
        print_hit(hit)
        print()
    searched = ", ".join(kinds) if kinds else "nothing: --seat and --machine leave no --kind given"
    if shown:
        last = parsed.skip + len(shown)
        if stopped_early:
            print(f"Hits {parsed.skip + 1}-{last}, newest first, of more than {last}: older transcripts "
                  f"were not read, since they could not change these hits. Searched: {searched}.")
            print(f"More: rerun with --skip {last}, or narrow with --since or --kind.")
        else:
            print(f"Hits {parsed.skip + 1}-{last} of {len(hits)}, newest first. Searched: {searched}.")
        if not stopped_early and last < len(hits):
            print(f"{len(hits) - last} more: rerun with --skip {last}, or narrow with --since or --kind.")
    else:
        print(f"No hits shown of {len(hits)}. Searched: {searched}.")
    if parsed.include_own_session:
        pass
    elif own_session:
        print(f"Left out this agent-session's own records, session {own_session}; "
              f"--include-own-session searches them too.")
    else:
        print(f"This agent-session could not be identified, since ${OWN_SESSION_VARIABLE} is not set, "
              f"so its own records, if any, are among the hits.")
    for failure in failures:
        print(f"FAILED: {failure}", file=sys.stderr)
    if failures:
        print(failures_closing_line(bool(shown)), file=sys.stderr)
        return EXIT_FAILED
    return EXIT_FOUND if hits else EXIT_NOTHING_FOUND


if __name__ == "__main__":
    sys.exit(main())
