#!/usr/bin/env python3
"""Cases for the Stop hook that reminds an agent to check a system's status
with a command before it states that status to the user.

Every case runs the hook as a subprocess, its real stdin-to-stdout path, on a
transcript this suite writes. The exit code is asserted on every case: the
hook exits 0, or 1 with one stderr line on a fault, and never 2, which would
keep the turn from ending.

Run: python3 scripts/agent-reply-possibly-stale-system-status-claim-recheck-reminder-hook-test.py
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HOOK_NAME = "agent-reply-possibly-stale-system-status-claim-recheck-reminder-hook"
HOOK_SCRIPT = Path(__file__).with_name(f"{HOOK_NAME}.py")
CLAIM = "Task #421 is still on hold because cold-read-research is offline."
# Each line the agent must act on, so that deleting or rewording one fails a case.
REMINDER_LINES = [
    "[rule agent-reply-system-status-claim-recheck-with-a-command-before-stating-it] system-status reminder: "
    "your last reply states the current status of something outside this conversation (\"still on hold\", "
    "\"offline\"), and no Bash command, SendMessage or ListAgents call in this turn checked it.",
    "If the reply states a status you did not check in this turn: check it now with a command, such as "
    "`claude auth status` for the login on this machine, `tmux -L <agent-seat> ls` on the agent-seat's machine, "
    "or the ListAgents tool for an agent-seat you would message. Then tell the user, in one line, what the "
    "command showed and the time you ran it, correcting your reply where it was wrong.",
    "If you hold work, such as a task, waiting on that status: start the work once the check shows the wait is "
    "over.",
    "If the matched words state no current status, as in a plan, a quotation or a description of what a "
    "program does: carry on, and do not mention this reminder.",
    "From now on, check a status with a command in the same turn before you state it to the user, and say when "
    "you checked it.",
]
# The hook runs at every Stop, so it must not add a noticeable delay; a Python start-up takes about a tenth of this.
MOST_SECONDS_A_STOP_MAY_TAKE = 1.0

failures = []
SUITE_ROOT = Path(tempfile.mkdtemp(prefix="system-status-claim-recheck-reminder-test-"))


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


class Case:
    counter = 0

    def __init__(self):
        Case.counter += 1
        self.root = SUITE_ROOT / f"case-{Case.counter}"
        self.root.mkdir()
        self.transcript = self.root / "transcript.jsonl"
        self.records = []

    def user(self, text):
        self.records.append({"type": "user", "message": {"role": "user", "content": text}})
        return self

    def assistant_text(self, text):
        Case.counter += 1
        self.records.append({"type": "assistant", "message": {
            "id": f"msg_{Case.counter}", "role": "assistant", "content": [{"type": "text", "text": text}]}})
        return self

    def tool_use(self, name, tool_input):
        Case.counter += 1
        self.records.append({"type": "assistant", "message": {
            "id": f"msg_{Case.counter}", "role": "assistant",
            "content": [{"type": "tool_use", "id": f"toolu_{Case.counter}", "name": name, "input": tool_input}]}})
        self.records.append({"type": "user", "message": {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": f"toolu_{Case.counter}", "content": "ok"}]}})
        return self

    def write(self):
        self.transcript.write_text("".join(json.dumps(record) + "\n" for record in self.records))
        return self

    def run(self, payload=None, stdin_text=None, **environment_overrides):
        if stdin_text is None:
            stop_payload = {"session_id": "session-one", "hook_event_name": "Stop",
                            "transcript_path": str(self.transcript), "cwd": "/", "stop_hook_active": False}
            stop_payload.update(payload or {})
            stdin_text = json.dumps(stop_payload)
        environment = dict(os.environ)
        environment.pop("NEDSNODES_SESSION_REINCARNATION_OWNED_BY_CALLER", None)
        environment["CLAUDE_CODE_SESSION_ATTENDED"] = "1"
        environment.update(environment_overrides)
        return subprocess.run([sys.executable, str(HOOK_SCRIPT)], input=stdin_text, capture_output=True,
                              text=True, env=environment, timeout=60)


def reminder(result):
    """The additionalContext of a reminder at exit 0 with no decision and no systemMessage, else None."""
    if result.returncode != 0:
        return None
    try:
        output = json.loads(result.stdout)
    except ValueError:
        return None
    if "decision" in output or "systemMessage" in output:
        return None
    specific = output.get("hookSpecificOutput") or {}
    return specific.get("additionalContext") if specific.get("hookEventName") == "Stop" else None


def silent(result):
    return result.returncode == 0 and result.stdout == "" and result.stderr == ""


def fault_reported(result, fault_words):
    lines = result.stderr.splitlines()
    return (result.returncode == 1 and result.stdout == "" and len(lines) == 1
            and lines[0].startswith(f"{HOOK_NAME}: the hook failed with ") and fault_words in lines[0])


try:
    # A claim with no check in the turn: the reminder, which never blocks.
    case = Case().user("where are we?").tool_use("Read", {"file_path": "/x/handoff.md"}).assistant_text(CLAIM).write()
    started = time.monotonic()
    result = case.run()
    elapsed = time.monotonic() - started
    text = reminder(result)
    check("an unchecked claim: a non-blocking reminder holding each line the agent acts on",
          text is not None and all(line in text for line in REMINDER_LINES), (result.stdout, result.stderr))
    check(f"an unchecked claim: the hook ends within {MOST_SECONDS_A_STOP_MAY_TAKE} s",
          elapsed < MOST_SECONDS_A_STOP_MAY_TAKE, elapsed)

    # A check ran in the same turn: silent, for each tool that can look at a status.
    for tool, tool_input in (("Bash", {"command": "tmux -L cold-read-research ls"}),
                             ("SendMessage", {"to": "cold-read-research", "message": "are you there?"}),
                             ("ListAgents", {})):
        case = Case().user("where are we?").tool_use(tool, tool_input).assistant_text(CLAIM).write()
        check(f"a {tool} call in the turn: silent", silent(case.run()))

    # A check in an earlier turn does not count for this one.
    case = (Case().user("first").tool_use("Bash", {"command": "tmux ls"}).assistant_text("checked")
            .user("and now?").assistant_text(CLAIM).write())
    check("a check only in an earlier turn: the reminder", reminder(case.run()) is not None)

    # Ordinary progress talk: silent.
    for words in ("The tests are still running.", "I wrote the report to docs/walk/report.md."):
        case = Case().user("go").assistant_text(words).write()
        check(f"progress talk {words!r}: silent", silent(case.run()))
    case = Case().user("go").tool_use("Bash", {"command": "pytest &"}).assistant_text(
        "The tests are still running.").write()
    check("tests started this turn and said to be running: silent", silent(case.run()))

    # Only the last reply counts.
    case = Case().user("go").assistant_text(CLAIM).assistant_text("Done with the edit.").write()
    check("a claim in an earlier message of the turn but not the last reply: silent", silent(case.run()))

    # The agent is answering a Stop hook's output: silent.
    case = Case().user("go").assistant_text(CLAIM).write()
    check("stop_hook_active true: silent", silent(case.run({"stop_hook_active": True})))

    # No user attends: silent.
    case = Case().user("go").assistant_text(CLAIM).write()
    check("a headless agent-session: silent", silent(case.run(CLAUDE_CODE_SESSION_ATTENDED="0")))

    # No transcript named, or none on disk: silent.
    case = Case()
    check("no transcript_path: silent", silent(case.run({"transcript_path": None})))
    check("a transcript that does not exist: silent", silent(case.run({"transcript_path": str(case.root / "none")})))

    # Faults: one stderr line, exit 1, nothing on stdout.
    case = Case()
    check("stdin not JSON: the fault reported, exit 1", fault_reported(case.run(stdin_text="not json"), "JSONDecodeError"))
    check("stdin a JSON list: the fault reported, exit 1",
          fault_reported(case.run(stdin_text="[1]"), "not an object"))
    unreadable = Case().user("go").assistant_text(CLAIM).write()
    unreadable.transcript.chmod(0)
    if os.access(unreadable.transcript, os.R_OK):
        print("SKIP  an unreadable transcript: this user can read a file with mode 0, as root can")
    else:
        check("an unreadable transcript: the fault reported, exit 1",
              fault_reported(unreadable.run(), "PermissionError"))
    unreadable.transcript.chmod(0o600)
finally:
    shutil.rmtree(SUITE_ROOT, ignore_errors=True)

print(f"{len(failures)} failure(s)" if failures else "all cases pass")
sys.exit(1 if failures else 0)
