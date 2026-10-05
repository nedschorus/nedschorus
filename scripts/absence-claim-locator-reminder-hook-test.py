#!/usr/bin/env python3
"""Cases for the Stop and SubagentStop hook that reminds an agent to run the
locator after it says a file is gone.

Every hook case runs the hook as a subprocess, its real stdin-to-stdout path,
with the log file and the once-per-session marker directory pointed into a
directory this suite made, so no case writes the live log-store or
~/.local/state/claude. The exit code is asserted on every case: a Stop hook
that exits 2 blocks the turn from ending, so "always 0" is a property.

The precision case reads the labelled replies the trigger was measured on,
which stay in the log-store because they are transcript text and this
repository is public. Where that file is absent, as on the Mac, the case
prints a SKIP line.
"""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HOOK_SCRIPT = Path(__file__).with_name("absence-claim-locator-reminder-hook.py")
LABELLED_REPLIES = Path(
    "/home/nedlern/nedschorus-logs/seats/ned-box-helper/"
    "absence-claim-trigger-phrases-2026-10-05/out/precision/labels.csv")
EXPECTED_PRECISION_LINE = "fires 107: correct 88, incorrect 19, unclear 0; precision 0.8224"
B01_CLAIM = "The transcripts it points to are gone."
REMINDER_FOR_B01 = (
    "absence-claim reminder: your reply says a file or record is gone, missing "
    "or cannot be found (\"are gone\"), and you have not run the locator this "
    "turn. Files agents call missing are often in another checkout, the "
    "log-store, a transcript or a backup.\n"
    "Before you tell anyone it does not exist, run: python3 "
    "scripts/locate-file-copies-across-machines.py <the file's name>\n"
    "If the locator finds it, tell whoever read your reply that it is not "
    "missing, and where it is.\n"
    "If the locator finds nothing, say where you looked, not that the file "
    "does not exist.\n"
    "If your reply was not about a stored file or record, carry on; this "
    "reminder comes once per session."
)

failures = []
SUITE_ROOT = Path(tempfile.mkdtemp(prefix="absence-claim-locator-reminder-test-"))


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


class Case:
    """One case's own transcript, log file and marker directory."""

    counter = 0

    def __init__(self):
        Case.counter += 1
        self.root = SUITE_ROOT / f"case-{Case.counter}"
        self.root.mkdir()
        self.log = self.root / "fires.jsonl"
        self.state = self.root / "state"
        self.transcript = self.root / "transcript.jsonl"
        self.records = []

    def user(self, text):
        self.records.append({"type": "user", "message": {"role": "user", "content": text}})
        return self

    def assistant_text(self, text, message_id=None):
        Case.counter += 1
        self.records.append({"type": "assistant", "message": {
            "id": message_id or f"msg_{Case.counter}", "role": "assistant",
            "content": [{"type": "text", "text": text}]}})
        return self

    def tool_use(self, name, tool_input):
        Case.counter += 1
        self.records.append({"type": "assistant", "message": {
            "id": f"msg_{Case.counter}", "role": "assistant",
            "content": [{"type": "tool_use", "id": f"toolu_{Case.counter}",
                         "name": name, "input": tool_input}]}})
        self.records.append({"type": "user", "message": {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": f"toolu_{Case.counter}",
             "content": "ok"}]}})
        return self

    def write(self):
        self.transcript.write_text(
            "".join(json.dumps(record) + "\n" for record in self.records))
        return self

    def environment(self, **overrides):
        environment = dict(os.environ)
        environment.pop("NEDSCHORUS_SESSION_REINCARNATION_OWNED_BY_CALLER", None)
        environment["CLAUDE_CODE_SESSION_ATTENDED"] = "1"
        environment["HOME"] = str(self.root / "home")
        environment["NEDSCHORUS_ABSENCE_CLAIM_REMINDER_LOG"] = str(self.log)
        environment["NEDSCHORUS_ABSENCE_CLAIM_REMINDER_STATE_DIRECTORY"] = str(self.state)
        environment.update(overrides)
        return environment

    def run(self, payload=None, stdin_text=None, **environment_overrides):
        if stdin_text is None:
            stop_payload = {"session_id": "session-one", "hook_event_name": "Stop",
                            "transcript_path": str(self.transcript), "cwd": "/",
                            "stop_hook_active": False}
            stop_payload.update(payload or {})
            stdin_text = json.dumps(stop_payload)
        return subprocess.run([sys.executable, str(HOOK_SCRIPT)], input=stdin_text,
                              capture_output=True, text=True,
                              env=self.environment(**environment_overrides), timeout=60)

    def log_lines(self):
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text().splitlines()]


def blocked_reason(result):
    try:
        output = json.loads(result.stdout)
    except ValueError:
        return None
    return output.get("reason") if output.get("decision") == "block" else None


# --- the trigger, on the labelled replies it was measured on ----------------

if LABELLED_REPLIES.exists():
    result = subprocess.run([sys.executable, str(HOOK_SCRIPT), "--measure-precision",
                             str(LABELLED_REPLIES)], capture_output=True, text=True,
                            timeout=600)
    check("labelled replies: the measured fires and precision, unchanged",
          result.returncode == 0 and result.stdout.strip() == EXPECTED_PRECISION_LINE,
          (result.returncode, result.stdout, result.stderr))
else:
    print(f"SKIP  labelled-reply precision: {LABELLED_REPLIES} is not on this machine")

# --- the trigger, phrase by phrase --------------------------------------------

_hook_spec = importlib.util.spec_from_file_location("absence_claim_locator_reminder_hook",
                                                    HOOK_SCRIPT)
hook = importlib.util.module_from_spec(_hook_spec)
_hook_spec.loader.exec_module(hook)

for case_name, text in [
    ("B01's claim fires", B01_CLAIM),
    ("B02's claim fires", "The exact phrase isn't in the mirror."),
    ("B03's claim fires", 'I did not locate your "y" to item 5 itself or to item 2, and the review says so.'),
    ("no reply in between fires", "There was no reply from you in between those two messages."),
    ("a ruling never given fires", "That item rests on a ruling you never gave."),
]:
    check(f"trigger: {case_name}", bool(hook.absence_claim_matches(text)), text)

for case_name, text in [
    ("processes gone are not files", "The child processes are gone now, so the file lock is free."),
    ("a denied loss", "In the worst case no report is lost, because the copy is written first."),
    ("unresolved alternatives", "Either the file is missing or its content differs; I did not check which."),
    ("information, not an artifact", "I did not find out which run wrote the recordings in the store."),
    ("a condition", "If the file is missing, the program exits 1."),
    ("a modal", "The worker could be killed and the file is gone afterwards."),
    ("until", "Until the merge, the file is missing on main."),
    ("a quotation", 'The test prints "the file is gone" when the fixture is empty.'),
    ("a code block", "The output was:\n```\nthe transcript is gone\n```\nThat is the expected text."),
    ("an inline code span", "The message `transcripts are gone` is now printed in full."),
    ("a block quote", "> The transcripts it points to are gone.\nThat claim was wrong."),
    ("a scoring reply", "The report covers finding 3: the file is missing from the match file."),
    ("someone else's 'does not say'", "The log does not say the file is gone; it says the copy failed."),
    ("plain status", "All tests pass and the pull request is merged."),
    ("a name missing from a list", "That file name is missing from the list of exceptions."),
    ("a program not finding a binary", "The service did not find the git binary."),
    ("not saying it is gone", "I am not saying the transcript is gone."),
    ("before saying it is gone", "I ran the locator before saying the transcript is gone."),
    ("a glossary entry", "The glossary file is missing an entry for that term."),
    ("nothing is lost", "Nothing in the record is lost by the rename."),
]:
    check(f"trigger: silent on {case_name}", not hook.absence_claim_matches(text),
          hook.absence_claim_matches(text))

# --- reminds once, with the exact text ----------------------------------------

case = Case().user("Where are the transcripts?").assistant_text(B01_CLAIM).write()
first = case.run()
check("first claim: exit 0", first.returncode == 0, first.returncode)
check("first claim: blocks with the exact reminder",
      blocked_reason(first) == REMINDER_FOR_B01, first.stdout)
second = case.run()
check("second claim in the same session: exit 0, silent",
      second.returncode == 0 and second.stdout == "", (second.returncode, second.stdout))
lines = case.log_lines()
check("both claims are logged, as reminded then already_reminded",
      [line.get("outcome") for line in lines] == ["reminded", "already_reminded"], lines)
check("the log line carries the event, session, matched phrase and reply",
      lines and lines[0].get("event") == "Stop" and lines[0].get("session_id") == "session-one"
      and lines[0].get("matches") == [{"pattern": 2, "phrase": "are gone"}]
      and lines[0].get("reply") == B01_CLAIM and "time" in lines[0], lines[:1])
other_session = case.run({"session_id": "session-two"})
check("another session is reminded on its own",
      blocked_reason(other_session) == REMINDER_FOR_B01, other_session.stdout)

# --- silent when the locator ran this turn ------------------------------------

case = (Case().user("Where are the transcripts?")
        .tool_use("Bash", {"command": "python3 scripts/locate-file-copies-across-machines.py 21dc3d71.jsonl"})
        .assistant_text(B01_CLAIM).write())
result = case.run()
check("locator ran this turn: exit 0, silent",
      result.returncode == 0 and result.stdout == "", (result.returncode, result.stdout))
check("locator ran this turn: logged as locator_ran",
      [line.get("outcome") for line in case.log_lines()] == ["locator_ran"], case.log_lines())

case = (Case().user("Where are the transcripts?")
        .tool_use("Skill", {"skill": "locate-before-saying-a-file-is-missing"})
        .assistant_text(B01_CLAIM).write())
result = case.run()
check("the skill invoked this turn: silent", result.stdout == "", result.stdout)

case = (Case().user("Where are the transcripts?")
        .tool_use("Bash", {"command": "python3 scripts/locate-file-copies-across-machines.py x.jsonl"})
        .assistant_text("It found nothing for x.jsonl.")
        .user("And the other ones?").assistant_text(B01_CLAIM).write())
result = case.run()
check("the locator ran in an earlier turn only: reminded",
      blocked_reason(result) == REMINDER_FOR_B01, result.stdout)

# --- only the last reply of the turn counts ------------------------------------

case = (Case().user("Where are the transcripts?").assistant_text(B01_CLAIM)
        .tool_use("Bash", {"command": "ls /tmp"})
        .assistant_text("Found them under /tmp after all.").write())
result = case.run()
check("a claim the agent moved past within the turn: silent, nothing logged",
      result.stdout == "" and case.log_lines() == [], (result.stdout, case.log_lines()))

case = Case().user("Status?").assistant_text("All tests pass.").write()
result = case.run()
check("no claim: exit 0, silent, nothing logged",
      result.returncode == 0 and result.stdout == "" and case.log_lines() == [],
      (result.returncode, result.stdout, case.log_lines()))

# --- stop_hook_active, headless sessions ---------------------------------------

case = Case().user("Where are the transcripts?").assistant_text(B01_CLAIM).write()
result = case.run({"stop_hook_active": True})
check("stop_hook_active: exit 0, silent, nothing logged",
      result.returncode == 0 and result.stdout == "" and case.log_lines() == [],
      (result.returncode, result.stdout, case.log_lines()))

case = Case().user("Where are the transcripts?").assistant_text(B01_CLAIM).write()
result = case.run(CLAUDE_CODE_SESSION_ATTENDED="0")
check("a headless claude -p child: silent, logged as headless",
      result.stdout == "" and [line.get("outcome") for line in case.log_lines()] == ["headless"],
      (result.stdout, case.log_lines()))
result = case.run(NEDSCHORUS_SESSION_REINCARNATION_OWNED_BY_CALLER="1")
check("a session its caller owns: silent", result.stdout == "", result.stdout)

# --- subagents -------------------------------------------------------------------

case = Case().user("Find issue 80's transcripts.").assistant_text(B01_CLAIM).write()
subagent_payload = {"hook_event_name": "SubagentStop", "agent_id": "agent-one",
                    "transcript_path": "/nonexistent-parent.jsonl",
                    "agent_transcript_path": str(case.transcript)}
result = case.run(subagent_payload)
check("a subagent's claim: reminded, read from agent_transcript_path",
      result.returncode == 0 and blocked_reason(result) == REMINDER_FOR_B01, result.stdout)
check("a subagent's claim: logged with its event and agent",
      [(line.get("event"), line.get("agent_id")) for line in case.log_lines()]
      == [("SubagentStop", "agent-one")], case.log_lines())
result = case.run(dict(subagent_payload, agent_id="agent-two"))
check("another subagent in the same session is reminded on its own",
      blocked_reason(result) == REMINDER_FOR_B01, result.stdout)
result = case.run({"hook_event_name": "SubagentStop", "agent_id": "agent-three",
                   "transcript_path": str(case.transcript)})
check("a SubagentStop without agent_transcript_path: silent", result.stdout == "", result.stdout)

# --- faults: exit 0, nothing printed, the error logged -----------------------------

case = Case()
result = case.run({"transcript_path": str(case.root / "no-such-transcript.jsonl")})
check("a missing transcript: exit 0, nothing printed",
      result.returncode == 0 and result.stdout == "" and result.stderr == "",
      (result.returncode, result.stdout, result.stderr))
check("a missing transcript: the error is logged",
      [line.get("outcome") for line in case.log_lines()] == ["error"]
      and "FileNotFoundError" in case.log_lines()[0].get("error", ""), case.log_lines())

case = Case()
result = case.run(stdin_text="not json")
check("stdin that is not JSON: exit 0, nothing printed, error logged",
      result.returncode == 0 and result.stdout == "" and result.stderr == ""
      and [line.get("outcome") for line in case.log_lines()] == ["error"],
      (result.returncode, result.stdout, result.stderr, case.log_lines()))

case = Case().user("Where are the transcripts?").assistant_text(B01_CLAIM).write()
case.log.mkdir()
result = case.run()
check("a log path that cannot be written: still reminds, exit 0",
      result.returncode == 0 and blocked_reason(result) == REMINDER_FOR_B01,
      (result.returncode, result.stdout))

shutil.rmtree(SUITE_ROOT, ignore_errors=True)
print()
if failures:
    print(f"{len(failures)} FAILED: {failures}")
    sys.exit(1)
print("all cases passed")
