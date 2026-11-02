#!/usr/bin/env python3
"""PostToolUse hook: keep a work-snapshot of each worktree's uncommitted changes.

Runs after every Edit, Write, NotebookEdit and Bash call. For each worktree
the call may have changed, it writes or replaces the calling `claude`
process's work-snapshot when something is uncommitted, and deletes it when
nothing is, through nc-systems/handoff/uncommitted-work-snapshots.py. It
never changes a worktree's files, index or branch.

Which worktrees: after Edit, Write and NotebookEdit, the one holding the
edited file; after Bash, the one holding the call's cwd, plus every existing
worktree that already has a work-snapshot of this owner, because a Bash
command can change files elsewhere. Only worktrees of the clone this script
belongs to are touched.

It also writes the owner file of a subagent's worktree, which
scripts/worktree-owner-file-read-and-write.py describes: when the worktree has
none and Claude Code's `git worktree lock` reason on it, "claude agent
agent-<id> (pid N start M)", names the hook's own `claude` process, the file
names that process's agent-session as the owner. Claude Code drops the lock
when the subagent finishes, so the subagent's Edit, Write, NotebookEdit and
Bash calls in the worktree are when the owner can be read. A worktree whose
subagent made none of those calls there gets no owner file.

When something fails, or no `claude` process is among the hook's ancestors,
the agent is told through additionalContext that the worktree's uncommitted
work is not protected; the hook always exits 0, since the tool call has
already happened.

Design: nc-systems/handoff/handoff-uncommitted-work-snapshots-across-crashes-design.md.
"""

import importlib.util
import json
import os
import sys
from pathlib import Path

CLONE_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = CLONE_ROOT / "nc-systems" / "handoff" / "uncommitted-work-snapshots.py"
OWNER_FILE_MODULE_PATH = CLONE_ROOT / "scripts" / "worktree-owner-file-read-and-write.py"

FILE_EDITING_TOOLS = ("Edit", "Write", "NotebookEdit")

NOT_PROTECTED_MESSAGE = (
    "Your uncommitted work in {worktree} has no work-snapshot, so a crash "
    "before you commit can lose it: {reason}\n"
    "If the work matters, commit it soon.\n"
    "If this message comes again after your next edit in the same worktree, "
    "tell the user what it says.")


OWNER_FILE_NOT_WRITTEN_MESSAGE = (
    "The owner file of your worktree {worktree}, the file that tells the worktree cleaner "
    "who owns the worktree, could not be written, so "
    "scripts/clean-worktrees.py will never remove that worktree, and it stays on disk once your "
    "work is done: {reason}\n"
    "Carry on with your task; nothing you do here fixes this.\n"
    "In your final report, give the agent that dispatched you this sentence: \"Worktree "
    "{worktree} has no owner file, the file that tells the worktree cleaner who owns it, so "
    "the worktree cleaner leaves it alone; when its work is pushed or merged, remove it with "
    "git worktree remove {worktree}.\"")


def load_worktree_owner_file_read_and_write_module():
    spec = importlib.util.spec_from_file_location("worktree_owner_file_read_and_write",
                                                  OWNER_FILE_MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_snapshots_module():
    spec = importlib.util.spec_from_file_location("uncommitted_work_snapshots", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


snapshots = None


def edited_path(tool_input):
    return tool_input.get("file_path") or tool_input.get("notebook_path")


def candidate_worktrees(payload, owner_key):
    """(worktrees the call may have changed, messages for those that could not be found)"""
    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input") or {}
    candidates = []
    messages = []

    def add_worktree_containing(path):
        try:
            candidates.append(snapshots.worktree_containing(path))
        except Exception as error:
            messages.append(NOT_PROTECTED_MESSAGE.format(
                worktree=f"the worktree holding {path}",
                reason=f"its worktree could not be found: {type(error).__name__}: {error}"))

    if tool_name in FILE_EDITING_TOOLS:
        path = edited_path(tool_input)
        if path:
            add_worktree_containing(path)
    elif tool_name == "Bash":
        if payload.get("cwd"):
            add_worktree_containing(payload["cwd"])
        if owner_key:
            for snapshot in snapshots.all_work_snapshots(CLONE_ROOT):
                if (snapshot["owner_key"] == owner_key
                        and Path(snapshot["worktree"]).is_dir()):
                    candidates.append(Path(snapshot["worktree"]).resolve())
    unique = []
    for worktree in candidates:
        if worktree is not None and worktree not in unique:
            unique.append(worktree)
    return unique, messages


def subagent_worktree_owner_file_write_message(worktree, owner_process, owner_key, agent_seat):
    """Write the owner file of a subagent's worktree, naming the agent-session that dispatched the
    subagent, while Claude Code's lock names that agent-session's claude process, which is this
    hook's owner; return a message for the agent when the file could not be written, else None."""
    try:
        owner_file = load_worktree_owner_file_read_and_write_module()
        lock_reason = owner_file.worktree_lock_reason_read(worktree)
        if owner_file.claude_code_subagent_worktree_lock_reason_dispatching_process_id_parse(lock_reason) != owner_process:
            return None
        if owner_file.worktree_owner_file_read(worktree) is not None:
            return None
        owner_file.worktree_owner_file_write(worktree, owner_file.OWNER_AGENT_SESSION,
                                             agent_seat or snapshots.UNKNOWN_AGENT_SEAT, owner_key)
    except Exception as error:
        # A concurrent hook run of the same agent-session may have written it first.
        if type(error).__name__ == "WorktreeOwnerFileAlreadyExistsError":
            return None
        return OWNER_FILE_NOT_WRITTEN_MESSAGE.format(
            worktree=worktree, reason=f"{type(error).__name__}: {error}")
    return None


def run(payload, start_process_id):
    """Messages for the agent; empty when every worktree is protected."""
    try:
        clone = snapshots.common_git_directory(CLONE_ROOT)
        owner_process = snapshots.claude_owner_process_id(start_process_id)
        owner_key = (snapshots.owner_key_of_process(owner_process)
                     if owner_process is not None else None)
        worktrees, messages = candidate_worktrees(payload, owner_key)
    except Exception as error:
        return [NOT_PROTECTED_MESSAGE.format(
            worktree="the worktree this call changed",
            reason=f"the hook could not start: {type(error).__name__}: {error}")]
    agent_seat = os.environ.get(snapshots.AGENT_SEAT_ENVIRONMENT_VARIABLE, "")
    for worktree in worktrees:
        try:
            if worktree != CLONE_ROOT and snapshots.common_git_directory(worktree) != clone:
                continue
            if owner_process is not None:
                message = subagent_worktree_owner_file_write_message(
                    worktree, owner_process, owner_key, agent_seat)
                if message:
                    messages.append(message)
            if owner_key is None:
                if snapshots.has_uncommitted_changes(worktree):
                    messages.append(NOT_PROTECTED_MESSAGE.format(
                        worktree=worktree,
                        reason="no process named claude is among this hook's parent "
                               "processes, so the work-snapshot has no owner to record"))
                continue
            snapshots.refresh_work_snapshot(worktree, owner_key, agent_seat,
                                            payload.get("transcript_path", ""))
        except Exception as error:
            messages.append(NOT_PROTECTED_MESSAGE.format(
                worktree=worktree, reason=f"{type(error).__name__}: {error}"))
    return messages


def main():
    global snapshots
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError as error:
        payload = None
        messages = [NOT_PROTECTED_MESSAGE.format(
            worktree="the worktree this call changed",
            reason=f"the hook's input was not JSON: {error}")]
    if payload is not None:
        try:
            snapshots = load_snapshots_module()
        except Exception as error:
            payload = None
            messages = [NOT_PROTECTED_MESSAGE.format(
                worktree="the worktree this call changed",
                reason=f"{MODULE_PATH} could not be loaded: {type(error).__name__}: {error}")]
    if payload is not None:
        messages = run(payload, os.getppid())
    if messages:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": "\n\n".join(messages)}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
