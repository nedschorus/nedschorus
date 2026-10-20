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

WHEN A DOCUMENT IS DUE. A document in a git checkout is due only when that
checkout changed it from main: the document is not in the merge-base of the
checkout's HEAD and refs/remotes/origin/main, as with a new file or a
git-ignored walk-document, or its bytes differ from the copy there, through
an uncommitted edit or a commit on the topic branch. The merge-base, not
origin/main's tip, because a checkout behind main would otherwise be asked
about every document main changed since. A document the checkout left alone
is never due, whatever its records, because an agent should fast-read only
what it can still change. The checkout that holds the document decides, not
the payload's cwd: an agent-seat's cwd is its seat checkout, while the
documents it changes sit in its topic branch's worktree. The ref is used as it
stands, without a fetch. When that checkout has no origin/main, or git fails,
is killed or outlasts its time limit while comparing, or cannot run or
outlasts its time limit while finding the document's checkout, or fails there
for any reason but the directory being in no repository, the hook cannot
tell whether the document changed: it treats the document as changed, so the
record test below decides whether it is due, and lists it under its own
heading with git's reason whether or not it is due, marked as read when it is
not, so the agent sees git's failure on every Stop; it says so on stderr too,
and goes on with the other documents. A failed merge-base, a timeout
included, is found once per checkout per run. A document in no git
checkout skips this test. When git fails in the same ways while finding the
top of the payload cwd's checkout, the hook says so on
stderr and at the top of its additionalContext on every Stop that reaches
the check, and goes on without that top.
A document that passes it is not due when a fast read of its
current text is on record. A walk-document named docs/walk/<name>-draft.md
in any git worktree, fast-read from that checkout or another, writes
docs/walk/<name>-suggestions.md beside it, so a suggestions file newer than
the walk-document counts as that read; only a draft in no git worktree gets a
cold-read-record like any document.
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

ONCE PER AGENT-SESSION FOR ITS OWN READS. A document this agent-session
fast-read is not due again in this agent-session, whatever the document's own
time: applying a fast read's findings changes the document, which would
otherwise make it due again every time the agent linked it. A read is this
agent-session's own when the file a finished fast read writes beside its
report (nc-systems/cold-read/cold-read-record-names.py,
cold_read_fast_read_report_agent_session_id_file_path) names the payload's session_id and the
document's resolved path. The fast read takes the ID from
CLAUDE_CODE_SESSION_ID, which a subagent's Bash shares with its parent, so a
fast read a subagent runs counts as its parent agent-session's own. A record
without that file, as older reads and reads run without the variable leave,
or naming another agent-session, counts only by the file-time rule above, so
this agent-session is reminded about its own later change to a document
someone else read. The hook keeps no list of its own: a reminder the agent
ignores comes back, because no read ran. When the transcript cannot be read,
the hook checks nothing and tells the agent so, in additionalContext and on
stderr.

SILENT when nothing is due, when this Stop ends the agent's answer to a Stop
hook's output (the shared rule of
nc-systems/general-tools/claude-code-stop-hooks-stay-silent-while-agent-answers-a-stop-hook-rule-common.py), when the agent-session is a
headless `claude -p` child (its last words are its caller's answer), when the
transcript file does not exist, and when the log-store's cold-read-records
directory does not exist, as on the Mac, because without it every document
would look due. NEDSCHORUS_LOG_STORE_COLD_READ_RECORDS_DIRECTORY overrides
that directory; the log-store is its parent directory.

OUTPUT: {"hookSpecificOutput": {"hookEventName": "Stop", "additionalContext": ...}},
which continues the conversation with the text as the agent's next input.
ON A FAULT, such as input that is not JSON, a module that will not load, or a
record directory it cannot read, the hook prints one line on stderr naming the
fault and, where there is one, the path that failed, and exits 1: Claude Code records
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



def one_line_reason(error):
    # str, not repr: an OSError's repr drops the file name its str carries.
    return " ".join(f"{type(error).__name__}: {error}".split())


def fault_exit(error):
    print(f"cold-read-fast-read-due-for-linked-document-reminder-hook: the hook failed, "
          f"so it made no check of the documents the reply linked; the agent need not act: "
          f"{one_line_reason(error)}", file=sys.stderr)
    return 1


class ModuleLoadFailure(Exception):
    """A module this hook loads by path would not load; the message names the path."""


def load_module(name, path):
    try:
        specification = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(module)
    except Exception as error:
        # An exception raised inside the module names neither the module nor its path.
        raise ModuleLoadFailure(f"could not load {path}: {one_line_reason(error)}") from error
    return module


# Not resolved, so a fault names a module under the directory the hook was run
# from, as the agent and the user know it, not under a symlink's target.
REPOSITORY_TOP = Path(__file__).absolute().parent.parent


def _load_general_tools_module(file_name):
    return load_module(file_name.removesuffix(".py").replace("-", "_"),
                       REPOSITORY_TOP / "nc-systems" / "general-tools" / file_name)


# Constants below are built from these modules, so a load that fails ends the
# hook here, reported the way main() reports any other fault.
try:
    # Every Stop hook obeys this rule first: see the module's docstring.
    stop_hooks_stay_silent_rule = _load_general_tools_module(
        "claude-code-stop-hooks-stay-silent-while-agent-answers-a-stop-hook-rule-common.py")
    ned_box_home_path_constants = _load_general_tools_module(
        "ned-box-home-directory-and-its-mac-mount-point-path-constants-common.py")
    git_runner = _load_general_tools_module(
        "git-machine-readable-output-runner-and-parser-common.py")
except Exception as error:
    sys.exit(fault_exit(error))

LOG_STORE_DIRECTORY = Path(ned_box_home_path_constants.NED_BOX_HOME) / "nedschorus-logs"
LOG_STORE_COLD_READ_RECORDS_ENVIRONMENT_VARIABLE = "NEDSCHORUS_LOG_STORE_COLD_READ_RECORDS_DIRECTORY"
MAC_MOUNT_OF_NED_BOX_HOME = ned_box_home_path_constants.MAC_MOUNT_OF_NED_BOX_HOME + "/"
NED_BOX_HOME = ned_box_home_path_constants.NED_BOX_HOME + "/"
WALK_DIRECTORY_PARTS = ("docs", "walk")
WALK_DRAFT_SUFFIX = "-draft.md"
WALK_SUGGESTIONS_SUFFIX = "-suggestions.md"
GIT_TIMEOUT_SECONDS = 5
MAIN_REFERENCE = "refs/remotes/origin/main"
FAST_READ_PROGRAM = "nc-systems/cold-read/cold-read-fast-read.py"
TRANSCRIPT_UNREADABLE_LINES = (
    "cold-read-fast-read due check skipped: this hook could not read this "
    "agent-session's transcript ({reason}), so it did not check the documents "
    "your last reply linked.",
    "If your last reply linked a document you changed since its last "
    "cold-read-fast-read, run on it, from your checkout: python3 " + FAST_READ_PROGRAM
    + " --target <document path>",
)

TRANSCRIPT_READER_FILE = Path(__file__).with_name("absence-claim-locator-reminder-hook.py")
SUITE_RUNNER_FILE = Path(__file__).with_name("run-all-test-suites.py")

PATH_END = r"[^\s)\]>\"'`<|*]*?\.md(?![\w-])"
FILE_URL_PATTERN = re.compile(r"file://(/" + PATH_END + ")")
ABSOLUTE_PATH_PATTERN = re.compile(r"(?<![\w/.:~-])(/(?:home|Volumes)/" + PATH_END + ")")
RELATIVE_PATH_PATTERN = re.compile(
    r"(?<![\w/.:~-])((?:docs|nc-systems|\.claude)/" + PATH_END + ")")

REMINDER_OPENING = (
    "cold-read-fast-read due: your last reply linked these documents for the "
    "user, and none of them has had a cold-read-fast-read since the document's "
    "last change. Each is either outside any git checkout, or new or changed in "
    "the git checkout that holds it, compared with the commit where that "
    "checkout's branch left origin/main:")
UNCHECKED_OPENING = (
    "cold-read-fast-read due check failed for these documents: git could not "
    "find the git checkout that holds each, or could not compare it with "
    "origin/main there, so this hook cannot tell whether that checkout changed it:")
UNCHECKED_INSTRUCTION = (
    "If you changed a document in this list that is not marked as read since that "
    "document's last cold-read-fast-read, or cannot tell whether you changed it, run on "
    "it, from your checkout: "
    "python3 " + FAST_READ_PROGRAM + " --target <document path>")
UNCHECKED_ALREADY_READ_NOTICE = (
    " (marked as read: it has had a cold-read-fast-read since its last change, "
    "or this agent-session has given it one, so it needs none now)")
UNCHECKED_STDERR_LINE = (
    "cold-read-fast-read-due-for-linked-document-reminder-hook: could not tell "
    "whether the git checkout that holds {document} changed it, because git could not "
    "find that checkout or compare the document with origin/main: {reason}")
SESSION_CHECKOUT_UNKNOWN_STDERR_LINE = (
    "cold-read-fast-read-due-for-linked-document-reminder-hook: could not find the top "
    "of the git checkout holding {cwd}: {reason}")
SESSION_CHECKOUT_UNKNOWN_LINES = (
    "cold-read-fast-read due check incomplete: git could not find the top of the git "
    "checkout holding your working directory {cwd} ({reason}), so this hook did not look "
    "for document paths relative to that top, nor for records in the cold-read-records "
    "directory at that top.",
    "If your last reply linked a document you changed since its last cold-read-fast-read "
    "and it is not listed below, run on it, from your checkout: python3 " + FAST_READ_PROGRAM
    + " --target <document path>",
)
REMINDER_INSTRUCTIONS = (
    "Run on each document, from your checkout: python3 " + FAST_READ_PROGRAM
    + " --target <document path>",
    "Apply to the document each finding of the fast read that holds.",
    "If you changed a document, tell the user which document changed and what changed.",
    "Do not start a cold-read-full-run for these documents; only the fast read is asked for.",
)


def load_cold_read_record_names():
    """Loaded by run() rather than at import, so a fault loading it is reported by main."""
    return load_module("cold_read_record_names",
                       REPOSITORY_TOP / "nc-systems" / "cold-read" / "cold-read-record-names.py")


def environment_without_git_redirection():
    runner = load_module("run_all_test_suites", SUITE_RUNNER_FILE)
    return {name: value for name, value in os.environ.items()
            if name not in runner.GIT_REDIRECTING_ENVIRONMENT_VARIABLES}


def last_reply_text(transcript_path):
    """Read the turn's last reply with the absence-claim hook's reader."""
    reader = load_module("absence_claim_locator_reminder_hook", TRANSCRIPT_READER_FILE)
    reply, _ = reader.read_turn(transcript_path)
    return reply


class GitComparisonFailure(Exception):
    """git could not find a document's checkout, or compare the document with origin/main."""


def checkout_top(directory, git_environment):
    """The top of the git checkout holding the directory, or None when git says it is in none.

    Raises GitComparisonFailure for any other git failure, since then the hook
    cannot tell whether the directory is in a checkout.
    """
    try:
        output = git_runner.run_git_unless_outside_a_repository(
            directory, ["rev-parse", "--show-toplevel"], environment=git_environment,
            timeout_seconds=GIT_TIMEOUT_SECONDS)
    except git_runner.GitCommandFailed as failure:
        raise GitComparisonFailure(str(failure)) from failure
    top = os.fsdecode(output or b"").strip()
    return Path(top).resolve() if top else None


def git_in_checkout(top, arguments, git_environment):
    try:
        return subprocess.run(["git", "-C", str(top), *arguments], capture_output=True,
                              timeout=GIT_TIMEOUT_SECONDS, env=git_environment)
    except subprocess.TimeoutExpired as error:
        raise GitComparisonFailure(f"git {' '.join(arguments)} in {top}: {error!r}") from error


def git_failure(top, arguments, completed):
    return GitComparisonFailure(
        f"git {' '.join(arguments)} failed in {top} with exit {completed.returncode}: "
        f"{completed.stderr.decode(errors='replace').strip()}")


def main_base(document_top, git_environment, bases):
    """The checkout's fork point from origin/main, or its failure, found once per checkout per run.

    A timeout is kept like an exit-code failure: each document after the first
    would otherwise wait out the time limit again, and enough of them outlast
    the hook's own time limit, so no reminder is printed at all.
    """
    if document_top not in bases:
        arguments = ["merge-base", "HEAD", MAIN_REFERENCE]
        try:
            found = git_in_checkout(document_top, arguments, git_environment)
        except GitComparisonFailure as failure:
            bases[document_top] = failure
        else:
            bases[document_top] = (git_failure(document_top, arguments, found)
                                   if found.returncode != 0
                                   else found.stdout.decode().strip())
    if isinstance(bases[document_top], GitComparisonFailure):
        raise bases[document_top]
    return bases[document_top]


def document_differs_from_main(document, document_top, git_environment, bases):
    """True when the document is not at its checkout's main base, or its bytes differ."""
    arguments = ["ls-tree", "-z", main_base(document_top, git_environment, bases), "--",
                 document.relative_to(document_top).as_posix()]
    listed = git_in_checkout(document_top, arguments, git_environment)
    if listed.returncode != 0:
        raise git_failure(document_top, arguments, listed)
    if not listed.stdout:
        return True
    # An entry reads "<mode> <type> <object>\t<path>".
    arguments = ["cat-file", "blob", listed.stdout.split()[2].decode()]
    shown = git_in_checkout(document_top, arguments, git_environment)
    if shown.returncode != 0:
        raise git_failure(document_top, arguments, shown)
    return shown.stdout != document.read_bytes()


def find_markdown_file_paths_linked_or_named_in_agent_reply(
        reply, cwd, session_top=None, skipped=lambda path: False):
    """Return the existing Markdown files the reply links, resolved, in order.

    A relative path is tried against cwd, then session_top, the top of cwd's checkout.
    """
    candidates = []
    for match in FILE_URL_PATTERN.finditer(reply):
        candidates.append(unquote(match[1]))
    for match in ABSOLUTE_PATH_PATTERN.finditer(reply):
        candidates.append(match[1])
    relative_bases = [base for base in (cwd, session_top) if base]
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


def read_by_agent_session(report, document, session_id, record_names):
    return record_names.cold_read_fast_read_target_path_if_run_by_given_agent_session(report, session_id) == document


def document_is_due(document, record_directories, document_top, record_names,
                    session_id=None):
    suggestions = walk_draft_suggestions_path(document)
    if suggestions is not None and suggestions.is_file():
        # Read the agent-session file first, so a malformed one is reported here as on the records route.
        read_by_this_agent_session = read_by_agent_session(suggestions, document, session_id, record_names)
        if (suggestions.stat().st_mtime >= document.stat().st_mtime
                or read_by_this_agent_session):
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
            if any(read_by_agent_session(report, document, session_id, record_names)
                   for report in record.iterdir()
                   if record_names.COMPLETED_REPORT_NAME_PATTERN.match(report.name)):
                return False
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
    if stop_hooks_stay_silent_rule.stop_hook_stays_silent_while_agent_answers_a_stop_hook(payload):
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
    cwd = Path(payload["cwd"]) if payload.get("cwd") else None
    try:
        reply = last_reply_text(Path(transcript_path).expanduser())
    except (OSError, UnicodeDecodeError) as error:
        lines = [line.format(reason=error) for line in TRANSCRIPT_UNREADABLE_LINES]
        print(f"cold-read-fast-read-due-for-linked-document-reminder-hook: {lines[0]}",
              file=sys.stderr)
        return json.dumps({"hookSpecificOutput": {
            "hookEventName": "Stop",
            "additionalContext": "\n".join(lines),
        }}, ensure_ascii=False)
    if not reply:
        return None
    git_environment = environment_without_git_redirection()
    session_top = None
    session_top_reason = None
    if cwd:
        try:
            session_top = checkout_top(cwd, git_environment)
        except GitComparisonFailure as failure:
            session_top_reason = " ".join(str(failure).split())
            print(SESSION_CHECKOUT_UNKNOWN_STDERR_LINE.format(cwd=cwd, reason=session_top_reason),
                  file=sys.stderr)
    due = []
    unchecked = []
    main_bases = {}
    documents = find_markdown_file_paths_linked_or_named_in_agent_reply(
        reply, cwd, session_top,
        lambda path: is_skipped(path, log_store_directory, record_names))
    for document in documents:
        document_top = None
        reason = None
        try:
            document_top = checkout_top(document.parent, git_environment)
            changed = document_top is None or document_differs_from_main(
                document, document_top, git_environment, main_bases)
        except GitComparisonFailure as failure:
            reason = " ".join(str(failure).split())
            print(UNCHECKED_STDERR_LINE.format(document=document, reason=reason),
                  file=sys.stderr)
            changed = True
        if not changed:
            continue
        stores = [store]
        for top in (document_top, session_top):
            if top is not None and top / record_names.RECORDS_DIRECTORY_NAME not in stores:
                stores.append(top / record_names.RECORDS_DIRECTORY_NAME)
        is_due = document_is_due(document, stores, document_top, record_names,
                                 payload.get("session_id"))
        if reason is not None:
            # Listed even when not due: stderr alone would hide git's failure from the agent.
            unchecked.append((document, reason, is_due))
        elif is_due:
            due.append(document)
    if not due and not unchecked and session_top_reason is None:
        return None
    unchecked_due = [document for document, _, is_due in unchecked if is_due]
    lines = []
    if session_top_reason is not None:
        lines += [line.format(cwd=cwd, reason=session_top_reason)
                  for line in SESSION_CHECKOUT_UNKNOWN_LINES]
    if due:
        lines += [REMINDER_OPENING] + [f"  {document}" for document in due]
    if unchecked:
        lines += [UNCHECKED_OPENING]
        lines += [f"- {document}: {reason}" + ("" if is_due else UNCHECKED_ALREADY_READ_NOTICE)
                  for document, reason, is_due in unchecked]
        if unchecked_due:
            lines += [UNCHECKED_INSTRUCTION]
    if due or unchecked_due:
        lines += list(REMINDER_INSTRUCTIONS)
    return json.dumps({"hookSpecificOutput": {
        "hookEventName": "Stop",
        "additionalContext": "\n".join(lines),
    }}, ensure_ascii=False)


def main():
    try:
        output = run(sys.stdin.read(), os.environ)
    except Exception as error:
        return fault_exit(error)
    if output is not None:
        print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
