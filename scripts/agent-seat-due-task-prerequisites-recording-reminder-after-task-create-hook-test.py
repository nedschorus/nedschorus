#!/usr/bin/env python3
"""Cases for the hook that, after each TaskCreate, tells the agent how to
record what the new task waits on.

Each case runs the hook as a subprocess, as Claude Code does. The expected
text is written out whole here, so a change to the user's wording fails this
suite. The waits_on example in that text is checked against the due-task
hook's own reader, so the two hooks cannot drift apart.
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

HOOK_SCRIPT = Path(__file__).with_name("agent-seat-due-task-prerequisites-recording-reminder-after-task-create-hook.py")
DUE_TASK_RAISE_HOOK_SCRIPT = Path(__file__).with_name("agent-seat-due-task-raise-hook.py")

EXPECTED_TEXT_WITH_ID_7 = (
    'If this task (id 7) waits on a pull request merging or a GHI closing, record each one now with '
    'TaskUpdate in the task\'s metadata, as "waits_on": [{"pr_merged": <number>}, {"issue_closed": <number>}].\n'
    "If it waits on another task on your own task list, record that task with TaskUpdate's addBlockedBy.\n"
    "The due-task hook then raises this task when all of them are done.\n"
    "Record no other kind of dependency: one that is not a pull request, GHI or task is noise."
)
EXPECTED_TEXT_WITHOUT_ID = EXPECTED_TEXT_WITH_ID_7.replace(" (id 7)", "")

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def run_hook(stdin_text):
    return subprocess.run([sys.executable, str(HOOK_SCRIPT)], input=stdin_text,
                          capture_output=True, text=True, check=False)


def task_create_payload(tool_response):
    return json.dumps({"hook_event_name": "PostToolUse", "tool_name": "TaskCreate",
                       "tool_input": {"subject": "s", "description": "d"},
                       "tool_response": tool_response})


def check_reminder(case_name, result, expected_text):
    check(f"{case_name}: exit 0", result.returncode == 0, f"exit {result.returncode}, stderr {result.stderr!r}")
    check(f"{case_name}: nothing on stderr", result.stderr == "", repr(result.stderr))
    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError:
        check(f"{case_name}: stdout is JSON", False, repr(result.stdout))
        return
    check(f"{case_name}: output is the PostToolUse additionalContext, and no block",
          output == {"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                            "additionalContext": expected_text}},
          repr(output))


def check_fault(case_name, result):
    check(f"{case_name}: exit 1", result.returncode == 1, f"exit {result.returncode}")
    check(f"{case_name}: nothing on stdout", result.stdout == "", repr(result.stdout))
    check(f"{case_name}: one stderr line naming the hook and what was lost",
          result.stderr.startswith("agent-seat-due-task-prerequisites-recording-reminder-after-task-create-hook: "
                                   "the task was added, but this hook could not read it from the payload "
                                   "Claude Code sent, which is not a JSON object")
          and "you did nothing wrong" in result.stderr
          and result.stderr.count("\n") == 1, repr(result.stderr))


check_reminder("payload as Claude Code sends it, with the new task's id",
               run_hook(task_create_payload({"task": {"id": "7", "subject": "s"}})),
               EXPECTED_TEXT_WITH_ID_7)
check_reminder("payload whose tool_response has no task",
               run_hook(task_create_payload({})), EXPECTED_TEXT_WITHOUT_ID)
check_reminder("payload whose task id is empty",
               run_hook(task_create_payload({"task": {"id": ""}})), EXPECTED_TEXT_WITHOUT_ID)
check_reminder("payload whose tool_response is not an object",
               run_hook(task_create_payload("created")), EXPECTED_TEXT_WITHOUT_ID)
check_fault("stdin that is not JSON", run_hook("not json"))
check_fault("stdin that is JSON but not an object", run_hook("[1]"))

_due_task_spec = importlib.util.spec_from_file_location("agent_seat_due_task_raise_hook",
                                                        DUE_TASK_RAISE_HOOK_SCRIPT)
due_task_raise_hook = importlib.util.module_from_spec(_due_task_spec)
_due_task_spec.loader.exec_module(due_task_raise_hook)
example = json.loads(EXPECTED_TEXT_WITHOUT_ID.split('"waits_on": ', 1)[1].split("].", 1)[0]
                     .replace("<number>", "1874") + "]")
readable = due_task_raise_hook.parse_waits_on(example)
check("the waits_on example, numbers filled in, is one the due-task hook reads",
      readable == [("pr_merged", 1874), ("issue_closed", 1874)], repr(readable))

if failures:
    print(f"\n{len(failures)} case(s) failed")
    sys.exit(1)
print("\nall cases passed")
