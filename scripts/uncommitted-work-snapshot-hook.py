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

When something fails, or no `claude` process is among the hook's ancestors,
the agent is told through additionalContext that the worktree's uncommitted
work is not protected; the hook always exits 0, since the tool call has
already happened.

Design: nc-systems/handoff/uncommitted-work-snapshots-across-crashes-design.md.
"""

import importlib.util
import json
import os
import sys
from pathlib import Path

CLONE_ROOT = Path(__file__).resolve().parents[1]
_module_spec = importlib.util.spec_from_file_location(
    "uncommitted_work_snapshots",
    CLONE_ROOT / "nc-systems" / "handoff" / "uncommitted-work-snapshots.py")
snapshots = importlib.util.module_from_spec(_module_spec)
_module_spec.loader.exec_module(snapshots)

FILE_EDITING_TOOLS = ("Edit", "Write", "NotebookEdit")

NOT_PROTECTED_MESSAGE = (
    "Your uncommitted work in {worktree} has no work-snapshot, so a crash "
    "before you commit can lose it: {reason}\n"
    "If the work matters, commit it soon.\n"
    "If this repeats, tell the user what this message says.")


def edited_path(tool_input):
    return tool_input.get("file_path") or tool_input.get("notebook_path")


def candidate_worktrees(payload, owner_key):
    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input") or {}
    candidates = []
    if tool_name in FILE_EDITING_TOOLS:
        path = edited_path(tool_input)
        if path:
            candidates.append(snapshots.worktree_containing(path))
    elif tool_name == "Bash":
        if payload.get("cwd"):
            candidates.append(snapshots.worktree_containing(payload["cwd"]))
        if owner_key:
            for snapshot in snapshots.all_work_snapshots(CLONE_ROOT):
                if (snapshot["owner_key"] == owner_key
                        and Path(snapshot["worktree"]).is_dir()):
                    candidates.append(Path(snapshot["worktree"]).resolve())
    unique = []
    for worktree in candidates:
        if worktree is not None and worktree not in unique:
            unique.append(worktree)
    return unique


def run(payload, start_process_id):
    """Messages for the agent; empty when every worktree is protected."""
    messages = []
    try:
        clone = snapshots.common_git_directory(CLONE_ROOT)
        owner_process = snapshots.claude_owner_process_id(start_process_id)
        owner_key = (snapshots.owner_key_of_process(owner_process)
                     if owner_process is not None else None)
        worktrees = candidate_worktrees(payload, owner_key)
    except Exception as error:
        return [NOT_PROTECTED_MESSAGE.format(
            worktree="the worktree this call changed",
            reason=f"the hook could not start: {type(error).__name__}: {error}")]
    agent_seat = os.environ.get(snapshots.AGENT_SEAT_ENVIRONMENT_VARIABLE, "")
    for worktree in worktrees:
        try:
            if snapshots.common_git_directory(worktree) != clone:
                continue
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
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError as error:
        payload = None
        messages = [NOT_PROTECTED_MESSAGE.format(
            worktree="the worktree this call changed",
            reason=f"the hook's input was not JSON: {error}")]
    if payload is not None:
        messages = run(payload, os.getppid())
    if messages:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": "\n\n".join(messages)}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
