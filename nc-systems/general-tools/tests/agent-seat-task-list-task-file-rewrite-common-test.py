#!/usr/bin/env python3
"""Tests for nc-systems/general-tools/agent-seat-task-list-task-file-rewrite-common.py.

Run: python3 nc-systems/general-tools/tests/agent-seat-task-list-task-file-rewrite-common-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import importlib.util
import json
import sys
import tempfile
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location(
    "agent_seat_task_list_task_file_rewrite_common",
    REPOSITORY_ROOT / "nc-systems" / "general-tools"
    / "agent-seat-task-list-task-file-rewrite-common.py")
task_file_rewrite_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(task_file_rewrite_module)
rewrite = task_file_rewrite_module.agent_seat_task_list_task_file_rewrite

failures = 0


def check(name, condition, detail=None):
    global failures
    if condition:
        print(f"PASS  {name}")
    else:
        failures += 1
        print(f"FAIL  {name}: {detail!r}")


ORIGINAL = {"id": "3", "subject": "the subject", "description": "the description",
            "status": "pending", "blocks": [], "blockedBy": []}
CHANGED = dict(ORIGINAL, status="completed", description="the description\nMarked completed.")

with tempfile.TemporaryDirectory() as scratch:
    list_directory = Path(scratch) / "nedschorus-alpha-tasks"
    list_directory.mkdir()
    task_file = list_directory / "3.json"
    task_file.write_text(json.dumps(ORIGINAL, indent=2), encoding="utf-8")

    rewrite(task_file, CHANGED)
    check("the task file is replaced by the task given, and no partial file is left",
          json.loads(task_file.read_text(encoding="utf-8")) == CHANGED
          and sorted(path.name for path in list_directory.iterdir()) == ["3.json"],
          sorted(path.name for path in list_directory.iterdir()))

    rewrite(str(task_file), ORIGINAL)
    check("a task file given as a string path is replaced too",
          json.loads(task_file.read_text(encoding="utf-8")) == ORIGINAL)

    list_directory.chmod(0o555)
    try:
        rewrite(task_file, CHANGED)
        raised = None
    except OSError as error:
        raised = error
    finally:
        list_directory.chmod(0o755)
    check("a list directory where no partial file can be made raises OSError and leaves the task "
          "file as it was", isinstance(raised, PermissionError)
          and json.loads(task_file.read_text(encoding="utf-8")) == ORIGINAL, raised)

    # The partial file is written, then the replace fails: only removing the partial cleans up.
    real_replace = task_file_rewrite_module.os.replace

    def failing_replace(source, target):
        raise OSError(28, "No space left on device")
    task_file_rewrite_module.os.replace = failing_replace
    try:
        rewrite(task_file, CHANGED)
        raised = None
    except OSError as error:
        raised = error
    finally:
        task_file_rewrite_module.os.replace = real_replace
    check("a replace that fails after the partial file is written raises that OSError, leaves "
          "the task file as it was and removes the partial file",
          raised is not None and raised.errno == 28
          and json.loads(task_file.read_text(encoding="utf-8")) == ORIGINAL
          and sorted(path.name for path in list_directory.iterdir()) == ["3.json"],
          (raised, sorted(path.name for path in list_directory.iterdir())))

    real_unlink = task_file_rewrite_module.os.unlink

    def failing_unlink(path):
        raise OSError(13, "Permission denied")
    task_file_rewrite_module.os.replace = failing_replace
    task_file_rewrite_module.os.unlink = failing_unlink
    try:
        rewrite(task_file, CHANGED)
        raised = None
    except OSError as error:
        raised = error
    finally:
        task_file_rewrite_module.os.replace = real_replace
        task_file_rewrite_module.os.unlink = real_unlink
    check("when the partial file cannot be removed either, the replace's OSError is the one raised "
          "and the task file is as it was",
          raised is not None and raised.errno == 28
          and json.loads(task_file.read_text(encoding="utf-8")) == ORIGINAL, raised)

sys.exit(1 if failures else 0)
