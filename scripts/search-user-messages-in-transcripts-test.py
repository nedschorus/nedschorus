#!/usr/bin/env python3
"""Tests for search-user-messages-in-transcripts.py.

Run: python3 scripts/search-user-messages-in-transcripts-test.py
Prints one line per case and exits non-zero if any case fails.

Fixture transcripts are written to a temporary directory; no real session is read.
"""

import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

SEARCH_SCRIPT = Path(__file__).with_name("search-user-messages-in-transcripts.py")

_spec = importlib.util.spec_from_file_location("search_user_messages_in_transcripts", SEARCH_SCRIPT)
search_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(search_module)

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def typed(text):
    return {"type": "user", "message": {"role": "user", "content": text}}


def tool_result(text):
    return {"type": "user", "message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": "toolu_1", "content": text}]}}


def interrupt_notice():
    return {"type": "user", "message": {"role": "user", "content": [
        {"type": "text", "text": "[Request interrupted by user]"}]}}


def agent(text):
    return {"type": "assistant", "message": {"role": "assistant", "content": [
        {"type": "text", "text": text}]}}


# The shape the harness writes for a message typed mid-turn, which has no user record.
def queued(text, origin_kind="human"):
    return {"type": "attachment", "attachment": {
        "type": "queued_command", "prompt": text, "commandMode": "prompt",
        "origin": {"kind": origin_kind}, "humanTurn": origin_kind == "human"}}


def enqueue(text):
    return {"type": "queue-operation", "operation": "enqueue", "content": text}


def write_transcript(directory, records, name="session.jsonl"):
    project = Path(directory) / "-home-someone-agents-alpha"
    project.mkdir(parents=True, exist_ok=True)
    path = project / name
    path.write_text("".join(json.dumps(record) + "\n" for record in records))
    return path


def user_texts(path):
    return [turn[2] for turn in search_module.read_turns(str(path)) if turn[1] == "user"]


with tempfile.TemporaryDirectory() as directory:
    path = write_transcript(directory, [
        typed("please review the pull request"),
        agent("Reviewing now."),
        tool_result("diff output"),
        enqueue("y"),
        queued("y"),
        agent("Approved item 1."),
    ])
    texts = user_texts(path)
    check("a message typed mid-turn is read from its queued_command attachment",
          texts == ["please review the pull request", "y"], texts)

with tempfile.TemporaryDirectory() as directory:
    path = write_transcript(directory, [
        typed("start"),
        queued("<cross-session-message from=\"peer\">hello</cross-session-message>", "peer"),
        queued("<task-notification>done</task-notification>", "task-notification"),
        agent("ok"),
    ])
    texts = user_texts(path)
    check("a queued_command attachment whose origin is not human is not the user's",
          texts == ["start"], texts)

with tempfile.TemporaryDirectory() as directory:
    path = write_transcript(directory, [
        typed("start"),
        queued("stop, another session is doing this"),
        interrupt_notice(),
        enqueue("stop, another session is doing this"),
        typed("stop, another session is doing this"),
        agent("Stopped."),
    ])
    texts = user_texts(path)
    check("a queued message the harness re-sends after an interrupt is read once",
          texts == ["start", "stop, another session is doing this"], texts)

with tempfile.TemporaryDirectory() as directory:
    path = write_transcript(directory, [
        typed("item 1?"),
        queued("y"),
        agent("Item 2?"),
        typed("y"),
        agent("Done."),
    ])
    texts = user_texts(path)
    check("the same words typed again after the agent answered are a second message",
          texts == ["item 1?", "y", "y"], texts)

with tempfile.TemporaryDirectory() as directory:
    path = write_transcript(directory, [
        typed("start"),
        queued("y"),
        agent("Item 2?"),
        interrupt_notice(),
        typed("y"),
    ])
    texts = user_texts(path)
    check("a re-send is matched only before the agent answers the queued message",
          texts == ["start", "y", "y"], texts)

with tempfile.TemporaryDirectory() as directory:
    write_transcript(directory, [
        typed("walk item 9?"),
        enqueue("y"),
        queued("y"),
        agent("Recorded."),
    ])
    run = subprocess.run(
        [sys.executable, str(SEARCH_SCRIPT), "--projects-dir", directory, "^y$"],
        capture_output=True, text=True)
    check("the command line finds a message typed mid-turn and exits 0",
          run.returncode == 0 and "USER: y" in run.stdout
          and "1 matching user message(s)" in run.stdout,
          f"exit {run.returncode}: {run.stdout}{run.stderr}")

print(f"{'FAILED' if failures else 'all cases passed'}: {len(failures)} failure(s)")
sys.exit(1 if failures else 0)
