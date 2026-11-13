#!/usr/bin/env python3
"""After each TaskCreate, tell the agent how to record what the new task waits
on, so scripts/agent-seat-due-task-raise-hook.py can raise the task when that
work is done, and the branches and worktrees it holds, so
nc-systems/handoff/agent-seat-worktrees-and-branches-with-no-pull-request-first-prompt-list.py
leaves them out of the first prompt's list while the task is open.

Wired as a PostToolUse hook with matcher TaskCreate in .claude/settings.json.
The task has already been added; the hook never blocks or changes it.

OUTPUT: one JSON object on stdout, exit 0,
{"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": ...}},
which Claude Code hands the agent beside the tool result. The text names the
task's id when the payload's tool_response.task.id holds one, and otherwise is
the same text without the id. The prerequisites format it gives is the one the
due-task hook's docstring defines, and the branches format the one the list
program's docstring defines.

A payload that is not a JSON object: one line on stderr naming the hook and
the fault, nothing on stdout, exit 1, which Claude Code records as a
non-blocking error; the agent gets no reminder for that task.
"""
import importlib.util
import json
import sys
from pathlib import Path

_next_step_lines_spec = importlib.util.spec_from_file_location(
    "failed_command_tool_message_to_agent_rerun_once_then_stop_and_report_lines_common",
    Path(__file__).resolve().parents[1] / "nc-systems" / "general-tools"
    / "failed-command-tool-message-to-agent-rerun-once-then-stop-and-report-lines-common.py")
next_step_lines = importlib.util.module_from_spec(_next_step_lines_spec)
_next_step_lines_spec.loader.exec_module(next_step_lines)

# Messages here follow docs/nedschorus-wiki/nedschorus-how-to-write-a-tool-message-to-agent-such-as-a-hook-refusal-or-script-error.md.
PROGRAM = "agent-seat-due-task-prerequisites-recording-reminder-after-task-create-hook"

# The user set this wording; change it only with his approval. {task_id_clause} is the only addition.
PREREQUISITES_RECORD_INSTRUCTION_TEMPLATE = (
    'If this task{task_id_clause} waits on a pull request merging or a GHI closing, record each one now '
    'with TaskUpdate in the task\'s metadata, as "prerequisites": [{{"pr_merged": <number>}}, '
    '{{"issue_closed": <number>}}].\n'
    'If it waits on the user\'s decision on an approval-walk item, add the item to the same prerequisites list, as '
    '{{"approval_walk_item_decided": {{"approval_walk_minutes_file_path": "<absolute path of the walk-minutes file>", '
    '"approval_walk_item_heading": "<the item\'s heading in the walk-document>"}}}}; any decision the walk-minutes '
    "record meets it, approval, disapproval or moving on, but a deferral does not.\n"
    "If it waits on another task on your own task list, record that task with TaskUpdate's addBlockedBy.\n"
    "The due-task hook then raises this task when all of them are done.\n"
    "Record no other kind of dependency: one that is not a pull request, GHI, approval-walk item or task "
    "is noise.\n"
    'If this task holds a branch or a worktree, now or once you make one, record each with TaskUpdate '
    'in the task\'s metadata, as "branches": ["<branch name>", "<worktree path>"]; the first prompt\'s '
    "list of this agent-seat's worktrees and branches then leaves them out while the task is open."
)
TASK_ID_CLAUSE_TEMPLATE = " (id {task_id})"
FAULT_LINE_TEMPLATE = ("{program}: the task was added, but this hook could not read it from the payload "
                       "Claude Code sent, which is not a JSON object ({error}); you did nothing wrong. If the task waits on a pull request or a GHI, "
                       "record each one with TaskUpdate in the task's metadata, as "
                       "\"prerequisites\": [{{\"pr_merged\": <number>}}, {{\"issue_closed\": <number>}}]; "
                       "if it waits on the user's decision on an approval-walk item, add the item to "
                       "the same prerequisites list, as {{\"approval_walk_item_decided\": {{\"approval_walk_minutes_file_path\": "
                       "\"<absolute path of the walk-minutes file>\", \"approval_walk_item_heading\": "
                       "\"<the item's heading in the walk-document>\"}}}}; "
                       "if it waits on another task, record that task with TaskUpdate's addBlockedBy; "
                       "if it holds a branch or a worktree, record each with TaskUpdate in the task's "
                       "metadata, as \"branches\": [\"<branch name>\", \"<worktree path>\"].")


def created_task_id(payload):
    """Return the new task's id from tool_response.task.id, or None."""
    tool_response = payload.get("tool_response")
    task = tool_response.get("task") if isinstance(tool_response, dict) else None
    task_id = task.get("id") if isinstance(task, dict) else None
    return task_id if isinstance(task_id, str) and task_id else None


def prerequisites_record_instruction(task_id):
    clause = TASK_ID_CLAUSE_TEMPLATE.format(task_id=task_id) if task_id is not None else ""
    return PREREQUISITES_RECORD_INSTRUCTION_TEMPLATE.format(task_id_clause=clause)


def main():
    try:
        payload = json.loads(sys.stdin.read())
        if not isinstance(payload, dict):
            raise ValueError(f"the payload is JSON but not an object ({type(payload).__name__})")
    except ValueError as error:
        print(FAULT_LINE_TEMPLATE.format(program=PROGRAM, error=f"{type(error).__name__}: {error}"),
              file=sys.stderr)
        return 1
    next_step_lines.post_tool_use_hook_additional_context_print_for_agent(
        prerequisites_record_instruction(created_task_id(payload)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
