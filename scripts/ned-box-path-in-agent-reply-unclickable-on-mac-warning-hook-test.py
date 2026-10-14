#!/usr/bin/env python3
"""Tests for ned-box-path-in-agent-reply-unclickable-on-mac-warning-hook.py.

Run: python3 scripts/ned-box-path-in-agent-reply-unclickable-on-mac-warning-hook-test.py
Prints one line per case and exits non-zero if any case fails.

The scanner's cases call unopenable_paths_in() directly. The hook's cases
call run() in this process with on_ned_box given, so they pass on either
machine, against transcripts written under a temporary directory; the fault
cases run the hook as Claude Code does, as a subprocess reading a payload on
stdin. The hook keeps its record of noted replies under the temporary
directory, which this file points at a directory of its own.
"""

import atexit
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HOOK_PATH = Path(__file__).resolve().with_name(
    "ned-box-path-in-agent-reply-unclickable-on-mac-warning-hook.py")
_specification = importlib.util.spec_from_file_location(
    "ned_box_path_in_agent_reply_unclickable_on_mac_warning_hook", HOOK_PATH)
hook = importlib.util.module_from_spec(_specification)
_specification.loader.exec_module(hook)

SCRATCH = Path(tempfile.mkdtemp(prefix="ned-box-path-in-agent-reply-unclickable-on-mac-warning-hook-test-"))
atexit.register(shutil.rmtree, str(SCRATCH), True)
RECORD_TEMPORARY_DIRECTORY = SCRATCH / "temporary"
RECORD_TEMPORARY_DIRECTORY.mkdir()
tempfile.tempdir = str(RECORD_TEMPORARY_DIRECTORY)

# An attended session, as an agent-seat's own is.
ATTENDED = {"CLAUDE_CODE_SESSION_ATTENDED": "1"}

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def replacements_in(text):
    return [path.replacement for path in hook.unopenable_paths_in(text)]


# --- The scanner -------------------------------------------------------------

LOG_STORE_LINK = ("[nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/x-minutes.md]"
                  "(file:///Volumes/nedhome/nedschorus-logs/walk/x-minutes.md)")

found = replacements_in("The minutes are at /home/nedlern/nedschorus-logs/walk/x-minutes.md.")
check("a bare log-store path is noted, with the scp citation as the suggested link's text",
      found == [LOG_STORE_LINK], found)

found = replacements_in("See /home/nedlern/agents/merge-lane-2/report.md for the list.")
check("a bare path outside the log-store is noted, with the path as the suggested link's text",
      found == ["[/home/nedlern/agents/merge-lane-2/report.md]"
                "(file:///Volumes/nedhome/agents/merge-lane-2/report.md)"], found)

found = replacements_in("Read [the minutes](/home/nedlern/nedschorus-logs/walk/x-minutes.md) first.")
check("a link whose target is a /home/nedlern/ path is noted, keeping the link text",
      found == ["[the minutes](file:///Volumes/nedhome/nedschorus-logs/walk/x-minutes.md)"], found)

found = replacements_in("Read [nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/x-minutes.md]"
                        "(file:///home/nedlern/nedschorus-logs/walk/x-minutes.md).")
check("a link whose target is a file:///home/nedlern/ URL is noted once, for its target",
      found == [LOG_STORE_LINK], found)

found = replacements_in("Open <file:///home/nedlern/agents/a/b.md> or file://localhost/home/nedlern/c.md.")
check("bare and angle-bracketed file:///home/nedlern/ URLs are noted",
      found == ["[/home/nedlern/agents/a/b.md](file:///Volumes/nedhome/agents/a/b.md)",
                "[/home/nedlern/c.md](file:///Volumes/nedhome/c.md)"], found)

found = replacements_in("The minutes: " + LOG_STORE_LINK + ".")
check("an scp-form citation linked to its /Volumes/nedhome file is not noted", found == [], found)

found = replacements_in("Cited as nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/x-minutes.md, "
                        "or ned-box:/home/nedlern/nedschorus-logs/y.md.")
check("an scp-form citation as plain text is not noted", found == [], found)

found = replacements_in("Open [the report](file:///Volumes/nedhome/agents/a/report.md).")
check("a link to a /Volumes/nedhome file is not noted", found == [], found)

found = replacements_in("Run `ssh nedlern@ned-box cat /home/nedlern/nedschorus-logs/x.md` to see it, "
                        "or `ls /home/nedlern/agents`.")
check("a command in a code span is not noted", found == [], found)

found = replacements_in("Run this on ned-box:\n\n```\ncat /home/nedlern/nedschorus-logs/x.md\n```\n"
                        "~~~sh\nls file:///home/nedlern/y\n~~~\n")
check("a path in a fenced code block is not noted", found == [], found)

found = replacements_in("The report is `/home/nedlern/agents/a/report.md`.")
check("a code span holding only a path is noted",
      found == ["[/home/nedlern/agents/a/report.md](file:///Volumes/nedhome/agents/a/report.md)"], found)

found = replacements_in("The link `nedlern@ned-box:/home/nedlern/nedschorus-logs/x.md` is the scp form.")
check("a code span holding only the scp form is not noted", found == [], found)

found = replacements_in("Paths /home/nedlern/a.md and /home/nedlern/a.md, again (/home/nedlern/a.md).")
check("a path repeated in a reply is listed once, without the sentence's punctuation",
      found == ["[/home/nedlern/a.md](file:///Volumes/nedhome/a.md)"], found)

found = replacements_in("Not /Volumes/nedhome/a.md, not https://example.com/home/nedlern/a, "
                        "not ~/home/nedlern/a, and not /homes/nedlern/a.")
check("text that only resembles a /home/nedlern/ path is not noted", found == [], found)

found = hook.unopenable_paths_in("Open file://localhost/home/nedlern/c.md.")
check("a bare file URL is quoted without the sentence's punctuation",
      [path.written for path in found] == ["file://localhost/home/nedlern/c.md"],
      [path.written for path in found])

found = hook.unopenable_paths_in("See /home/nedlern/a.md now.")
check("each noted path carries what the reply wrote and an excerpt around it",
      len(found) == 1 and found[0].written == "/home/nedlern/a.md"
      and found[0].excerpt == "See /home/nedlern/a.md now.",
      [(path.written, path.excerpt) for path in found])


# --- The hook, by run() --------------------------------------------------------

def transcript(*records):
    path = SCRATCH / f"transcript-{len(list(SCRATCH.glob('transcript-*')))}.jsonl"
    with open(path, "w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record) + "\n")
    return path


def user(text):
    return {"type": "user", "message": {"role": "user", "content": text}}


def assistant(message_id, text):
    return {"type": "assistant", "message": {"id": message_id, "role": "assistant",
                                             "content": [{"type": "text", "text": text}]}}


SESSION_NUMBERS = iter(range(1, 10 ** 6))


def prompt_payload(path, session_id=None):
    return {"hook_event_name": "UserPromptSubmit", "transcript_path": str(path),
            "session_id": session_id or f"session-{next(SESSION_NUMBERS)}", "prompt": "next"}


def note_of(output):
    if output is None:
        return ""
    return json.loads(output)["hookSpecificOutput"]["additionalContext"]


FLAGGED_REPLY = transcript(user("where is it?"),
                           assistant("m1", "It is at /home/nedlern/nedschorus-logs/walk/x-minutes.md."))

output = hook.run(json.dumps(prompt_payload(FLAGGED_REPLY)), ATTENDED, on_ned_box=True)
note = note_of(output)
check("on ned-box, a reply with a /home/nedlern/ path gets a UserPromptSubmit note",
      output is not None and json.loads(output)["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
      and "showed 1 path(s) under /home/nedlern/" in note, output)
check("the note shows the /Volumes/nedhome link to write",
      '"/home/nedlern/nedschorus-logs/walk/x-minutes.md" in "It is at' in note
      and "write " + LOG_STORE_LINK in note, note)
check("the note never blocks the prompt", "decision" not in json.loads(output or "{}"), output)

output = hook.run(json.dumps(prompt_payload(FLAGGED_REPLY)), ATTENDED, on_ned_box=False)
check("off ned-box the hook is silent", output is None, output)

for variable, value in (("NEDSCHORUS_SESSION_REINCARNATION_OWNED_BY_CALLER", "1"),
                        ("CLAUDE_CODE_SESSION_ATTENDED", "0")):
    output = hook.run(json.dumps(prompt_payload(FLAGGED_REPLY)), {variable: value}, on_ned_box=True)
    check(f"a headless child ({variable}={value}) gets no note", output is None, output)

output = hook.run(json.dumps(prompt_payload(transcript(
    user("where?"), assistant("m1", "It is " + LOG_STORE_LINK + ".")))), ATTENDED, on_ned_box=True)
check("a reply with only openable links gets no note", output is None, output)

output = hook.run(json.dumps(prompt_payload(SCRATCH / "no-such-transcript.jsonl")), ATTENDED, on_ned_box=True)
check("a transcript not yet written means no previous reply, and no note", output is None, output)

output = hook.run(json.dumps({"hook_event_name": "PostToolUse"}), ATTENDED, on_ned_box=True)
check("an event other than UserPromptSubmit is ignored", output is None, output)

many = " ".join(f"/home/nedlern/f{index}.md" for index in range(hook.HIT_LINES_LISTED_AT_MOST + 3))
note = note_of(hook.run(json.dumps(prompt_payload(transcript(user("list?"), assistant("m1", many)))),
                        ATTENDED, on_ned_box=True))
check("at most HIT_LINES_LISTED_AT_MOST paths are listed, and the rest counted",
      note.count("file:///Volumes/nedhome/f") == hook.HIT_LINES_LISTED_AT_MOST
      and "3 more not listed" in note, note)

session = "session-once"
first = hook.run(json.dumps(prompt_payload(FLAGGED_REPLY, session)), ATTENDED, on_ned_box=True)
second = hook.run(json.dumps(prompt_payload(FLAGGED_REPLY, session)), ATTENDED, on_ned_box=True)
check("a reply is noted once per agent-session, not again at the next prompt",
      first is not None and second is None, (first, second))

# A file where the record's directory belongs makes the record unwritable.
blocked_temporary = SCRATCH / "blocked-temporary"
blocked_temporary.mkdir()
(blocked_temporary / hook.NOTE_RECORD_DIRECTORY_NAME).write_text("not a directory", encoding="utf-8")
tempfile.tempdir = str(blocked_temporary)
note = note_of(hook.run(json.dumps(prompt_payload(FLAGGED_REPLY)), ATTENDED, on_ned_box=True))
tempfile.tempdir = str(RECORD_TEMPORARY_DIRECTORY)
check("a record that cannot be written keeps the note and adds one line saying so",
      "showed 1 path(s)" in note and note.count("could not be written") == 1, note)

unreadable_session = "session-unreadable-record"
record_path = hook.note_record_path_for(unreadable_session)
record_path.parent.mkdir(parents=True, exist_ok=True)
record_path.write_text("{not json", encoding="utf-8")
note = note_of(hook.run(json.dumps(prompt_payload(FLAGGED_REPLY, unreadable_session)), ATTENDED, on_ned_box=True))
check("a record that cannot be read keeps the note and adds one line saying so",
      "showed 1 path(s)" in note and note.count("could not be read") == 1, note)


# --- The hook, as a subprocess -------------------------------------------------

def run_hook(stdin_text):
    environment = {**os.environ, **ATTENDED, "TMPDIR": str(RECORD_TEMPORARY_DIRECTORY)}
    environment.pop("NEDSCHORUS_SESSION_REINCARNATION_OWNED_BY_CALLER", None)
    return subprocess.run([sys.executable, str(HOOK_PATH)], input=stdin_text, capture_output=True,
                          text=True, timeout=60, env=environment)


this_machine_is_ned_box = hook.daily_memory_review_mark().this_machine_is_ned_box()
result = run_hook(json.dumps(prompt_payload(FLAGGED_REPLY)))
check("as a subprocess, the hook notes the reply on ned-box and is silent elsewhere "
      f"(this machine is {'ned-box' if this_machine_is_ned_box else 'not ned-box'})",
      result.returncode == 0 and result.stderr == ""
      and ("showed 1 path(s)" in result.stdout) == this_machine_is_ned_box,
      (result.returncode, result.stdout, result.stderr))


result = run_hook("not json")
check("a payload that is not JSON is a fault: one line on stderr, nothing on stdout, exit 1",
      result.returncode == 1 and result.stdout == ""
      and result.stderr.startswith(hook.PROGRAM + ": no check was made: JSONDecodeError")
      and len(result.stderr.strip().splitlines()) == 1, (result.returncode, result.stdout, result.stderr))

result = run_hook(json.dumps({"hook_event_name": "Stop"}))
check("as a subprocess, a payload with nothing to check prints nothing and exits 0",
      result.returncode == 0 and result.stdout == "" and result.stderr == "",
      (result.returncode, result.stdout, result.stderr))

try:
    hook.run(json.dumps(prompt_payload(SCRATCH)), ATTENDED, on_ned_box=True)
    raised = None
except OSError as error:
    raised = error
check("a transcript that cannot be read raises to main(), which reports it as a fault",
      raised is not None, raised)


if failures:
    print(f"\n{len(failures)} case(s) failed")
    sys.exit(1)
print("\nAll cases passed.")
