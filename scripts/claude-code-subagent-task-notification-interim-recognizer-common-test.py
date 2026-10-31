#!/usr/bin/env python3
"""Tests for claude-code-subagent-task-notification-interim-recognizer-common.py.

Run: python3 scripts/claude-code-subagent-task-notification-interim-recognizer-common-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import importlib.util
import json
import sys
from pathlib import Path

_specification = importlib.util.spec_from_file_location(
    "claude_code_subagent_task_notification_interim_recognizer_common",
    Path(__file__).with_name("claude-code-subagent-task-notification-interim-recognizer-common.py"))
recognizer = importlib.util.module_from_spec(_specification)
_specification.loader.exec_module(recognizer)

failures = []


def check(case_name, condition):
    print(f"{'PASS' if condition else 'FAIL'}  {case_name}")
    if not condition:
        failures.append(case_name)


# Trimmed from real transcripts.
INTERIM_BY_NOTE = (
    "<task-notification>\n<task-id>a68d25248370ee861</task-id>\n<status>completed</status>\n"
    '<summary>Agent "Fix-round for PR 2045" is waiting on its own background work</summary>\n'
    "<note>This agent stopped with background work of its own still running. It may resume on "
    "its own when that work completes or reports, and the same task-id notifies again if it "
    "does; the result below may be interim.</note>\n"
    "<result>Waiting on the test run.</result>\n</task-notification>")
# Its <note> is left out, so only the <result> marks it interim.
INTERIM_BY_RESULT = (
    "<task-notification>\n<task-id>a35d12962c3517666</task-id>\n<status>completed</status>\n"
    '<summary>Agent "Fix marker-before-ship in grid PR" finished</summary>\n'
    "<result>This agent has not reported yet: it is waiting on its own background work and will "
    "deliver its report through SubagentHandback when that finishes.\n</result>\n"
    "</task-notification>")
FINAL = (
    "<task-notification>\n<task-id>ab44021c35306f441</task-id>\n<status>completed</status>\n"
    '<summary>Agent "Fable check of decisions 4 and 5" finished</summary>\n'
    "<note>A task-notification fires each time this agent stops with no live background "
    "children of its own.</note>\n"
    "<result>This agent's report was delivered to you as a message from \"ab44021c35306f441\" "
    "(its SubagentHandback call). Read it there; it is not repeated here.\n</result>\n"
    "</task-notification>")

check("a note saying the result may be interim marks the notification interim",
      recognizer.task_notification_is_interim(INTERIM_BY_NOTE))
check("a result saying the agent has not reported yet marks the notification interim",
      recognizer.task_notification_is_interim(INTERIM_BY_RESULT))
check("a final notification is not interim",
      not recognizer.task_notification_is_interim(FINAL))
check("a notification with no note and no result is not interim",
      not recognizer.task_notification_is_interim(
          "<task-notification>\n<task-id>a1</task-id>\n<status>completed</status>\n"
          "</task-notification>"))
check("the JSON-escaped text of a transcript line is read the same way",
      recognizer.task_notification_is_interim(json.dumps(INTERIM_BY_NOTE))
      and recognizer.task_notification_is_interim(json.dumps(INTERIM_BY_RESULT))
      and not recognizer.task_notification_is_interim(json.dumps(FINAL)))
check("a final report that quotes an interim note is not interim",
      not recognizer.task_notification_is_interim(FINAL.replace(
          "<result>", "<result>The notice read <note>the result below may be interim</note>. ")))
check("a report that quotes an interim note, in a notification with no note of its own, is not interim",
      not recognizer.task_notification_is_interim(
          "<task-notification>\n<task-id>a1</task-id>\n<status>completed</status>\n"
          "<result>The notice read <note>the result below may be interim</note>.</result>\n"
          "</task-notification>"))
check("a final report that only mentions the not-yet-reported wording is not interim",
      not recognizer.task_notification_is_interim(FINAL.replace(
          "<result>", "<result>Fixed: This agent has not reported yet is now recognised. ")))
check("the not-yet-reported wording after leading whitespace still marks it interim",
      recognizer.task_notification_is_interim(INTERIM_BY_RESULT.replace("<result>", "<result>\n  ")))

sys.exit(1 if failures else 0)
