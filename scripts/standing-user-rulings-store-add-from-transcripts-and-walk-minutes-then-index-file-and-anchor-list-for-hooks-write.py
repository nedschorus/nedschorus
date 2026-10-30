#!/usr/bin/env python3
"""Add the user's new words and walk-minutes user-rulings to the standing user-rulings store, then write
the index file and the anchor list that hooks read.

Usage:
  scripts/standing-user-rulings-store-add-from-transcripts-and-walk-minutes-then-index-file-and-anchor-list-for-hooks-write.py
      [--log-store DIR] [--agents-directory DIR] [--repository-checkout DIR]

  --log-store            default /home/nedlern/nedschorus-logs, the log-store on ned-box
  --agents-directory     default /home/nedlern/agents, whose agent-seats' docs/walk/*-minutes.md are read
  --repository-checkout  default the checkout this file is in; its origin/main, as last fetched, resolves the
                         repository paths and GHI-MD paths that become tags and anchors. Nothing is fetched.

This is the index program of the ruling-agent design, docs/issues/2118-ruling-agent-keeps-user-rulings-
checks-approval-walk.md, part 1 of its build order. It runs on ned-box and writes three files in
<log-store>/user-rulings/:

  standing-user-rulings-decided-by-the-user-full-text-searchable.sqlite3  the store
  standing-user-rulings-hook-index-file.jsonl                              the index file
  standing-user-rulings-hook-anchor-list.txt                               the anchor list

WHAT IT READS.
- The transcripts that scripts/transcript-mirror-to-log-store.py mirrors into
  <log-store>/agent-session-files-by-machine/: mac/projects/*/*.jsonl, then ned-box/projects/*/*.jsonl,
  then recovered/*/*/*.jsonl (the Mac's transcripts recovered from Time Machine), in that order, so a
  message found in more than one copy links to the current mirror. Subagent transcripts are not read: their
  user turns are the parent agent's prompts. A user turn is his when
  scripts/search-user-messages-in-transcripts.py's TurnReader says so, queued_command attachments included.
  ned-box's own ~/.claude/projects is not read: the mirror copies it each minute, and one copy keeps one
  link per message.
- The walk-minutes: <agents-directory>/*/docs/walk/*-minutes.md, then <log-store>/walk/*-minutes.md, the
  copies scripts/walk-files-ship.py ships; <log-store>/walk/superseded/ is not read. A line is a user-ruling
  when it is the answer line that walk-me-through's check program writes for an approved or disapproved
  answer (ANSWER_LINE_WITH_TIME below; a deferred answer decides nothing), or when it holds the project's
  citation of a decision of his with its date (USER_RULED_CITATION below). The answer line's time is local
  time in WALK_MINUTES_LOCAL_TIME_ZONE and is stored as UTC; a citation's date is stored as written, a date
  alone or a UTC time.

WHAT IT STORES. One entry per message of his, kind user-words, with its UTC time, his text verbatim, the
text of the agent's messages since his previous message (the agent message he was answering), at most
AGENT_MESSAGE_ANSWERED_KEPT_CHARACTERS of its end, and its link, the transcript's path in the log-store and
the line number. One entry per walk-minutes user-ruling line, kind walk-minutes-user-ruling, linked to its
walk-minutes file and line. Every entry is added as standing; nothing is changed or deleted. Pairs are not
made: the design links two entries as a pair only when ruling-agent's prompt judges that they conflict, and
that prompt is part 2, so entry_pairs stays empty, ready, with its unreviewed state.

TAGS. From his own words: each GHI, pull request, task, system and repository file he names. From the
agent message he answered: each GHI, pull request, task and system it names; a file it names is tagged by
its system only. A system is nc-systems/<system>/; a file under .claude/skills/ is in nc-systems/skills/.
A file outside both has no system. A path is a repository file when its longest trailing part is a file on
origin/main, so a Mac, ned-box or worktree path resolves to the same file. A task is "task <agent-seat>
<number>", the agent-seat being the one named just before "task #N" (as "merge-lane-2's task #N"), else
the one whose agents/<agent-seat> directory the agent-session ran in. GHI and pull request numbers are
nedschorus's: a message from an agent-session whose directory is neither an agents/<agent-seat> directory
nor a nedschorus checkout, such as the old nedlern repository's, gets no tags. A walk-minutes line is
tagged from its own text, its agent-seat being the one whose directory holds the walk-minutes, or, for a
shipped copy, the agent-seat its name starts with.

NO DOUBLE-ADDS. An entry's duplicate_key is unique: a message of his is keyed by its time and text, so
the same message in a resumed agent-session, a recovered copy or a second read stores once; a walk-minutes
line is keyed by its file's name and text, so a live copy and its shipped copy store once. Each transcript
is read from where the last run stopped, the byte offset, line count and TurnReader state being kept in
source_files_read and committed with that file's entries; a file whose size and mtime are unchanged is not
opened. A transcript's last line is read only once it ends in a newline. A file that is smaller than the
offset, or is another file (another inode), is read again from its start, and the keys keep what it held
from being added twice.

THE INDEX FILE AND THE ANCHOR LIST, written from the store after every run. The index file is JSON Lines:
its first line {"index_built_at_utc": ..., "standing_entry_count": ...}; then one line per standing entry,
newest first, with its id ("entry-<number>", never reused), kind, said_at_utc, link, tags, anchors and
text, the text cut to its first INDEX_FILE_TEXT_WORDS words with "…" appended when cut (the full text is in
the store). The anchor list holds one anchor per line, sorted, every anchor of an entry in the index file.
An anchor is a literal string a hook finds in a tool's file path: "/<path>" for a tagged repository file,
"/nc-systems/<system>/" for a tagged system, and "/docs/issues/<number>-<words>.md" for a tagged GHI whose
GHI-MD is on origin/main; a GHI without one has no anchor, nor has a pull request or a task. The leading
"/" keeps "scripts/x.py" from matching "other-scripts/x.py". Each file is written beside itself and renamed
over the old one, so a reader sees a whole file; the index file is written first.

OUTPUT AND EXIT. One line on stdout: what was added, and the two files' entries, anchors and sizes. Each
failure prints a line on stderr starting FAILED. Exit 0 when nothing failed; 1 when a transcript or
walk-minutes file could not be read (the others are still added, and the next run tries it again) or the
index file or the anchor list could not be written (the store keeps what was added); 2 when it could not
run at all: the store cannot be opened, or origin/main cannot be read in the repository checkout, since
tags are fixed when an entry is added and would be lost; 3 when another run holds the lock, which is
expected when a run outlasts the minute between two runs.

WHAT IT DOES NOT HANDLE. A message of his that Claude Code recorded before it wrote an origin on user turns,
and that a program wrote, such as an early launch prompt, is stored as his words: TurnReader can tell such
turns only by their text. Words he typed only on the Mac reach the store once mirrored. A tag is only as
good as the name matched: a GHI named without "GHI", "issue" or a link, or a system named without its
path, is missed.
"""

import argparse
import datetime
import fcntl
import hashlib
import importlib.util
import json
import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
TRANSCRIPT_READER_FILE = HERE / "search-user-messages-in-transcripts.py"
GIT_ENVIRONMENT_FILE = (HERE.parent / "nc-systems" / "general-tools"
                        / "git-redirecting-environment-variables-removal-common.py")
RUN_AGAIN_COMMAND = f"python3 {Path(__file__).resolve()}"

DEFAULT_LOG_STORE = Path("/home/nedlern/nedschorus-logs")
DEFAULT_AGENTS_DIRECTORY = Path("/home/nedlern/agents")
STORE_DIRECTORY_NAME = "user-rulings"
STORE_FILE_NAME = "standing-user-rulings-decided-by-the-user-full-text-searchable.sqlite3"
INDEX_FILE_NAME = "standing-user-rulings-hook-index-file.jsonl"
ANCHOR_LIST_FILE_NAME = "standing-user-rulings-hook-anchor-list.txt"
LOCK_FILE_NAME = STORE_FILE_NAME + ".index-program.lock"
MIRROR_DIRECTORY_NAME = "agent-session-files-by-machine"
# Read in this order, so a message in more than one copy links to the current mirror.
TRANSCRIPT_GLOBS = (("mac", "mac/projects/*/*.jsonl"),
                    ("ned-box", "ned-box/projects/*/*.jsonl"),
                    ("recovered", "recovered/*/*/*.jsonl"))
SEAT_BRIEF_GLOB = "*/seat-briefs/*"
SHIPPED_WALK_DIRECTORY_NAME = "walk"
WALK_MINUTES_GLOB = "*-minutes.md"
LINK_HOST = "nedlern@ned-box"
WALK_MINUTES_LOCAL_TIME_ZONE = "America/Los_Angeles"
AGENT_MESSAGE_ANSWERED_KEPT_CHARACTERS = 8000
INDEX_FILE_TEXT_WORDS = 30
ADDED_BY = "standing-user-rulings index program"

KIND_USER_WORDS = "user-words"
KIND_WALK_MINUTES_USER_RULING = "walk-minutes-user-ruling"
STATE_STANDING = "standing"
EXIT_OK, EXIT_SOURCE_OR_OUTPUT_FAILED, EXIT_COULD_NOT_RUN, EXIT_LOCK_HELD = 0, 1, 2, 3

SCHEMA_VERSION = 1
SCHEMA = """
CREATE TABLE IF NOT EXISTS entries (
    entry_id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL CHECK (kind IN ('user-words', 'walk-minutes-user-ruling', 'approved-note')),
    state TEXT NOT NULL DEFAULT 'standing' CHECK (state IN ('standing', 'superseded', 'lapsed')),
    said_at_utc TEXT NOT NULL,
    text TEXT NOT NULL,
    agent_message_answered TEXT,
    source_machine TEXT,
    source_path TEXT NOT NULL,
    source_line INTEGER NOT NULL,
    agent_seat TEXT,
    session_id TEXT,
    superseded_by_entry_id INTEGER REFERENCES entries (entry_id),
    state_changed_at_utc TEXT,
    added_at_utc TEXT NOT NULL,
    added_by TEXT NOT NULL,
    duplicate_key TEXT NOT NULL UNIQUE
);
CREATE INDEX IF NOT EXISTS entries_by_state_and_time ON entries (state, said_at_utc);
CREATE TABLE IF NOT EXISTS entry_tags (
    entry_id INTEGER NOT NULL REFERENCES entries (entry_id),
    tag TEXT NOT NULL,
    tag_source TEXT NOT NULL CHECK (tag_source IN ('user-words', 'agent-message-answered', 'walk-minutes-line')),
    PRIMARY KEY (entry_id, tag)
);
CREATE INDEX IF NOT EXISTS entry_tags_by_tag ON entry_tags (tag);
CREATE TABLE IF NOT EXISTS entry_pairs (
    pair_id INTEGER PRIMARY KEY,
    first_entry_id INTEGER NOT NULL REFERENCES entries (entry_id),
    second_entry_id INTEGER NOT NULL REFERENCES entries (entry_id),
    state TEXT NOT NULL DEFAULT 'unreviewed'
        CHECK (state IN ('unreviewed', 'one-superseded', 'changed', 'all-stand')),
    linked_at_utc TEXT NOT NULL,
    linked_by TEXT NOT NULL,
    ruled_at_utc TEXT,
    CHECK (first_entry_id < second_entry_id),
    UNIQUE (first_entry_id, second_entry_id)
);
CREATE TABLE IF NOT EXISTS source_files_read (
    path TEXT PRIMARY KEY,
    device INTEGER NOT NULL,
    inode INTEGER NOT NULL,
    size_read INTEGER NOT NULL,
    mtime_ns INTEGER NOT NULL,
    lines_read INTEGER NOT NULL,
    reader_state TEXT NOT NULL,
    read_at_utc TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS index_program_runs (
    run_id INTEGER PRIMARY KEY,
    started_at_utc TEXT NOT NULL,
    finished_at_utc TEXT,
    user_words_added INTEGER,
    walk_minutes_user_rulings_added INTEGER,
    failures TEXT
);
CREATE VIRTUAL TABLE IF NOT EXISTS entries_full_text USING fts5 (
    text, agent_message_answered, content='entries', content_rowid='entry_id');
CREATE TRIGGER IF NOT EXISTS entries_full_text_after_insert AFTER INSERT ON entries BEGIN
    INSERT INTO entries_full_text (rowid, text, agent_message_answered)
    VALUES (new.entry_id, new.text, new.agent_message_answered);
END;
CREATE TRIGGER IF NOT EXISTS entries_full_text_after_text_update
AFTER UPDATE OF text, agent_message_answered ON entries BEGIN
    INSERT INTO entries_full_text (entries_full_text, rowid, text, agent_message_answered)
    VALUES ('delete', old.entry_id, old.text, old.agent_message_answered);
    INSERT INTO entries_full_text (rowid, text, agent_message_answered)
    VALUES (new.entry_id, new.text, new.agent_message_answered);
END;
"""

GHI_REFERENCE = re.compile(
    r"(?<![\w/#-])(?:GHIs?|issues?)\s*#?(\d{1,5})\b"
    r"|\bnedschorus#(\d{1,5})\b"
    r"|github\.com/nedschorus/nedschorus/issues/(\d{1,5})\b"
    r"|\bdocs/issues/(\d{1,5})-", re.IGNORECASE)
PULL_REQUEST_REFERENCE = re.compile(
    r"(?<![\w/#-])(?:PRs?|pull requests?)\s*#?(\d{1,5})\b"
    r"|github\.com/nedschorus/nedschorus/pull/(\d{1,5})\b", re.IGNORECASE)
TASK_REFERENCE = re.compile(r"(?:\b([a-z][a-z0-9-]*[a-z0-9])(?:'s|’s)\s+)?\btasks?\s+#(\d{1,5})\b",
                            re.IGNORECASE)
PATH_TOKEN = re.compile(r"[\w.~@-]*(?:/[\w.@-]+)+/?")
NEDSCHORUS_SESSION_DIRECTORY = re.compile(
    r"^/(?:home/nedlern|Users/el)/(?:agents/(?P<seat>[^/]+)|Projects/nedschorus)(?:/|$)")
AGENT_SEAT_DIRECTORY = re.compile(r"/agents/(?P<seat>[^/]+)/docs/walk/[^/]+$")
# The answer line walk-me-through's check program writes (its CHECK_MINUTES); "deferred" has no such line.
ANSWER_LINE_WITH_TIME = re.compile(
    r"^(?P<item>items? .+?): the user answered (?P<answered>.+?)(?: #approved_(?:obvious|after_advisor))? "
    r"\((?P<when>\d{4}-\d\d-\d\d \d\d:\d\d)\), which makes its change\. Fast reads:$", re.IGNORECASE)
USER_RULED_CITATION = re.compile(r"\buser-ruled (?P<date>\d{4}-\d\d-\d\d)(?P<time>T\d\d:\d\d(?::\d\d)?Z)?")

# Messages follow docs/nedschorus-wiki/nedschorus-how-to-write-an-agent-facing-message-such-as-a-hook-refusal-or-script-error.md.
FAILED_LINE = "FAILED: {what}: {error}"
OWNER_REPORT_INSTRUCTION = ("If it fails the same way at the next run, send prime-intellect, the agent-seat that owns "
                            "this program, the FAILED line above with SendMessage.")
SOURCE_FAILED_INSTRUCTIONS = (
    "The other transcripts and walk-minutes were read, and what they held was added; the file above is read "
    "again from where it stopped at the next run.",
    OWNER_REPORT_INSTRUCTION,
)
OUTPUT_FAILED_INSTRUCTIONS = (
    "The store keeps every entry this run added; hooks go on reading the last index file and anchor list "
    "written whole, since each is renamed into place only once written.",
    "If the error says the disk is full, free space on the log-store's disk first.",
    "Then run `" + RUN_AGAIN_COMMAND + "` once more; if it fails the same way again, send prime-intellect, the "
    "agent-seat that owns this program, the FAILED line above with SendMessage.",
)
REPOSITORY_UNREADABLE_INSTRUCTIONS = (
    "Nothing was added: tags are fixed when an entry is added, so no entry is added without origin/main's files.",
    "Run `git -C {checkout} fetch origin main`, then `" + RUN_AGAIN_COMMAND + "` again.",
    "If origin/main still cannot be read, run it again with --repository-checkout naming another nedschorus "
    "checkout on ned-box, such as /home/nedlern/Projects/nedschorus; if that fails too, send prime-intellect, "
    "the agent-seat that owns this program, the FAILED line above with SendMessage.",
)
STORE_UNOPENABLE_INSTRUCTIONS = (
    "Nothing was added.",
    "If the store's directory is missing or not writable, as when the log-store's disk is not mounted, send "
    "prime-intellect, the agent-seat that owns this program, the FAILED line above with SendMessage.",
    "If the store file itself is damaged, send prime-intellect, the agent-seat that owns this program, the FAILED "
    "line above with SendMessage, and do not delete, move or replace the store: no other copy of it exists.",
)
NEWER_STORE_INSTRUCTIONS = (
    "Nothing was added: this copy of the program is older than the store.",
    "Fetch origin/main into your checkout, merge it, and run your checkout's copy of this program again; if "
    "origin/main's copy is the same as this one, send prime-intellect, the agent-seat that owns this program, the "
    "FAILED line above with SendMessage.",
)
LOCK_HELD_LINE = ("standing-user-rulings index program: another run holds {lock}, so this run added nothing; "
                  "the next run reads what this one would have. No action is needed: the lock ends with the run that "
                  "holds it, even a run that is killed.")
SUMMARY_LINE = ("standing-user-rulings index program: added {user_words} user-words and {walk} "
                "walk-minutes-user-ruling entries; index file {index} holds {entries} standing entries "
                "({index_bytes} bytes); anchor list {anchors_path} holds {anchors} anchors ({anchor_bytes} bytes)")


def load_transcript_reader():
    spec = importlib.util.spec_from_file_location("search_user_messages_in_transcripts", TRANSCRIPT_READER_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


transcript_reader = load_transcript_reader()
_git_environment_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_variables_removal_common", GIT_ENVIRONMENT_FILE)
git_environment = importlib.util.module_from_spec(_git_environment_spec)
_git_environment_spec.loader.exec_module(git_environment)


class CouldNotRun(Exception):
    """The run cannot start, and nothing was added; args are the reason and the instruction lines."""

    def __init__(self, reason, instructions):
        super().__init__(reason)
        self.reason, self.instructions = reason, instructions


def utc_now_text():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def link_to(path, line_number):
    return f"{LINK_HOST}:{path} line {line_number}"


class Repository:
    """The files on origin/main that paths and GHI numbers resolve to."""

    def __init__(self, checkout):
        completed = subprocess.run(["git", "-C", str(checkout), "ls-tree", "-r", "--name-only", "origin/main"],
                                   capture_output=True, text=True, check=False,
                                   env=git_environment.environment_without_git_redirecting_variables())
        if completed.returncode:
            raise CouldNotRun(f"git ls-tree of origin/main in {checkout} failed: {completed.stderr.strip()}",
                              [line.format(checkout=checkout) for line in REPOSITORY_UNREADABLE_INSTRUCTIONS])
        self.files = set(completed.stdout.splitlines())
        self.ghi_md_paths = {}
        for path in self.files:
            match = re.fullmatch(r"docs/issues/(\d+)-[^/]+\.md", path)
            if match:
                self.ghi_md_paths.setdefault(int(match.group(1)), []).append(path)
        top_level = sorted((path for path in self.files if "/" not in path), key=len, reverse=True)
        self.top_level_file = (re.compile(r"(?<![\w/.-])(" + "|".join(re.escape(p) for p in top_level)
                                          + r")(?![\w-])") if top_level else None)

    def files_named(self, text):
        """The repository files a text names, each as its path on origin/main."""
        found = set()
        for token in PATH_TOKEN.findall(text):
            parts = [part for part in token.strip("/").split("/") if part]
            for start in range(len(parts)):
                candidate = "/".join(parts[start:])
                if candidate in self.files:
                    found.add(candidate)
                    break
        if self.top_level_file is not None:
            found.update(self.top_level_file.findall(text))
        return found

    def systems_named(self, text):
        """The systems a text names by a path: nc-systems/<system>/ directories."""
        systems = set()
        for token in PATH_TOKEN.findall(text):
            system = system_of_path(token)
            if system is not None:
                systems.add(system)
        return systems


def system_of_path(path):
    match = re.search(r"(?:^|/)nc-systems/([\w.-]+)(?:/|$)", path)
    if match:
        return f"nc-systems/{match.group(1)}/"
    if re.search(r"(?:^|/)\.claude/skills/[\w.-]+", path):
        return "nc-systems/skills/"
    return None


def numbers(pattern, text):
    return {int(next(group for group in match.groups() if group)) for match in pattern.finditer(text)}


def task_tags(text, default_seat, known_seats):
    tags = set()
    for match in TASK_REFERENCE.finditer(text):
        seat = match.group(1).lower() if match.group(1) and match.group(1).lower() in known_seats else default_seat
        if seat:
            tags.add(f"task {seat} {int(match.group(2))}")
    return tags


def tags_named_in(text, repository, default_seat, known_seats, files_are_tags):
    """The tags a text names: GHIs, pull requests, tasks, systems, and, when files_are_tags, files."""
    tags = {f"GHI {number}" for number in numbers(GHI_REFERENCE, text)}
    tags |= {f"PR {number}" for number in numbers(PULL_REQUEST_REFERENCE, text)}
    tags |= task_tags(text, default_seat, known_seats)
    tags |= repository.systems_named(text)
    for path in repository.files_named(text):
        system = system_of_path(path)
        if system is not None:
            tags.add(system)
        if files_are_tags:
            tags.add(path)
    return tags


def anchors_of(tags, repository):
    anchors = set()
    for tag in tags:
        if tag.startswith("GHI "):
            anchors.update("/" + path for path in repository.ghi_md_paths.get(int(tag.split(" ")[1]), ()))
        elif tag.startswith(("PR ", "task ")):
            continue
        else:
            anchors.add("/" + tag)
    return anchors


def open_store(store_path):
    try:
        connection = sqlite3.connect(str(store_path))
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        (version,) = connection.execute("PRAGMA user_version").fetchone()
        if version not in (0, SCHEMA_VERSION):
            raise CouldNotRun(f"the store {store_path} has schema version {version}, and this program "
                              f"knows version {SCHEMA_VERSION}", NEWER_STORE_INSTRUCTIONS)
        connection.executescript(SCHEMA)
        connection.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
        connection.commit()
    except (OSError, sqlite3.Error) as error:
        raise CouldNotRun(f"the store {store_path} cannot be opened: {error}",
                          STORE_UNOPENABLE_INSTRUCTIONS) from error
    return connection


def duplicate_key(*parts):
    return hashlib.sha256("\0".join(parts).encode()).hexdigest()


def add_entry(connection, entry, tags_by_source):
    """Insert one entry and its tags; return whether it was new."""
    cursor = connection.execute(
        "INSERT OR IGNORE INTO entries (kind, said_at_utc, text, agent_message_answered, source_machine, "
        "source_path, source_line, agent_seat, session_id, added_at_utc, added_by, duplicate_key) "
        "VALUES (:kind, :said_at_utc, :text, :agent_message_answered, :source_machine, :source_path, "
        ":source_line, :agent_seat, :session_id, :added_at_utc, :added_by, :duplicate_key)", entry)
    if not cursor.rowcount:
        return False
    tagged = set()
    for source, tags in tags_by_source:
        for tag in sorted(tags - tagged):
            connection.execute("INSERT INTO entry_tags (entry_id, tag, tag_source) VALUES (?, ?, ?)",
                               (cursor.lastrowid, tag, source))
        tagged |= tags
    return True


def previous_reading(connection, path):
    return connection.execute("SELECT device, inode, size_read, mtime_ns, lines_read, reader_state "
                              "FROM source_files_read WHERE path = ?", (str(path),)).fetchone()


def record_reading(connection, path, status, size_read, lines_read, reader_state):
    connection.execute(
        "INSERT INTO source_files_read (path, device, inode, size_read, mtime_ns, lines_read, reader_state, "
        "read_at_utc) VALUES (?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT (path) DO UPDATE SET device = excluded.device, "
        "inode = excluded.inode, size_read = excluded.size_read, mtime_ns = excluded.mtime_ns, "
        "lines_read = excluded.lines_read, reader_state = excluded.reader_state, read_at_utc = excluded.read_at_utc",
        (str(path), status.st_dev, status.st_ino, size_read, status.st_mtime_ns, lines_read,
         json.dumps(reader_state), utc_now_text()))


def session_context(cwd):
    """(whether the agent-session ran in a nedschorus checkout, its agent-seat or None)."""
    match = NEDSCHORUS_SESSION_DIRECTORY.match(cwd or "")
    if not match:
        return False, None
    return True, match.group("seat")


def read_transcript(connection, machine, path, repository, known_seats):
    """Add the new messages of his in one transcript; return how many were added."""
    status = path.stat()
    previous = previous_reading(connection, path)
    offset, line_number, state = 0, 0, {}
    if previous is not None:
        device, inode, size_read, mtime_ns, lines_read, reader_state = previous
        if (device, inode, size_read, mtime_ns) == (status.st_dev, status.st_ino, status.st_size,
                                                     status.st_mtime_ns):
            return 0
        if (device, inode) == (status.st_dev, status.st_ino) and status.st_size >= size_read:
            offset, line_number, state = size_read, lines_read, json.loads(reader_state)
    reader = transcript_reader.TurnReader(state.get("turn_reader"))
    agent_text = state.get("agent_message_since_user_message", "")
    cwd = state.get("cwd", "")
    added = 0
    with open(path, "rb") as handle:
        handle.seek(offset)
        for raw_line in iter(handle.readline, b""):
            if not raw_line.endswith(b"\n"):
                break
            offset += len(raw_line)
            line_number += 1
            try:
                record = json.loads(raw_line.decode("utf-8", errors="replace"))
            except json.JSONDecodeError:
                continue
            if not isinstance(record, dict):
                continue
            if isinstance(record.get("cwd"), str):
                cwd = record["cwd"]
            turn = reader.turn(record)
            if turn is None:
                continue
            speaker, text = turn
            if speaker == "agent":
                agent_text = (agent_text + "\n\n" + text if agent_text else text)[
                    -AGENT_MESSAGE_ANSWERED_KEPT_CHARACTERS:]
                continue
            in_nedschorus, seat = session_context(cwd)
            tags_by_source = []
            if in_nedschorus:
                tags_by_source = [
                    ("user-words", tags_named_in(text, repository, seat, known_seats, files_are_tags=True)),
                    ("agent-message-answered",
                     tags_named_in(agent_text, repository, seat, known_seats, files_are_tags=False)),
                ]
            stamp = record.get("timestamp") or ""
            entry = {
                "kind": KIND_USER_WORDS, "said_at_utc": stamp, "text": text,
                "agent_message_answered": agent_text or None, "source_machine": machine,
                "source_path": str(path), "source_line": line_number, "agent_seat": seat,
                "session_id": record.get("sessionId") or path.stem, "added_at_utc": utc_now_text(),
                "added_by": ADDED_BY,
                "duplicate_key": (duplicate_key(KIND_USER_WORDS, stamp, text) if stamp
                                  else duplicate_key(KIND_USER_WORDS, path.name, str(line_number), text)),
            }
            if add_entry(connection, entry, tags_by_source):
                added += 1
            agent_text = ""
    record_reading(connection, path, status, offset, line_number,
                   {"turn_reader": reader.state(), "agent_message_since_user_message": agent_text, "cwd": cwd})
    return added


def walk_minutes_said_at(line):
    match = ANSWER_LINE_WITH_TIME.match(line)
    if match:
        local = datetime.datetime.strptime(match.group("when"), "%Y-%m-%d %H:%M").replace(
            tzinfo=ZoneInfo(WALK_MINUTES_LOCAL_TIME_ZONE))
        return local.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    match = USER_RULED_CITATION.search(line)
    if match:
        return match.group("date") + (match.group("time") or "")
    return None


def walk_minutes_seat(path, known_seats):
    match = AGENT_SEAT_DIRECTORY.search(str(path))
    if match:
        return match.group("seat")
    starting = [seat for seat in known_seats if path.name.startswith(seat + "-")]
    return max(starting, key=len) if starting else None


def read_walk_minutes(connection, path, repository, known_seats):
    """Add the new user-ruling lines of one walk-minutes file; return how many were added."""
    status = path.stat()
    previous = previous_reading(connection, path)
    if previous is not None and tuple(previous[:4]) == (status.st_dev, status.st_ino, status.st_size,
                                                         status.st_mtime_ns):
        return 0
    seat = walk_minutes_seat(path, known_seats)
    added, line_count = 0, 0
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        for line_count, line in enumerate(handle, start=1):
            line = line.strip()
            said_at = walk_minutes_said_at(line)
            if said_at is None:
                continue
            entry = {
                "kind": KIND_WALK_MINUTES_USER_RULING, "said_at_utc": said_at,
                "text": line, "agent_message_answered": None, "source_machine": "ned-box",
                "source_path": str(path), "source_line": line_count, "agent_seat": seat, "session_id": None,
                "added_at_utc": utc_now_text(), "added_by": ADDED_BY,
                "duplicate_key": duplicate_key(KIND_WALK_MINUTES_USER_RULING, path.name, line),
            }
            tags = tags_named_in(line, repository, seat, known_seats, files_are_tags=True)
            if add_entry(connection, entry, [("walk-minutes-line", tags)]):
                added += 1
    record_reading(connection, path, status, status.st_size, line_count, {})
    return added


def known_agent_seats(agents_directory, mirror_directory):
    seats = {path.name.lower() for path in agents_directory.glob("*") if path.is_dir()}
    seats |= {path.name.lower() for path in mirror_directory.glob(SEAT_BRIEF_GLOB) if path.is_dir()}
    return seats


def index_lines(connection, repository, built_at):
    tags_by_entry = {}
    for entry_id, tag in connection.execute(
            "SELECT entry_tags.entry_id, tag FROM entry_tags JOIN entries USING (entry_id) WHERE state = ?",
            (STATE_STANDING,)):
        tags_by_entry.setdefault(entry_id, []).append(tag)
    rows = connection.execute(
        "SELECT entry_id, kind, said_at_utc, text, source_path, source_line FROM entries WHERE state = ? "
        "ORDER BY said_at_utc DESC, entry_id DESC", (STATE_STANDING,)).fetchall()
    lines = [json.dumps({"index_built_at_utc": built_at, "standing_entry_count": len(rows)})]
    all_anchors = set()
    for entry_id, kind, said_at, text, source_path, source_line in rows:
        tags = sorted(tags_by_entry.get(entry_id, ()))
        anchors = sorted(anchors_of(tags, repository))
        all_anchors.update(anchors)
        words = text.split()
        shown = " ".join(words[:INDEX_FILE_TEXT_WORDS]) + (" …" if len(words) > INDEX_FILE_TEXT_WORDS else "")
        lines.append(json.dumps({"id": f"entry-{entry_id}", "kind": kind, "said_at_utc": said_at,
                                 "link": link_to(source_path, source_line), "tags": tags, "anchors": anchors,
                                 "text": shown}, ensure_ascii=False))
    return lines, sorted(all_anchors)


def write_whole(path, lines):
    """Write the lines beside the file, then rename over it; return the size written."""
    partial = path.with_name(path.name + ".partial")
    partial.write_text("".join(line + "\n" for line in lines), encoding="utf-8")
    os.replace(partial, path)
    return path.stat().st_size


def run(log_store, agents_directory, repository_checkout):
    store_directory = log_store / STORE_DIRECTORY_NAME
    try:
        store_directory.mkdir(parents=True, exist_ok=True)
        lock_handle = open(store_directory / LOCK_FILE_NAME, "w")
    except OSError as error:
        print(FAILED_LINE.format(what=f"the store directory {store_directory}", error=error), file=sys.stderr)
        print("\n".join(STORE_UNOPENABLE_INSTRUCTIONS), file=sys.stderr)
        return EXIT_COULD_NOT_RUN
    try:
        fcntl.flock(lock_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print(LOCK_HELD_LINE.format(lock=store_directory / LOCK_FILE_NAME))
        return EXIT_LOCK_HELD
    try:
        repository = Repository(repository_checkout)
        connection = open_store(store_directory / STORE_FILE_NAME)
    except CouldNotRun as error:
        print(FAILED_LINE.format(what="this run", error=error.reason), file=sys.stderr)
        print("\n".join(error.instructions), file=sys.stderr)
        return EXIT_COULD_NOT_RUN
    started = utc_now_text()
    mirror_directory = log_store / MIRROR_DIRECTORY_NAME
    known_seats = known_agent_seats(agents_directory, mirror_directory)
    source_failures, output_failures = [], []
    user_words_added = walk_added = 0
    for machine, pattern in TRANSCRIPT_GLOBS:
        for path in sorted(mirror_directory.glob(pattern)):
            try:
                with connection:
                    user_words_added += read_transcript(connection, machine, path, repository, known_seats)
            except (OSError, sqlite3.Error) as error:
                source_failures.append(FAILED_LINE.format(what=f"transcript {path}", error=error))
    minutes_paths = (sorted(agents_directory.glob(f"*/docs/walk/{WALK_MINUTES_GLOB}"))
                     + sorted((log_store / SHIPPED_WALK_DIRECTORY_NAME).glob(WALK_MINUTES_GLOB)))
    for path in minutes_paths:
        try:
            with connection:
                walk_added += read_walk_minutes(connection, path, repository, known_seats)
        except (OSError, sqlite3.Error) as error:
            source_failures.append(FAILED_LINE.format(what=f"walk-minutes {path}", error=error))
    built_at = utc_now_text()
    lines, anchors = index_lines(connection, repository, built_at)
    index_path, anchor_path = store_directory / INDEX_FILE_NAME, store_directory / ANCHOR_LIST_FILE_NAME
    index_bytes = anchor_bytes = "not written"
    try:
        index_bytes = write_whole(index_path, lines)
        anchor_bytes = write_whole(anchor_path, anchors)
    except OSError as error:
        output_failures.append(FAILED_LINE.format(what="the index file or the anchor list", error=error))
    failures = source_failures + output_failures
    with connection:
        connection.execute("INSERT INTO index_program_runs (started_at_utc, finished_at_utc, user_words_added, "
                           "walk_minutes_user_rulings_added, failures) VALUES (?, ?, ?, ?, ?)",
                           (started, utc_now_text(), user_words_added, walk_added, "\n".join(failures) or None))
    connection.close()
    for line in source_failures:
        print(line, file=sys.stderr)
    if source_failures:
        print("\n".join(SOURCE_FAILED_INSTRUCTIONS), file=sys.stderr)
    for line in output_failures:
        print(line, file=sys.stderr)
    if output_failures:
        print("\n".join(OUTPUT_FAILED_INSTRUCTIONS), file=sys.stderr)
    print(SUMMARY_LINE.format(user_words=user_words_added, walk=walk_added, index=index_path,
                              entries=len(lines) - 1, index_bytes=index_bytes, anchors_path=anchor_path,
                              anchors=len(anchors), anchor_bytes=anchor_bytes))
    return EXIT_SOURCE_OR_OUTPUT_FAILED if failures else EXIT_OK


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--log-store", type=Path, default=DEFAULT_LOG_STORE)
    parser.add_argument("--agents-directory", type=Path, default=DEFAULT_AGENTS_DIRECTORY)
    parser.add_argument("--repository-checkout", type=Path, default=HERE.parent)
    arguments = parser.parse_args(argv)
    return run(arguments.log_store, arguments.agents_directory, arguments.repository_checkout)


if __name__ == "__main__":
    sys.exit(main())
