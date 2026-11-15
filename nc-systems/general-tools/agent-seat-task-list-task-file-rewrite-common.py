#!/usr/bin/env python3
"""Replace an existing task file in an agent-seat's Claude Code task list, for a program that
changes a task it or another program opened, such as marking it completed.

An agent-seat's task list is the directory `~/.claude/tasks/nedschorus-<seat>-tasks/`; each task
is `<id>.json` there. A new task is written by
nc-systems/general-tools/agent-seat-task-list-new-pending-task-write-common.py.

Load it by path, under the snake_case form of its file name:

    spec = importlib.util.spec_from_file_location(
        "agent_seat_task_list_task_file_rewrite_common", <path>)
"""

import json
import os
import tempfile
from pathlib import Path


def agent_seat_task_list_task_file_rewrite(task_file, task):
    """Replace task_file with the task dict `task`, so a reader sees the old file or the new one,
    never a part. Raises OSError, and then leaves task_file as it was and no partial file.

    The partial file's name is unique, because programs that rewrite tasks can run at the same
    moment, such as one cleaner per session-handoff.
    """
    task_file = Path(task_file)
    descriptor, partial = tempfile.mkstemp(prefix=f".{task_file.name}.", suffix=".partial",
                                           dir=task_file.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(json.dumps(task, indent=2))  # pragma: no mutate, the indent only changes whitespace, and Claude Code and every program here read the task file as JSON
        os.replace(partial, task_file)
    except BaseException:
        Path(partial).unlink(missing_ok=True)
        raise
