#!/usr/bin/env python3
"""Search the log-store's records of past discussions for one pattern, newest first.

Usage:
  scripts/log-store-past-discussions-regex-search-newest-first.py PATTERN
      [--kind KIND]... [--seat SUBSTRING] [--machine {ned-box,mac}]
      [--since YYYY-MM-DD] [--until YYYY-MM-DD] [--context N] [--limit N] [--skip N]

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
the transcripts to read from their raw JSON, where a quote mark or a backslash
is escaped: a pattern holding either can miss a user's message, though not
the same words in the session dialogs.

WHAT EACH HIT SAYS. Its kind, date, machine and agent-seat where the record
shows them, its file and line, and the matching line with --context lines
either side (default 1); a user's message is shown as an excerpt around the
match. The date is the one in the file's name for walk, cold-read-records and
analysis, or the file's modification date when the name has none; the time
the user sent a message; and for a session dialog the session's last
activity, since a dialog's turns carry no time. A walk file's agent-seat is
the one its header says ran the approval-walk. A session's agent-seat is read
from its project-key, the transcript folder Claude Code names after the
session's directory.

FILTERS. --kind limits the search to the kinds named. --seat keeps sessions
whose project-key contains SUBSTRING, and --machine those of one machine;
either one searches only session-dialogs and user-messages, the two kinds
that record a session. --since and --until bound the hit's date, inclusive,
in UTC; a session dialog is kept when the session was active at any time in
the window. Hits come newest first; --limit (default 30) caps how many are
shown and --skip passes over the first N, so the closing line says how to see
the next ones.

FROM THE MAC. The whole log-store, the Mac's mirrored transcripts and session
dialogs included, is on ned-box. When the log-store is not on this machine
and this machine is not ned-box, the program runs ned-box's copy,
/home/nedlern/Projects/nedschorus/scripts/<this program>, over
`ssh nedlern@ned-box` with the same arguments. Reading eleven gigabytes of
transcripts through the Mac's mount /Volumes/nedhome/nedschorus-logs would
be slow, and ripgrep is not reliably on the Mac's PATH.

FAILURES. A record that could not be searched prints a line opening FAILED,
naming what failed and what to do, after the hits found elsewhere: a missing
log-store or kind directory, a file ripgrep could not read, a transcript the
reader could not read, ripgrep missing, ned-box unreachable from the Mac.

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
import datetime
import importlib.util
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


def session_start(transcript):
    """The first timestamp in a transcript, or "" when there is none or it cannot be read."""
    try:
        with transcript.open("rb") as handle:
            for line in handle:
                try:
                    stamp = json.loads(line).get("timestamp")
                except (ValueError, AttributeError):
                    continue
                if isinstance(stamp, str) and stamp:
                    return stamp
    except OSError:
        pass
    return ""


def walk_seat(path):
    try:
        with path.open(errors="replace") as handle:
            header = "".join(handle.readline() for _ in range(WALK_HEADER_LINES))
    except OSError:
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
            # ripgrep counts bytes; the excerpt only needs to land near the match.
            start = submatches[0]["start"] if submatches else 0
            matches.append((path, number, excerpt(text, start)))
    hits = []
    for path_text, number, shown in matches:
        path = Path(path_text)
        kind = path.relative_to(root).parts[0]
        nearby = lines_by_file[path_text]
        hit = {"kind": kind, "path": path_text, "line": number, "shown": shown,
               "before": [(n, nearby[n][:CONTEXT_CHARACTERS]) for n in range(number - context, number)
                          if n in nearby],
               "after": [(n, nearby[n][:CONTEXT_CHARACTERS]) for n in range(number + 1, number + context + 1)
                         if n in nearby],
               "machine": "", "seat": ""}
        if kind == SESSION_DIALOGS:
            hit["machine"], key = session_parts(path, root)
            hit["seat"] = seat_from_project_key(key)
            hit["project_key"] = key
        else:
            named = DATE_IN_NAME.search(str(path.relative_to(root / kind)))
            hit["date"] = named.group(0) if named else None
            if kind == "walk":
                hit["seat"] = walk_seat(path)
        hits.append(hit)
    return hits


def dated_file_hits(hits, root, seat, machine, since, until, failures):
    """Fill in each hit's date and drop those outside the filters."""
    kept = []
    modification_dates = {}
    starts = {}
    for hit in hits:
        path = Path(hit["path"])
        if hit["kind"] == SESSION_DIALOGS:
            if machine and hit["machine"] != machine:
                continue
            if seat and seat not in hit["project_key"]:
                continue
        if hit.get("date") is None:
            if hit["path"] not in modification_dates:
                try:
                    modification_dates[hit["path"]] = utc_iso(path.stat().st_mtime)
                except OSError as error:
                    failures.append(f"could not read the date of {path}: {error}")
                    modification_dates[hit["path"]] = ""
            hit["date"] = modification_dates[hit["path"]]
        if hit["kind"] == SESSION_DIALOGS:
            hit["date_note"] = "last activity"
            last = hit["date"][:10]
            if since and last and last < since:
                continue
            if until and last and last > until:
                if hit["path"] not in starts:
                    session_id = path.name[:-len(DIALOG_FILE_SUFFIX)]
                    transcript = (root / "transcripts" / hit["machine"] / "projects"
                                  / hit["project_key"] / f"{session_id}.jsonl")
                    starts[hit["path"]] = session_start(transcript)
                start = starts[hit["path"]][:10]
                if start and start > until:
                    continue
        elif not in_window(hit["date"], since, until):
            continue
        kept.append(hit)
    return kept


def user_message_hits(root, pattern, seat, machine, since, until, failures):
    """Hits among the user's typed messages in the mirrored transcripts."""
    try:
        regex = re.compile(pattern, re.IGNORECASE)
    except re.error as error:
        failures.append(f"the user's messages were not searched: Python's re module cannot read "
                        f"the pattern ({error}); give a pattern both ripgrep and Python read, "
                        f"or pass --kind to search the other kinds alone")
        return []
    directories = []
    for each in ([machine] if machine else MACHINES):
        directory = root / "transcripts" / each / "projects"
        if directory.is_dir():
            directories.append(directory)
        else:
            failures.append(f"the log-store has no {directory}, so {each}'s transcripts were not searched")
    if not directories:
        return []
    output = run_ripgrep(ripgrep_command(["--files-with-matches", "--max-depth", "2", "--glob", "*.jsonl"],
                                         pattern, directories), failures)
    extractor = None
    hits = []
    for line in sorted(output.splitlines()):
        path = Path(line)
        transcript_machine, key = session_parts(path, root)
        if seat and seat not in key:
            continue
        try:
            if since and utc_iso(path.stat().st_mtime)[:10] < since:
                continue
            if extractor is None:
                extractor = load_handoff_extractor()
            turns, _ = extractor.read_dialog_turns(path, drop_acknowledgements=False)
        except OSError as error:
            failures.append(f"could not read the transcript {path}: {error}")
            continue
        for turn in turns:
            if turn.get("voice") != "user":
                continue
            found = regex.search(turn["text"])
            if not found or not in_window(turn.get("timestamp", ""), since, until):
                continue
            flat = " ".join(turn["text"][:found.start()].split())
            whole = " ".join(turn["text"].split())
            hits.append({"kind": USER_MESSAGES, "path": str(path), "line": None,
                         "shown": "USER: " + excerpt(whole, len(flat)), "before": [], "after": [],
                         "date": turn.get("timestamp", ""), "machine": transcript_machine,
                         "seat": seat_from_project_key(key)})
    return hits


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
    parser.add_argument("--skip", type=int, default=0, metavar="N", help="pass over the newest N hits")
    return parser


def main(argv=None):
    arguments = sys.argv[1:] if argv is None else argv
    parsed = argument_parser().parse_args(arguments)
    root_override = os.environ.get(ROOT_OVERRIDE)
    root = Path(root_override) if root_override else DEFAULT_LOG_STORE_ROOT
    if not root.is_dir():
        if this_machine() != NED_BOX_HOSTNAME:
            return run_on_ned_box_over_ssh(arguments)
        print(f"FAILED: there is no log-store at {root} on {this_machine()}, so nothing was searched.\n"
              f"The log-store is on ned-box at {DEFAULT_LOG_STORE_ROOT}; run this program there.",
              file=sys.stderr)
        return EXIT_FAILED

    kinds = parsed.kind or KINDS
    if parsed.seat or parsed.machine:
        kinds = [kind for kind in kinds if kind in (SESSION_DIALOGS, USER_MESSAGES)]
    failures = []
    try:
        hits = dated_file_hits(file_hits(root, kinds, parsed.pattern, max(0, parsed.context), failures),
                               root, parsed.seat, parsed.machine, parsed.since, parsed.until, failures)
        if USER_MESSAGES in kinds:
            hits += user_message_hits(root, parsed.pattern, parsed.seat, parsed.machine,
                                      parsed.since, parsed.until, failures)
    except RipgrepMissing as missing:
        print(f"FAILED: ripgrep ({missing}) is not installed on {this_machine()}, so nothing was searched.\n"
              f"Install it: sudo apt install ripgrep (on the Mac: brew install ripgrep).", file=sys.stderr)
        return EXIT_FAILED

    hits.sort(key=lambda hit: hit["date"] or "", reverse=True)
    shown = hits[parsed.skip:parsed.skip + parsed.limit] if parsed.limit > 0 else hits[parsed.skip:]
    for hit in shown:
        print_hit(hit)
        print()
    searched = ", ".join(kinds) if kinds else "nothing: --seat and --machine leave no --kind given"
    if shown:
        last = parsed.skip + len(shown)
        print(f"Hits {parsed.skip + 1}-{last} of {len(hits)}, newest first. Searched: {searched}.")
        if last < len(hits):
            print(f"{len(hits) - last} more: rerun with --skip {last}, or narrow with --since or --kind.")
    else:
        print(f"No hits shown of {len(hits)}. Searched: {searched}.")
    for failure in failures:
        print(f"FAILED: {failure}", file=sys.stderr)
    if failures:
        return EXIT_FAILED
    return EXIT_FOUND if hits else EXIT_NOTHING_FOUND


if __name__ == "__main__":
    sys.exit(main())
