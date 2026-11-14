#!/usr/bin/env python3
"""Write a new pending task into an agent-seat's Claude Code task list, for a program that hands
an agent-seat work.

An agent-seat's task list is the directory `~/.claude/tasks/nedschorus-<seat>-tasks/`; each task
is `<id>.json` there, and `.highwatermark` holds the highest id Claude Code has used, deleted
tasks included.

Load it by path, under the snake_case form of its file name:

    spec = importlib.util.spec_from_file_location(
        "agent_seat_task_list_new_pending_task_write_common", <path>)
"""

import json
import os
import re
import tempfile
from pathlib import Path

TASK_FILE_NAME_PATTERN = re.compile(r"[1-9][0-9]*\.json")
TASK_HIGH_WATER_MARK_FILE_NAME = ".highwatermark"


def agent_seat_task_list_new_pending_task_write(list_directory, subject, description, metadata=None):
    """Write a new pending task into the list, with metadata when given; return its id. Raises
    OSError.

    The id is one more than the highest of the list's task ids and its .highwatermark, as
    Claude Code numbers a new task; the file is linked into place only where no file of that
    name exists, so a task Claude Code creates at the same moment is not overwritten. A list
    directory that does not exist raises FileNotFoundError: a caller whose agent-seat may have
    made no task yet creates the directory first.
    """
    list_directory = Path(list_directory)
    if not list_directory.is_dir():
        raise FileNotFoundError(f"the task list directory {list_directory} does not exist")
    highest = 0
    for path in list_directory.iterdir():
        if TASK_FILE_NAME_PATTERN.fullmatch(path.name):
            highest = max(highest, int(path.stem))
    mark_path = list_directory / TASK_HIGH_WATER_MARK_FILE_NAME
    mark = mark_path.read_text(encoding="utf-8").strip() if mark_path.is_file() else ""
    if mark.isdigit():
        highest = max(highest, int(mark))
    task_id = highest + 1
    with tempfile.NamedTemporaryFile("w", dir=list_directory, prefix=".task-", suffix=".partial",
                                     delete=False, encoding="utf-8") as partial:
        partial_path = Path(partial.name)
    try:
        while True:
            task = {"id": str(task_id), "subject": subject, "description": description,
                    "status": "pending", "blocks": [], "blockedBy": []}
            if metadata is not None:
                task["metadata"] = metadata
            partial_path.write_text(json.dumps(task, indent=2), encoding="utf-8")
            try:
                os.link(partial_path, list_directory / f"{task_id}.json")
                break
            except FileExistsError:
                task_id += 1
    finally:
        partial_path.unlink(missing_ok=True)
    mark_partial = list_directory / (TASK_HIGH_WATER_MARK_FILE_NAME + ".partial")
    mark_partial.write_text(str(task_id), encoding="utf-8")
    os.replace(mark_partial, mark_path)
    return task_id
