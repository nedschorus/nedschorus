#!/usr/bin/env python3
"""Stop hook: tell the agent to give a cold-read-fast-read to each Markdown
document its last reply linked for the user that has had none since the
document's last change. It never asks for a cold-read-full-run.

Wired as a Stop hook in .claude/settings.json.

WHAT COUNTS AS A LINKED DOCUMENT: in the last reply of the turn (read as
scripts/absence-claim-locator-reminder-hook.py reads it), a path ending .md
that is a file:// link, an absolute path under /home/ or /Volumes/, or a path
starting docs/, nc-systems/ or .claude/, which is resolved against the
payload's cwd and then the top of that cwd's checkout. /Volumes/nedhome/<path>,
the Mac's mount of ned-box, maps to /home/nedlern/<path> when that file exists.
Skipped: files that do not exist, anything in the log-store or in a
cold-read-records directory, and docs/walk/<name>-suggestions.md, which is a
fast read's own report.

WHEN A DOCUMENT IS DUE. A document is not due when a fast read of its
current text is on record. A walk-document named docs/walk/<name>-draft.md
fast-read from its own checkout writes docs/walk/<name>-suggestions.md beside
it, so a suggestions file newer than the walk-document counts as that read;
read from another checkout, it gets a cold-read-record like any document.
Records are the directories in the log-store's cold-read-records/ and in a
cold-read-records/ at the top of the document's checkout or the session's
checkout whose names match the document by
nc-systems/cold-read/cold-read-record-names.py, and that hold a finished
report there; a read that failed after freezing its target leaves no report
and does not count. The record-name, frozen-path and finished-report rules
are all taken from that module. A record holding a frozen copy under target/
belongs to the document only when the copy sits at the document's path,
relative to its checkout or absolute without the leading slash, the form a
fast read run from another checkout writes; a record without target/ is
matched by name alone. The document is not due when a record's frozen copy
has the document's bytes, whatever the file times say: a checkout or a pull
stamps a file with the time of the checkout, so file times alone would call
every document in a new worktree due. Otherwise the document is due when its
modification time is later than the newest file time in its newest record;
the shipper copies with rsync -a, which keeps file times, so a stored record
carries the time of the read. git runs without the variables that redirect
it, which scripts/run-all-test-suites.py lists, so a leaked GIT_DIR cannot
name the wrong checkout.

SILENT when nothing is due, when stop_hook_active is set (the agent is
already continuing because of a Stop hook), when the agent-session is a
headless `claude -p` child (its last words are its caller's answer), when the
transcript file does not exist, and when the log-store's cold-read-records
directory does not exist, as on the Mac, because without it every document
would look due. NEDSCHORUS_LOG_STORE_COLD_READ_RECORDS_DIRECTORY overrides
that directory; the log-store is its parent directory.

OUTPUT: {"hookSpecificOutput": {"hookEventName": "Stop", "additionalContext": ...}},
which continues the conversation with the text as the agent's next input.
ON A FAULT, such as input that is not JSON, a module that will not load, or
a record directory it cannot read,
the hook prints one line naming it on stderr and exits 1: Claude Code records
a Stop hook's exit 1 as a non-blocking error and still ends the turn.
"""
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote

LOG_STORE_DIRECTORY = Path("/home/nedlern/nedschorus-logs")
LOG_STORE_COLD_READ_RECORDS_ENVIRONMENT_VARIABLE = "NEDSCHORUS_LOG_STORE_COLD_READ_RECORDS_DIRECTORY"
MAC_MOUNT_OF_NED_BOX_HOME = "/Volumes/nedhome/"
NED_BOX_HOME = "/home/nedlern/"
WALK_DIRECTORY_PARTS = ("docs", "walk")
WALK_DRAFT_SUFFIX = "-draft.md"
WALK_SUGGESTIONS_SUFFIX = "-suggestions.md"
GIT_TIMEOUT_SECONDS = 5
FAST_READ_PROGRAM = "nc-systems/cold-read/cold-read-fast-read.py"

TRANSCRIPT_READER_FILE = Path(__file__).with_name("absence-claim-locator-reminder-hook.py")
SUITE_RUNNER_FILE = Path(__file__).with_name("run-all-test-suites.py")
REPOSITORY_TOP = Path(__file__).resolve().parent.parent

PATH_END = r"[^\s)\]>\"'`<|*]*?\.md(?![\w-])"
FILE_URL_PATTERN = re.compile(r"file://(/" + PATH_END + ")")
ABSOLUTE_PATH_PATTERN = re.compile(r"(?<![\w/.:~-])(/(?:home|Volumes)/" + PATH_END + ")")
RELATIVE_PATH_PATTERN = re.compile(
    r"(?<![\w/.:~-])((?:docs|nc-systems|\.claude)/" + PATH_END + ")")

REMINDER_OPENING = (
    "cold-read-fast-read due: your last reply linked these documents for the "
    "user, and none of them has had a cold-read-fast-read since the "
    "document's last change:")
REMINDER_INSTRUCTIONS = (
    "Run on each document, from your checkout: python3 " + FAST_READ_PROGRAM
    + " --target <document path>",
    "Apply to the document each finding of the fast read that holds.",
    "If you changed a document, tell the user which document changed and what changed.",
    "Do not start a cold-read-full-run for these documents; only the fast read is asked for.",
)


def load_module(name, path):
    specification = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def load_cold_read_record_names():
    """Loaded by run() rather than at import, so a fault loading it is reported by main."""
    specification = importlib.util.spec_from_file_location(
        "cold_read_record_names",
        REPOSITORY_TOP / "nc-systems" / "cold-read" / "cold-read-record-names.py")
    record_names = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(record_names)
    return record_names


def environment_without_git_redirection():
    runner = load_module("run_all_test_suites", SUITE_RUNNER_FILE)
    return {name: value for name, value in os.environ.items()
            if name not in runner.GIT_REDIRECTING_ENVIRONMENT_VARIABLES}


def last_reply_text(transcript_path):
    """Read the turn's last reply with the absence-claim hook's reader."""
    reader = load_module("absence_claim_locator_reminder_hook", TRANSCRIPT_READER_FILE)
    reply, _ = reader.read_turn(transcript_path)
    return reply


def checkout_top(directory, git_environment):
    try:
        completed = subprocess.run(
            ["git", "-C", str(directory), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=GIT_TIMEOUT_SECONDS,
            env=git_environment)
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0 or not completed.stdout.strip():
        return None
    return Path(completed.stdout.strip()).resolve()


def find_markdown_file_paths_linked_or_named_in_agent_reply(
        reply, cwd, git_environment=None, skipped=lambda path: False):
    """Return the existing Markdown files the reply links, resolved, in order."""
    candidates = []
    for match in FILE_URL_PATTERN.finditer(reply):
        candidates.append(unquote(match[1]))
    for match in ABSOLUTE_PATH_PATTERN.finditer(reply):
        candidates.append(match[1])
    relative_bases = [base for base in
                      (cwd, checkout_top(cwd, git_environment) if cwd else None) if base]
    found = []
    for raw in candidates:
        path = Path(raw)
        if raw.startswith(MAC_MOUNT_OF_NED_BOX_HOME):
            mapped = Path(NED_BOX_HOME + raw[len(MAC_MOUNT_OF_NED_BOX_HOME):])
            if mapped.is_file():
                path = mapped
        found.append(path)
    for match in RELATIVE_PATH_PATTERN.finditer(reply):
        for base in relative_bases:
            path = Path(base) / match[1]
            if path.is_file():
                found.append(path)
                break
    documents = []
    for path in found:
        if not path.is_file():
            continue
        path = path.resolve()
        if path in documents or skipped(path):
            continue
        documents.append(path)
    return documents


def is_skipped(path, log_store_directory, record_names):
    if log_store_directory in path.parents:
        return True
    if record_names.RECORDS_DIRECTORY_NAME in path.parts[:-1]:
        return True
    return (path.parent.parts[-2:] == WALK_DIRECTORY_PARTS
            and path.name.endswith(WALK_SUGGESTIONS_SUFFIX))


def newest_file_time(directory):
    newest = None
    for root, _, files in os.walk(directory):
        for name in files:
            try:
                modified = os.stat(os.path.join(root, name)).st_mtime
            except OSError:
                continue
            if newest is None or modified > newest:
                newest = modified
    return newest


def walk_draft_suggestions_path(document):
    if (document.parent.parts[-2:] == WALK_DIRECTORY_PARTS
            and document.name.endswith(WALK_DRAFT_SUFFIX)
            and len(document.name) > len(WALK_DRAFT_SUFFIX)):
        name = document.name[:-len(WALK_DRAFT_SUFFIX)]
        return document.parent / f"{name}{WALK_SUGGESTIONS_SUFFIX}"
    return None


def document_is_due(document, record_directories, document_top, record_names):
    suggestions = walk_draft_suggestions_path(document)
    if (suggestions is not None and suggestions.is_file()
            and suggestions.stat().st_mtime >= document.stat().st_mtime):
        return False
    pattern = record_names.record_directory_name_pattern_for_target(document)
    current_bytes = document.read_bytes()
    newest_record_time = None
    for directory in record_directories:
        try:
            entries = list(directory.iterdir())
        except OSError:
            continue
        for record in entries:
            if (not pattern.match(record.name) or not record.is_dir()
                    or not record_names.record_holds_completed_report(record)):
                continue
            if (record / record_names.FROZEN_TARGET_DIRECTORY_NAME).is_dir():
                frozen = next((candidate for candidate in
                               record_names.frozen_target_candidate_paths(
                                   document, record, document_top)
                               if candidate.is_file()), None)
                if frozen is None:
                    continue
                try:
                    if frozen.read_bytes() == current_bytes:
                        return False
                except OSError:
                    pass
            record_time = newest_file_time(record)
            if record_time is not None and (newest_record_time is None
                                            or record_time > newest_record_time):
                newest_record_time = record_time
    if newest_record_time is None:
        return True
    return document.stat().st_mtime > newest_record_time


def run(stdin_text, environment):
    """Return the text to print, or None."""
    payload = json.loads(stdin_text)
    if payload.get("stop_hook_active"):
        return None
    if (environment.get("NEDSCHORUS_SESSION_REINCARNATION_OWNED_BY_CALLER")
            or environment.get("CLAUDE_CODE_SESSION_ATTENDED") == "0"):
        return None
    transcript_path = payload.get("transcript_path")
    if not transcript_path or not Path(transcript_path).expanduser().is_file():
        return None
    record_names = load_cold_read_record_names()
    store = Path(environment.get(LOG_STORE_COLD_READ_RECORDS_ENVIRONMENT_VARIABLE)
                 or LOG_STORE_DIRECTORY / record_names.RECORDS_DIRECTORY_NAME)
    if not store.is_dir():
        return None
    log_store_directory = store.resolve().parent
    reply = last_reply_text(Path(transcript_path).expanduser())
    if not reply:
        return None
    git_environment = environment_without_git_redirection()
    cwd = Path(payload["cwd"]) if payload.get("cwd") else None
    session_top = checkout_top(cwd, git_environment) if cwd else None
    due = []
    documents = find_markdown_file_paths_linked_or_named_in_agent_reply(
        reply, cwd, git_environment,
        lambda path: is_skipped(path, log_store_directory, record_names))
    for document in documents:
        document_top = checkout_top(document.parent, git_environment)
        stores = [store]
        for top in (document_top, session_top):
            if top is not None and top / record_names.RECORDS_DIRECTORY_NAME not in stores:
                stores.append(top / record_names.RECORDS_DIRECTORY_NAME)
        if document_is_due(document, stores, document_top, record_names):
            due.append(document)
    if not due:
        return None
    lines = [REMINDER_OPENING] + [f"  {document}" for document in due]
    lines += list(REMINDER_INSTRUCTIONS)
    return json.dumps({"hookSpecificOutput": {
        "hookEventName": "Stop",
        "additionalContext": "\n".join(lines),
    }}, ensure_ascii=False)


def main():
    try:
        output = run(sys.stdin.read(), os.environ)
    except Exception as error:
        print(f"cold-read-fast-read-due-for-linked-document-reminder-hook: the hook failed, "
              f"so it made no check of the documents the reply linked; the agent need not act: "
              f"{error!r}", file=sys.stderr)
        return 1
    if output is not None:
        print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
