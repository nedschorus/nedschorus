#!/usr/bin/env python3
"""After a write, edit or shell command, name the shared names the branch newly adds, once per worktree and branch.

The names already reported are kept in the worktree's own git directory, keyed by the branch
the worktree is on, so a later agent-session of the same agent-seat is not told them again on
that branch, a new branch that adds the same name is told it, and each other worktree keeps its
own record. Entries for branches that no longer exist are dropped when the record is written.
The content cache and the once-per-session failure reports stay per agent-session.
"""
# The hook never blocks: any failure leaves the agent's turn as it was, apart from one line saying the check failed.

import fcntl
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

GIT_CALL_TIMEOUT_SECONDS = 10
# A first reminder on a large branch would otherwise run to hundreds of lines.
REMINDER_NAME_LIMIT = 30
LISTER_COMMAND = "python3 scripts/new-shared-names-in-changed-files-list.py"
FILE_WRITING_TOOL_NAMES = frozenset({"Write", "Edit", "MultiEdit", "NotebookEdit"})
SHELL_TOOL_NAME = "Bash"
STATE_DIRECTORY = Path(tempfile.gettempdir()) / "new-shared-names-reminder-hook-state"
SESSION_ID_SAFE_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
LISTER_PATH = Path(__file__).resolve().parent / "new-shared-names-in-changed-files-list.py"
NAMING_PAGE_PATH = "docs/nedschorus-wiki/nedschorus-how-to-choose-a-name-for-files-code-and-glossary-terms.md"
NAMING_FRESH_AGENT_NAME = "new-name-propose-and-check-fresh-agent"
REPORTED_NAMES_FILE_NAME = "new-shared-names-reported.json"

REMINDER_TEMPLATE = (
    "new-shared-names-reminder: your branch now adds these shared names, which other files "
    "or agents will meet:\n{names}\n"
    "Send them, with one sentence on what each names, to the {agent} subagent, run in the "
    "background, and keep working.\n"
    "When it flags a name, rename it everywhere your branch uses it, in one commit.\n"
    "If it flags a new project-term or system-term, put the new term to the user before you "
    "use it.\n"
    "If a listed name is not one you chose, such as quoted text or an existing name written "
    "differently, do not send it and do not rename it.\n"
    "How names are chosen: {page}."
)
MORE_NAMES_LINE = "  and {count} more, shown after a later edit; run {command} to see all now"
FAILURE_TEMPLATE = (
    "new-shared-names-reminder: the check for new shared names on this branch failed, so "
    "no names are being listed: {error}\n"
    "If the error names origin/main, run `git fetch`; the check runs again after your next "
    "edit.\n"
    "Until it works, check new names by hand against {page}."
)


def load_lister():
    spec = importlib.util.spec_from_file_location("new_shared_names_in_changed_files_list", LISTER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git_output(arguments, cwd: Path):
    try:
        finished = subprocess.run(["git", *arguments], cwd=str(cwd), capture_output=True,
                                  text=True, check=False, timeout=GIT_CALL_TIMEOUT_SECONDS)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None
    if finished.returncode != 0:
        return None
    return finished.stdout


def state_path_for(session_id: str) -> Path:
    return STATE_DIRECTORY / f"{session_id}.json"


def empty_state() -> dict:
    return {"worktree_fingerprint": "", "file_cache": {}, "reported_failures": []}


def read_state(session_id: str) -> dict:
    try:
        state = json.loads(state_path_for(session_id).read_text())
    except (OSError, ValueError):
        return empty_state()
    if not isinstance(state, dict):
        return empty_state()
    return dict(empty_state(), **state)


def write_state(session_id: str, state: dict) -> None:
    try:
        STATE_DIRECTORY.mkdir(parents=True, exist_ok=True)
        temporary = state_path_for(session_id).with_suffix(".partial")
        temporary.write_text(json.dumps(state))
        temporary.replace(state_path_for(session_id))
    except OSError:
        pass


def reported_names_path(checkout: Path):
    """Return the worktree's record of reported names, in its own git directory, or None when git cannot answer."""
    git_directory = git_output(["rev-parse", "--absolute-git-dir"], checkout)
    if not git_directory or not git_directory.strip():
        return None
    return Path(git_directory.strip()) / REPORTED_NAMES_FILE_NAME


DETACHED_HEAD_REPORTED_NAMES_RECORD_KEY = "HEAD"
LOCAL_BRANCH_LIST_FAILURE = (
    "new-shared-names-reminder: git for-each-ref failed, so this run could not drop the record's "
    "entries for branches that no longer exist; they are kept for now.\n"
    "The new names on the current branch were still recorded.\n"
    "Nothing is needed from you: the hook tries again on its next run."
)
UNREADABLE_RECORD_MOVED_TEMPLATE = (
    "new-shared-names-reminder: the record of names already reported in this worktree could not "
    "be read ({reason}), so it was moved to {unreadable} for inspection and a new record was started.\n"
    "Names reported before in this worktree may be reported again; nothing is needed from you for that.\n"
    "If this message repeats on later calls, tell the user, with the reason above."
)
UNREADABLE_RECORD_NOT_MOVED_TEMPLATE = (
    "new-shared-names-reminder: the record of names already reported in this worktree could not "
    "be read ({reason}), and could not be moved to {unreadable} ({move_reason}), so it stays in place "
    "at {record}.\n"
    "Names reported before, and the names shown now, may be reported again on later calls; nothing "
    "is needed from you for that.\n"
    "If this message repeats on later calls, tell the user, with both reasons above."
)
RECORD_WRITE_FAILED_TEMPLATE = (
    "new-shared-names-reminder: the record of names already reported in this worktree, {record}, "
    "could not be written ({reason}).\n"
    "The names just shown may be shown again on later calls; nothing is needed from you for that.\n"
    "If this message repeats on later calls, tell the user, with the reason above."
)


class ReportedNamesRecordFailure(Exception):
    pass


class UnreadableReportedNamesRecordNotMoved(ReportedNamesRecordFailure):
    def __init__(self, read_reason: str, move_reason: str):
        super().__init__(f"{read_reason}; {move_reason}")
        self.read_reason = read_reason
        self.move_reason = move_reason


def reported_names_record_key_for(checkout: Path) -> str:
    """Return the branch the worktree is on, or the detached-HEAD key when HEAD is detached or unreadable."""
    branch = git_output(["symbolic-ref", "--short", "-q", "HEAD"], checkout)
    return branch.strip() if branch and branch.strip() else DETACHED_HEAD_REPORTED_NAMES_RECORD_KEY


def read_reported_names_record(record_path: Path) -> dict:
    """Return the record, {branch: {reported "kind\\tname" keys}}; a missing record is empty.

    Raises ReportedNamesRecordFailure when the record exists but cannot be read or parsed.
    """
    try:
        text = record_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    except UnicodeDecodeError as error:
        raise ReportedNamesRecordFailure("not valid UTF-8") from error
    except OSError as error:
        raise ReportedNamesRecordFailure(error.strerror or type(error).__name__) from error
    try:
        record = json.loads(text)
    except ValueError as error:
        raise ReportedNamesRecordFailure("not valid JSON") from error
    if not isinstance(record, dict):
        raise ReportedNamesRecordFailure("not a record keyed by branch")
    return {key: {entry for entry in entries if isinstance(entry, str)}
            for key, entries in record.items() if isinstance(key, str) and isinstance(entries, list)}


def unreadable_record_path_for(record_path: Path) -> Path:
    return record_path.with_name(record_path.name + ".unreadable")


def reported_names_record_merge_prune_and_write(record_path: Path, key: str, entries: set, checkout: Path):
    """Add entries under key, merged with what other writers stored, drop branches that no longer exist, and write.

    Returns (branch_list_read, moved_reason). The branch list is read inside the lock, so a branch
    another run created and recorded while this run was scanning is not dropped; when git cannot
    list the branches, every branch is kept and branch_list_read is False. A record that cannot be
    read is first moved aside to the .unreadable file, replacing an older one, so it can still be
    inspected; moved_reason is then why it could not be read, and otherwise None.
    Nothing is written when the record would not change.
    A lock file serialises writers in one worktree, and each write goes to its own temporary
    file renamed over the record, so a reader never sees a partly written record.
    Raises UnreadableReportedNamesRecordNotMoved when an unreadable record cannot be moved aside,
    which leaves it in place, and ReportedNamesRecordFailure when the record cannot be written.
    """
    lock_path = record_path.with_name(record_path.name + ".lock")
    moved_reason = None
    try:
        with open(lock_path, "a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                stored = read_reported_names_record(record_path)
            except ReportedNamesRecordFailure as read_failure:
                stored = None
                try:
                    os.replace(record_path, unreadable_record_path_for(record_path))
                except OSError as move_error:
                    raise UnreadableReportedNamesRecordNotMoved(
                        str(read_failure), move_error.strerror or type(move_error).__name__) from move_error
                moved_reason = str(read_failure)
            record = dict(stored or {})
            if entries:
                record[key] = record.get(key, set()) | entries
            live_branches = local_branches(checkout)
            if live_branches is not None:
                keep = set(live_branches) | {key, DETACHED_HEAD_REPORTED_NAMES_RECORD_KEY}
                record = {name: values for name, values in record.items() if name in keep}
            if stored is not None and record == stored:
                return live_branches is not None, moved_reason
            descriptor, temporary = tempfile.mkstemp(prefix=record_path.name + ".", suffix=".partial",
                                                     dir=str(record_path.parent))
            try:
                with os.fdopen(descriptor, "w") as handle:
                    handle.write(json.dumps({name: sorted(values) for name, values in sorted(record.items())}))
                os.replace(temporary, record_path)
            except BaseException:
                try:
                    os.unlink(temporary)
                except OSError:
                    pass
                raise
    except OSError as error:
        raise ReportedNamesRecordFailure(error.strerror or type(error).__name__) from error
    return live_branches is not None, moved_reason


def local_branches(checkout: Path):
    """Return the names of the local branches, or None when git cannot list them."""
    listing = git_output(["for-each-ref", "--format=%(refname:short)", "refs/heads"], checkout)
    return listing.splitlines() if listing is not None else None


def worktree_fingerprint(checkout: Path):
    """Return a digest of HEAD, the uncommitted changes and the untracked files, or None when git cannot answer."""
    head = git_output(["rev-parse", "HEAD"], checkout)
    status = git_output(["status", "--porcelain", "--untracked-files=all"], checkout)
    diff = git_output(["diff", "HEAD"], checkout)
    untracked = git_output(["ls-files", "--others", "--exclude-standard"], checkout)
    if head is None or status is None or diff is None or untracked is None:
        return None
    parts = [head, status, diff]
    for path in untracked.splitlines():
        try:
            details = (checkout / path).stat()
        except OSError:
            continue
        parts.append(f"{path}\0{details.st_size}\0{details.st_mtime_ns}")
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()


class BranchCheckFailure(Exception):
    pass


def unreported_new_branch(checkout: Path, reported) -> str:
    """Return this worktree's branch when origin lacks it and it is not yet reported, else "".

    Only this worktree's own branch is considered: other worktrees of the same clone share
    refs/heads, and their branches belong to other agents.
    """
    try:
        finished = subprocess.run(["git", "symbolic-ref", "--short", "-q", "HEAD"], cwd=str(checkout),
                                  capture_output=True, text=True, check=False,
                                  timeout=GIT_CALL_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired as error:
        raise BranchCheckFailure("git symbolic-ref timed out") from error
    except OSError as error:
        raise BranchCheckFailure("git symbolic-ref could not start") from error
    if finished.returncode == 1:
        return ""
    if finished.returncode != 0:
        first_line = (finished.stderr.strip().splitlines() or [""])[0][:200]
        raise BranchCheckFailure(f"git symbolic-ref exited {finished.returncode}: {first_line}")
    branch = finished.stdout.strip()
    if not branch or f"branch\t{branch}" in reported:
        return ""
    try:
        lookup = subprocess.run(["git", "show-ref", "--verify", "--quiet", f"refs/remotes/origin/{branch}"],
                                cwd=str(checkout), capture_output=True, text=True, check=False,
                                timeout=GIT_CALL_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired as error:
        raise BranchCheckFailure("git show-ref timed out") from error
    except OSError as error:
        raise BranchCheckFailure("git show-ref could not start") from error
    if lookup.returncode == 0:
        return ""
    if lookup.returncode != 1:
        first_line = (lookup.stderr.strip().splitlines() or [""])[0][:200]
        raise BranchCheckFailure(f"git show-ref exited {lookup.returncode}: {first_line}")
    return branch


def failure_report_once(state: dict, error: str):
    """Return the failure text the first time this error is seen in the agent-session, else None."""
    failures = set(state.get("reported_failures", []))
    if error in failures:
        return None
    state["reported_failures"] = sorted(failures | {error})
    return FAILURE_TEMPLATE.format(error=error, page=NAMING_PAGE_PATH)


def reminder_text(new_names) -> str:
    lines = [f"  {name} ({kind}{', in ' + path if path and path != name else ''})"
             for path, kind, name in new_names[:REMINDER_NAME_LIMIT]]
    if len(new_names) > REMINDER_NAME_LIMIT:
        lines.append(MORE_NAMES_LINE.format(count=len(new_names) - REMINDER_NAME_LIMIT,
                                            command=LISTER_COMMAND))
    return REMINDER_TEMPLATE.format(names="\n".join(lines), agent=NAMING_FRESH_AGENT_NAME,
                                    page=NAMING_PAGE_PATH)


def emit(text: str) -> None:
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PostToolUse",
        "additionalContext": text,
    }}, ensure_ascii=False))


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except (json.JSONDecodeError, ValueError, OSError):
        return 0
    if not isinstance(payload, dict):
        return 0

    tool_name = payload.get("tool_name")
    if tool_name not in FILE_WRITING_TOOL_NAMES and tool_name != SHELL_TOOL_NAME:
        return 0
    session_id = payload.get("session_id")
    if not isinstance(session_id, str) or not SESSION_ID_SAFE_PATTERN.match(session_id):
        return 0
    working_directory = payload.get("cwd")
    if not isinstance(working_directory, str) or not Path(working_directory).is_dir():
        return 0
    top_level = git_output(["rev-parse", "--show-toplevel"], Path(working_directory))
    if not top_level or not top_level.strip():
        return 0
    checkout = Path(top_level.strip())

    record_path = reported_names_path(checkout)
    if record_path is None:
        return 0
    state = read_state(session_id)
    fingerprint = worktree_fingerprint(checkout)
    if fingerprint is None:
        return 0
    messages = []

    record_key = reported_names_record_key_for(checkout)
    # The branch is part of the identity, so a switch to another branch is never skipped as unchanged.
    fingerprint = f"{fingerprint}\0{record_key}"
    def tell_notice_once(text: str) -> None:
        notices = set(state.get("reported_failures", []))
        if text not in notices:
            state["reported_failures"] = sorted(notices | {text})
            messages.append(text)

    unreadable = unreadable_record_path_for(record_path)

    def record_merge_prune_and_write_telling_failures(entries: set) -> None:
        try:
            branch_list_read, moved_reason = reported_names_record_merge_prune_and_write(
                record_path, record_key, entries, checkout)
        except UnreadableReportedNamesRecordNotMoved as failure:
            tell_notice_once(UNREADABLE_RECORD_NOT_MOVED_TEMPLATE.format(
                reason=failure.read_reason, unreadable=unreadable, move_reason=failure.move_reason,
                record=record_path))
            return
        except ReportedNamesRecordFailure as failure:
            tell_notice_once(RECORD_WRITE_FAILED_TEMPLATE.format(record=record_path, reason=failure))
            return
        if not branch_list_read:
            tell_notice_once(LOCAL_BRANCH_LIST_FAILURE)
        if moved_reason:
            tell_notice_once(UNREADABLE_RECORD_MOVED_TEMPLATE.format(reason=moved_reason, unreadable=unreadable))

    try:
        record = read_reported_names_record(record_path)
    except ReportedNamesRecordFailure:
        # The locked writer below moves the unreadable record aside and tells the agent the outcome.
        record = {}
    reported = record.get(record_key, set())
    # Pruned on every run, so a branch deleted and later recreated under the same name starts fresh.
    record_merge_prune_and_write_telling_failures(set())
    try:
        new_branch = unreported_new_branch(checkout, reported)
    except BranchCheckFailure as failure:
        new_branch = ""
        failure_text = failure_report_once(state, str(failure))
        if failure_text:
            messages.append(failure_text)
    # A shell command that changed no file and left no new branch has nothing new to list.
    if (tool_name == SHELL_TOOL_NAME and not new_branch and not messages
            and fingerprint == state.get("worktree_fingerprint")):
        return 0
    state["worktree_fingerprint"] = fingerprint

    file_cache = state.get("file_cache") if isinstance(state.get("file_cache"), dict) else {}
    names = []
    try:
        lister = load_lister()
        names = lister.new_shared_names(checkout, [new_branch] if new_branch else [],
                                        already_reported=frozenset(reported), file_cache=file_cache)
    except Exception as failure:
        failure_text = failure_report_once(state, str(failure) or type(failure).__name__)
        if failure_text:
            messages.append(failure_text)

    state["file_cache"] = file_cache
    # Only the names the reminder shows count as reported; the rest are shown by a later reminder.
    shown = names[:REMINDER_NAME_LIMIT]
    newly_reported = {f"{kind}\t{name}" for _, kind, name in shown}
    if newly_reported - reported:
        record_merge_prune_and_write_telling_failures(newly_reported)
    write_state(session_id, state)
    if names:
        messages.append(reminder_text(names))
    if messages:
        emit("\n\n".join(messages))
    return 0


if __name__ == "__main__":
    sys.exit(main())
