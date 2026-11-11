#!/usr/bin/env python3
"""Tests for nc-systems/general-tools/agent-seat-task-list-new-pending-task-write-common.py.

Run: python3 nc-systems/general-tools/tests/agent-seat-task-list-new-pending-task-write-common-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import importlib.util
import json
import sys
import tempfile
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location(
    "agent_seat_task_list_new_pending_task_write_common",
    REPOSITORY_ROOT / "nc-systems" / "general-tools"
    / "agent-seat-task-list-new-pending-task-write-common.py")
task_list = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(task_list)
write = task_list.agent_seat_task_list_new_pending_task_write

failures = 0


def check(name, condition, detail=None):
    global failures
    if condition:
        print(f"PASS  {name}")
    else:
        failures += 1
        print(f"FAIL  {name}: {detail!r}")


with tempfile.TemporaryDirectory() as scratch:
    root = Path(scratch)

    missing = root / "nedschorus-gone-tasks"
    try:
        write(missing, "subject", "description")
        raised = None
    except FileNotFoundError as error:
        raised = str(error)
    check("a task list directory that does not exist raises FileNotFoundError naming it, and is "
          "not made", raised is not None and str(missing) in raised and not missing.exists(), raised)

    empty = root / "empty"
    empty.mkdir()
    task_id = write(empty, "the subject", "the description")
    written = json.loads((empty / "1.json").read_text(encoding="utf-8"))
    check("the first task of an empty list is 1, pending, with the subject and description given",
          task_id == 1 and written == {"id": "1", "subject": "the subject",
                                       "description": "the description", "status": "pending",
                                       "blocks": [], "blockedBy": []}, written)
    check("the high-water mark is raised to the new id, and no partial file is left",
          (empty / ".highwatermark").read_text(encoding="utf-8") == "1"
          and sorted(path.name for path in empty.iterdir()) == [".highwatermark", "1.json"],
          sorted(path.name for path in empty.iterdir()))

    numbered = root / "numbered"
    numbered.mkdir()
    for name in ("2.json", "9.json", "0.json", "10.json.bak", "notes.json", ".lock"):
        (numbered / name).write_text("{}", encoding="utf-8")
    check("the new id is one more than the highest task file, files not named <id>.json ignored",
          write(numbered, "s", "d") == 10, sorted(path.name for path in numbered.iterdir()))

    marked = root / "marked"
    marked.mkdir()
    (marked / "3.json").write_text("{}", encoding="utf-8")
    (marked / ".highwatermark").write_text("7\n", encoding="utf-8")
    check("a high-water mark above every task file, as after a deletion, is never reused",
          write(marked, "s", "d") == 8
          and (marked / ".highwatermark").read_text(encoding="utf-8") == "8",
          sorted(path.name for path in marked.iterdir()))

    raced = root / "raced"
    raced.mkdir()
    (raced / ".highwatermark").write_text("not a number", encoding="utf-8")
    (raced / "2.json").write_text("{}", encoding="utf-8")
    real_link = task_list.os.link
    links_tried = []

    def link_racing_claude_code(source, target):
        links_tried.append(target)
        if len(links_tried) > 5:
            raise RuntimeError("the task writer kept retrying one id")
        if Path(target).name == "3.json" and not Path(target).exists():
            Path(target).write_text('{"id": "3", "by": "claude code"}', encoding="utf-8")
        return real_link(source, target)

    task_list.os.link = link_racing_claude_code
    try:
        task_id = write(raced, "subject", "description")
    except RuntimeError as error:
        task_id = str(error)
    finally:
        task_list.os.link = real_link
    check("an id Claude Code takes at the same moment is skipped and its file kept, and a "
          "high-water mark that is not a number is ignored",
          task_id == 4 and json.loads((raced / "3.json").read_text())["by"] == "claude code"
          and json.loads((raced / "4.json").read_text())["subject"] == "subject"
          and not list(raced.glob("*.partial")), sorted(path.name for path in raced.iterdir()))

    refused = root / "refused"
    refused.mkdir()

    def link_refused(source, target):
        raise PermissionError(13, "Permission denied", str(target))

    task_list.os.link = link_refused
    try:
        write(refused, "subject", "description")
        raised = None
    except PermissionError as error:
        raised = error
    finally:
        task_list.os.link = real_link
    check("a task file that cannot be linked into place raises, and leaves no partial file and "
          "no high-water mark", raised is not None and list(refused.iterdir()) == [],
          sorted(path.name for path in refused.iterdir()))

if failures:
    print(f"\n{failures} case(s) failed")
    sys.exit(1)
print("\nall cases passed")
