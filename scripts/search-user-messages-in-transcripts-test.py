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

def typed_with(text, **fields):
    record = typed(text)
    record.update(fields)
    return record


with tempfile.TemporaryDirectory() as directory:
    path = write_transcript(directory, [
        typed_with("go on", origin={"kind": "human"}),
        typed_with("Another Claude session sent a message: done", origin={"kind": "peer"}),
        typed_with("<channel source=\"reviewer\">x</channel> trailing", origin={"kind": "channel"}),
        typed_with("<task-notification>x</task-notification> trailing", origin={"kind": "task-notification"}),
        typed_with("Stop hook feedback:\nrefused", isMeta=True),
        typed_with("Review this file for a range of defects.", entrypoint="sdk-cli"),
        typed_with("no origin field at all"),
        typed_with("origin is not a dict", origin=None),
        agent("ok"),
    ])
    texts = user_texts(path)
    check("a user turn whose origin is not human, or that is meta or a claude -p prompt, is not the user's",
          texts == ["go on", "no origin field at all"], texts)

with tempfile.TemporaryDirectory() as directory:
    path = write_transcript(directory, [
        typed_with("This session is being continued from a previous conversation that ran out of context."),
        typed_with("Read /h/.claude/handoffs/a-dialog-0002.md — the dialog from the session you are continuing, "
                   "written at 10:00", origin={"kind": "human"}),
        typed_with("Read /h/.claude/handoffs/a-dialog-0001.md — it is the dialog from the session you are "
                   "continuing", origin={"kind": "human"}),
        typed_with("Next step.\n\n(Recovered at supervisor boot: the previous session's conversation-tail is "
                   "unavailable; this next-step and the repository are your whole context.)",
                   origin={"kind": "human"}),
        typed_with("I said: Read the file — the dialog from the session you are continuing is long",
                   origin={"kind": "human"}),
    ])
    texts = user_texts(path)
    check("a compaction summary and a handoff successor's opening prompt are not the user's",
          texts == ["I said: Read the file — the dialog from the session you are continuing is long"], texts)

with tempfile.TemporaryDirectory() as directory:
    path = write_transcript(directory, [
        typed("start"),
        queued("y"),
        typed("y"),
    ])
    texts = user_texts(path)
    check("the same words typed right after a queued message, with no interrupt between, are a second message",
          texts == ["start", "y", "y"], texts)

_recover_spec = importlib.util.spec_from_file_location(
    "recover_crashed_seats", SEARCH_SCRIPT.with_name("recover-crashed-seats.py"))
recover_module = importlib.util.module_from_spec(_recover_spec)
_recover_spec.loader.exec_module(recover_module)
check("the handoff opener constants equal recover-crashed-seats.py's",
      (search_module.REINCARNATION_OPENER_MARKER, search_module.REINCARNATION_OPENER_PATTERN.pattern,
       search_module.IGNITION_WITHOUT_CONVERSATION_TAIL_MARKER)
      == (recover_module.REINCARNATION_OPENER_MARKER, recover_module.REINCARNATION_OPENER_PATTERN.pattern,
          recover_module.IGNITION_WITHOUT_CONVERSATION_TAIL_MARKER))

with tempfile.TemporaryDirectory() as directory:
    path = write_transcript(directory, [
        typed("start"),
        queued("stop"),
        interrupt_notice(),
        typed("stop"),
        agent("Stopped."),
    ])
    records = [json.loads(line) for line in path.read_text().splitlines()]
    whole = search_module.TurnReader()
    whole_turns = [whole.turn(record) for record in records]
    first_half = search_module.TurnReader()
    turns = [first_half.turn(record) for record in records[:3]]
    resumed = search_module.TurnReader(json.loads(json.dumps(first_half.state())))
    turns += [resumed.turn(record) for record in records[3:]]
    check("a reader resumed from its saved state reads the rest as one reader would",
          turns == whole_turns and [t for t in turns if t] == [("user", "start"), ("user", "stop"),
                                                                ("agent", "Stopped.")], turns)

print(f"{'FAILED' if failures else 'all cases passed'}: {len(failures)} failure(s)")
sys.exit(1 if failures else 0)
