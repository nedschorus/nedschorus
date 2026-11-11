#!/usr/bin/env python3
"""Cases for scripts/agent-seat-idle-sweep-headless-judge-wake-messages-send-and-user-alerts-write.py.

Every case runs the program as a subprocess against folders this suite made, never the real ones:
a handoff directory, agents, projects and tasks roots, a ~/.claude.json, a log file, a state
directory and HOME, under which user-alerts are written. `claude` is a fake placed first on PATH:
it answers each call with the next scripted answer, as stream-json, and records the call's
arguments and prompt. `gh` is never reached: no case gives a task prerequisites. Each invocation
fixes the time with --now.
"""

import atexit
import fcntl
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROGRAM = Path(__file__).with_name(
    "agent-seat-idle-sweep-headless-judge-wake-messages-send-and-user-alerts-write.py")
START = datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)
LONG_AGO = "2026-11-02T11:50:00Z"

FAKE_CLAUDE = r'''#!{python}
import json, os, sys, time
prompt = sys.stdin.read()
calls_path = os.environ["FAKE_CLAUDE_CALLS"]
calls = open(calls_path).read().splitlines() if os.path.exists(calls_path) else []
with open(calls_path, "a") as stream:
    stream.write(json.dumps({{"argv": sys.argv[1:], "prompt": prompt}}) + "\n")
answers = json.load(open(os.environ["FAKE_CLAUDE_ANSWERS"]))
answer = answers[len(calls)] if len(calls) < len(answers) else {{"exit": 3}}
if answer.get("child"):
    import subprocess
    subprocess.Popen(["sleep", str(answer["child"])])
time.sleep(answer.get("sleep", 0))
def emit(event):
    print(json.dumps(event), flush=True)
text = prompt.split("----------\n", 1)[-1].rsplit("\n----------", 1)[0]
for number, send in enumerate(answer.get("sends", [])):
    message = text if send.get("message") == "@prompt-text" else send.get("message", "")
    emit({{"type": "assistant", "message": {{"content": [
        {{"type": "tool_use", "id": f"t{{number}}", "name": "SendMessage",
         "input": {{"to": send["to"], "message": message}}}}]}}}})
    emit({{"type": "user", "message": {{"content": [
        {{"type": "tool_result", "tool_use_id": f"t{{number}}", "content": "sent",
         "is_error": send.get("is_error", False)}}]}}}})
sys.stderr.write(answer.get("stderr", ""))
sys.stderr.flush()
if answer.get("garbage"):
    print(answer.get("garbage") if isinstance(answer["garbage"], str) else "not json")
if answer.get("garbage_then_result") or not answer.get("garbage"):
    if "result" in answer:
        emit(dict({{"type": "result"}}, **answer["result"]))
    elif "answer" in answer:
        emit({{"type": "result", "subtype": "success", "is_error": False,
              "structured_output": answer["answer"]}})
if answer.get("signal"):
    import signal
    os.kill(os.getpid(), signal.SIGTERM)
sys.exit(answer.get("exit", 0))
'''
# Long texts of distinct characters, so a cut one character off shows in an exact comparison.
LONG_TEXT = "".join(f"{number:05d}" for number in range(400))

failures = []
SUITE_ROOT = Path(tempfile.mkdtemp(prefix="agent-seat-idle-sweep-slice-2-test-"))
# atexit, so that a case that raises or a sys.exit still leaves no files in /tmp.
atexit.register(shutil.rmtree, SUITE_ROOT, ignore_errors=True)


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def at(minutes):
    return (START + timedelta(minutes=minutes)).isoformat().replace("+00:00", "Z")


def assistant(text=None, when=LONG_AGO, tool=None, uuid=None):
    content = []
    if text is not None:
        content.append({"type": "text", "text": text})
    if tool is not None:
        content.append({"type": "tool_use", "id": "t", "name": tool[0], "input": tool[1]})
    return {"type": "assistant", "timestamp": when, "uuid": uuid or f"u-{when}-{text}",
            "message": {"model": "claude-opus-5-5", "content": content,
                        "usage": {"input_tokens": 100, "output_tokens": 100}}}


def user(text, when=LONG_AGO):
    return {"type": "user", "timestamp": when, "message": {"role": "user", "content": text}}


def turn_end(when=LONG_AGO):
    return {"type": "system", "subtype": "turn_duration", "timestamp": when}


def cross_session(text, when):
    return user("Another Claude session sent a message:\n<cross-session-message from=\"x\" "
                f"from-name=\"agent-seat-idle-sweep-1f\">\n{text}\n</cross-session-message>", when)


def usage_limit(resets_at, when=LONG_AGO):
    return {"type": "assistant", "timestamp": when, "uuid": "limit-record",
            "apiError": "usage_limit_reached", "quotaLimits": {"resetsAt": resets_at},
            "message": {"model": "<synthetic>", "content": [
                {"type": "text", "text": "You've hit your session limit"}],
                "usage": {"input_tokens": 0, "output_tokens": 0}}}


DONE_TURN = [user("go"), assistant("Done."), turn_end()]


def send_to(seat, message="@prompt-text", **extra):
    return dict({"to": f"{seat} [abc123]", "message": message}, **extra)


def sent_ok(seat="alpha"):
    return {"sends": [send_to(seat)], "answer": {"sent": True, "reason": "sent"}}


class Machine:
    def __init__(self):
        self.root = Path(tempfile.mkdtemp(dir=str(SUITE_ROOT)))
        self.handoffs, self.agents = self.root / "handoffs", self.root / "agents"
        self.projects, self.tasks = self.root / "projects", self.root / "tasks"
        self.home = self.root / "home"
        for folder in (self.handoffs, self.agents, self.projects, self.tasks, self.home):
            folder.mkdir()
        self.claude_json = self.root / "claude.json"
        self.account("account-1")
        self.log = self.root / "log" / "sweep.jsonl"
        self.state = self.root / "state"
        self.bin = self.root / "bin"
        self.bin.mkdir()
        fake = self.bin / "claude"
        fake.write_text(FAKE_CLAUDE.format(python=sys.executable))
        fake.chmod(0o755)
        self.calls = self.root / "claude-calls.jsonl"
        self.answers = self.root / "claude-answers.json"
        self.answers.write_text("[]")
        self.transcripts = {}

    def account(self, account):
        self.claude_json.write_text(json.dumps({"oauthAccount": {"accountUuid": account}}))

    def seat(self, name, records, session="s-1"):
        (self.agents / name).mkdir(exist_ok=True)
        (self.handoffs / f"{name}-supervisor-state.json").write_text(
            json.dumps({"launched_session_id": session}))
        project = self.projects / re.sub(r"[^a-zA-Z0-9]", "-", str((self.agents / name).resolve()))
        project.mkdir(exist_ok=True)
        transcript = project / f"{session}.jsonl"
        transcript.write_text("".join(json.dumps(record) + "\n" for record in records))
        self.transcripts[name] = transcript
        return transcript

    def append(self, name, *records):
        with self.transcripts[name].open("a") as stream:
            for record in records:
                stream.write(json.dumps(record) + "\n")

    def task(self, seat, task_id):
        directory = self.tasks / f"nedschorus-{seat}-tasks"
        directory.mkdir(exist_ok=True)
        (directory / f"{task_id}.json").write_text(json.dumps(
            {"id": task_id, "subject": f"task {task_id}", "status": "pending", "blocks": [],
             "blockedBy": []}))

    def handoff_put_off(self, session="s-1"):
        (self.handoffs / f"{session}-handoff-deferred").write_text("")

    def script(self, *answers):
        self.answers.write_text(json.dumps(list(answers)))
        if self.calls.exists():
            self.calls.unlink()

    def claude_calls(self):
        return ([json.loads(line) for line in self.calls.read_text().splitlines()]
                if self.calls.exists() else [])

    def events(self, kind=None):
        if not self.log.exists():
            return []
        events = [json.loads(line) for line in self.log.read_text().splitlines() if line.strip()]
        return [event for event in events if kind is None or event["event"] == kind]

    def alerts(self):
        pending = self.home / ".local" / "state" / "nedschorus" / "user-alerts" / "pending"
        return ([json.loads(path.read_text()) for path in sorted(pending.glob("*.json"))]
                if pending.is_dir() else [])

    def run(self, minutes, *extra, path_has_fake=True):
        environment = dict(os.environ)
        environment["HOME"] = str(self.home)
        if path_has_fake:
            environment["PATH"] = f"{self.bin}{os.pathsep}{environment['PATH']}"
        else:
            environment["PATH"] = os.pathsep.join(
                part for part in environment["PATH"].split(os.pathsep)
                if not (Path(part) / "claude").exists())
        environment["FAKE_CLAUDE_CALLS"] = str(self.calls)
        environment["FAKE_CLAUDE_ANSWERS"] = str(self.answers)
        completed = subprocess.run(
            [sys.executable, str(PROGRAM), "--now", at(minutes), "--handoff-directory",
             str(self.handoffs), "--agents-root", str(self.agents), "--projects-root",
             str(self.projects), "--tasks-root", str(self.tasks), "--claude-json",
             str(self.claude_json), "--log-file", str(self.log), "--state-directory",
             str(self.state), "--machine-name", "ned-box", *extra],
            capture_output=True, text=True, env=environment, check=False)
        return completed.returncode, completed.stdout + completed.stderr


HANDOFF_TEXT_START = "Your handoff was put off at"

# --- rule 3: the nudge, the delivery check, the escalation and telling the user --------------
machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.handoff_put_off()
machine.script(sent_ok())
code, output = machine.run(0)
calls = machine.claude_calls()
check("rule 3: exit 0, one headless agent-session", code == 0 and len(calls) == 1, (code, output))
argv = calls[0]["argv"] if calls else []
check("rule 3: the sender runs on Sonnet, allowed only SendMessage, ListAgents and ToolSearch",
      argv[argv.index("--model") + 1] == "sonnet"
      and argv[argv.index("--tools") + 1] == "SendMessage,ListAgents,ToolSearch"
      and argv[argv.index("--allowedTools") + 1] == "SendMessage,ListAgents,ToolSearch", argv)
check("rule 3: the sender is handed code's handoff text and the agent-seat's tmux session",
      calls and HANDOFF_TEXT_START in calls[0]["prompt"] and "tmux alpha:" in calls[0]["prompt"],
      calls)
sent = machine.events("message_sent")
check("rule 3: the send is logged as the nudge, with the text code wrote",
      len(sent) == 1 and sent[0]["step"] == "nudge" and sent[0]["text"].startswith(HANDOFF_TEXT_START),
      sent)
check("rule 3: a wait starts, counted from the last token spent",
      [(event["step"], event.get("first_idle_at")) for event in machine.events("wait_step")]
      == [("nudge", LONG_AGO)], machine.events("wait_step"))
machine.script()
code, _ = machine.run(0.5)
check("a run inside the delivery check's minute and the wait's 15 minutes does nothing",
      code == 0 and not machine.claude_calls() and not machine.events("delivery_checked"),
      machine.events())
code, _ = machine.run(2)
check("the message missing from the transcript of an idle agent-seat: a user-alert, exit 1",
      code == 1 and [event["found"] for event in machine.events("delivery_checked")] == [False]
      and len(machine.alerts()) == 1 and "did not reach alpha" in machine.alerts()[0]["title"],
      (machine.events("delivery_checked"), machine.alerts()))
machine.script(sent_ok())
code, _ = machine.run(16)
calls = machine.claude_calls()
check("idle again 15 minutes after the nudge: the escalation with the minutes since it went idle",
      len(calls) == 1 and "You've given this 26 minutes, please check; if not sure, hand off"
      in calls[0]["prompt"], calls)
# The agent-seat reads the escalation and answers it, and the delivery check finds it.
escalation = machine.events("message_sent")[-1]["text"]
machine.append("alpha", cross_session(escalation, at(16.2)), assistant("Still waiting.", at(16.3)),
               turn_end(at(16.4)))
machine.script()
code, _ = machine.run(18)
check("the message found in the agent-seat's transcript: no user-alert",
      [event["found"] for event in machine.events("delivery_checked")] == [False, True]
      and len(machine.alerts()) == 1, machine.events("delivery_checked"))
code, _ = machine.run(31.5)
check("idle again 15 minutes after the escalation: the user is told, and no message is sent",
      not machine.claude_calls() and len(machine.alerts()) == 2
      and "after a nudge and an escalation" in machine.alerts()[1]["title"], machine.alerts())
code, _ = machine.run(40)
check("after telling the user, nothing more while the agent-seat spends no tokens",
      not machine.claude_calls() and len(machine.alerts()) == 2, machine.alerts())
machine.append("alpha", user("more", at(41)), assistant("Back to it.", at(41.5)), turn_end(at(42)))
machine.script(sent_ok())
code, _ = machine.run(48)
check("spending tokens after the user was told starts the steps over, with a new nudge",
      len(machine.claude_calls()) == 1 and [event["step"] for event in machine.events("wait_step")]
      == ["nudge", "escalate", "tell_user", "nudge"]
      and machine.events("wait_ended")[-1]["why"] == "it spent tokens after the user was told",
      machine.events("wait_step"))

# --- rule 4 ends a wait; a new agent-session ends one too -------------------------------------
machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.handoff_put_off()
machine.script(sent_ok())
machine.run(0)
(machine.handoffs / "s-1-handoff-deferred").unlink()
machine.script()
machine.run(20)
check("rule 4 ends the wait: nothing to do, no escalation",
      not machine.claude_calls() and machine.events("wait_ended")[-1]["why"] == "nothing to do",
      machine.events())
machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.handoff_put_off()
machine.script(sent_ok())
machine.run(0)
machine.seat("alpha", DONE_TURN, session="s-2")
machine.handoff_put_off("s-2")
machine.script(sent_ok())
machine.run(20)
check("a new agent-session ends the wait and starts a new nudge, not the escalation",
      machine.events("wait_ended")[-1]["why"] == "a new agent-session"
      and machine.events("wait_step")[-1]["step"] == "nudge"
      and machine.events("wait_step")[-1]["session_id"] == "s-2", machine.events("wait_step"))

# --- rule 5: the judge decides whether to send --------------------------------------------------
machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.task("alpha", "1")
machine.script({"answer": {"sent": False, "reason": "a subagent started 3 minutes ago is still running"}})
code, _ = machine.run(0)
calls = machine.claude_calls()
check("rule 5: the judge is handed the open task and the agent-seat's last message",
      len(calls) == 1 and '"task 1"' in calls[0]["prompt"] and '"Done."' in calls[0]["prompt"]
      and "SendMessage,ListAgents,ToolSearch" in calls[0]["argv"], calls)
check("rule 5: a verdict not to send is logged with its reason, and no wait starts",
      [(event["sent"], event["reason"]) for event in machine.events("judge_answer")]
      == [(False, "a subagent started 3 minutes ago is still running")]
      and not machine.events("wait_step"), machine.events())
walk_item_machine = Machine()
walk_item_machine.seat("alpha", DONE_TURN)
walk_item_machine.task("alpha", "1")
walk = walk_item_machine.agents / "alpha" / "docs" / "walk"
walk.mkdir(parents=True)
(walk / "w-minutes.md").write_text("#next_to_present item 2 of 3\n")
walk_item_machine.script({"answer": {"sent": False, "reason": "it is answering the user"}})
walk_item_machine.run(0)
calls = walk_item_machine.claude_calls()
check("rule 5 with a walk item waiting: the judge is still asked, and is handed the walk item",
      len(calls) == 1 and '"task 1"' in calls[0]["prompt"]
      and '"approval_walk_items_waiting_on_the_user"' in calls[0]["prompt"]
      and '"item 2 of 3"' in calls[0]["prompt"], calls)
machine.script()
machine.run(10)
check("rule 5: not asked again within 15 minutes while the agent-seat spends no tokens",
      not machine.claude_calls(), machine.claude_calls())
machine.script({"sends": [send_to("alpha", "What's going on?")],
                "answer": {"sent": True, "reason": "nothing runs"}})
machine.run(15)
check("rule 5: asked again 15 minutes later; a message it sent starts the wait with its text",
      len(machine.claude_calls()) == 1 and machine.events("message_sent")[-1]["text"]
      == "What's going on?" and machine.events("wait_step")[-1]["step"] == "nudge",
      machine.events())
machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.task("alpha", "1")
machine.script({"answer": {"sent": False, "reason": "busy"}})
machine.run(0)
machine.append("alpha", user("go on", at(1)), assistant("Done again.", at(2)), turn_end(at(2)))
machine.script({"answer": {"sent": False, "reason": "busy"}})
machine.run(8)
check("rule 5: asked again when the agent-seat spent tokens and went idle again",
      len(machine.claude_calls()) == 1, machine.events())

machine = Machine()
transcript = machine.seat("alpha", [
    user("go"),
    dict(user("", when=at(-60)), toolUseResult={"status": "async_launched", "agentId": "a1b2"}),
    user("<task-notification>\n<task-id>a1b2</task-id>\n<status>completed</status>\n<note>the "
         "result below may be interim.</note>\n<result>Fix-round pushed.</result>\n"
         "</task-notification>", when=at(-40)),
    assistant("Waiting on the subagent."), turn_end()])
(transcript.with_suffix("") / "subagents").mkdir(parents=True)
(transcript.with_suffix("") / "subagents" / "agent-a1b2.jsonl").write_text("".join(
    json.dumps(record) + "\n" for record in [
        dict(user("", when=at(-50)), toolUseResult={"backgroundTaskId": "b3c4"}),
        assistant("Fix-round pushed.", when=at(-41))]))
machine.script({"answer": {"sent": False, "reason": "its test-suite run may be needed"}})
machine.run(0)
calls = machine.claude_calls()
prompt = calls[0]["prompt"] if calls else "\n{}"
judge_facts = json.loads(prompt[prompt.rindex("\n{") + 1:])
check("rule 5: a subagent stopped with a background command of its own still running is handed "
      "to the judge with its stop time, and that command with its minutes",
      judge_facts.get("running_subagents") == [{
          "id": "a1b2", "started": at(-60), "minutes_running": 60, "stopped_at": at(-40),
          "own_running_background_commands": [
              {"id": "b3c4", "started": at(-50), "minutes_running": 50}]}], calls)

# --- rule 2: promises and announced actions -------------------------------------------------------
PROMISE = "I'll report when PR 927 merges."
machine = Machine()
machine.seat("alpha", [user("go"), assistant(PROMISE), turn_end()])
machine.script(sent_ok())
machine.run(0)
calls = machine.claude_calls()
check("rule 2, an unbacked promise code settles: no judge, one sender with the promise line",
      len(calls) == 1 and 'You promised "I\'ll report when PR 927 merges.". Record it as a task'
      in calls[0]["prompt"], calls)
check("rule 2: the sentence is logged as checked, and the message is the nudge",
      [event["sentence"] for event in machine.events("sentence_checked")] == [PROMISE]
      and machine.events("wait_step")[0]["step"] == "nudge", machine.events())
machine.script()
machine.run(3)
check("rule 2: a sentence is raised once only", not machine.claude_calls(), machine.claude_calls())
check("rule 2: nothing to do does not end the wait a promise message started",
      not machine.events("wait_ended"), machine.events("wait_ended"))
machine.script(sent_ok())
machine.run(16)
calls = machine.claude_calls()
check("rule 2: still idle 15 minutes after the promise message: the escalation is sent",
      len(calls) == 1 and "please check" in calls[0]["prompt"]
      and [event["step"] for event in machine.events("wait_step")] == ["nudge", "escalate"],
      machine.events("wait_step"))
machine.script()
machine.run(32)
check("rule 2: idle 15 minutes after the escalation: the user is told",
      [event["step"] for event in machine.events("wait_step")] == ["nudge", "escalate", "tell_user"]
      and any("after a nudge and an escalation" in alert["title"] for alert in machine.alerts()),
      (machine.events("wait_step"), machine.alerts()))

SECOND_PROMISE = "I'll fix it after lunch."
machine = Machine()
machine.seat("alpha", [user("go"), assistant(PROMISE), turn_end()])
machine.script(sent_ok())
machine.run(0)
machine.append("alpha", cross_session("You promised", at(0.5)), assistant(SECOND_PROMISE, at(1)),
               turn_end(at(1)))
machine.script(sent_ok())
machine.run(7)
check("rule 2: a promise given in answer to the message is raised on the open wait",
      len(machine.claude_calls()) == 1 and SECOND_PROMISE in machine.claude_calls()[0]["prompt"]
      and [event["step"] for event in machine.events("wait_step")] == ["nudge"]
      and machine.events("wait_step")[0]["at"] == at(0), machine.events("wait_step"))
machine.script(sent_ok())
machine.run(16)
check("rule 2: the second promise did not put off the escalation",
      [event["step"] for event in machine.events("wait_step")] == ["nudge", "escalate"],
      machine.events("wait_step"))

# A promise sent on a wait a rule 5 or rule 3 message opened keeps that wait going through rule 4.
for opener in ("rule 5", "rule 3"):
    machine = Machine()
    machine.seat("alpha", DONE_TURN)
    if opener == "rule 5":
        machine.task("alpha", "1")
        machine.script({"sends": [send_to("alpha", "What's going on?")],
                        "answer": {"sent": True, "reason": "nothing runs"}})
    else:
        machine.handoff_put_off()
        machine.script(sent_ok())
    machine.run(0)
    if opener == "rule 5":
        (machine.tasks / "nedschorus-alpha-tasks" / "1.json").unlink()
    else:
        (machine.handoffs / "s-1-handoff-deferred").unlink()
    machine.append("alpha", cross_session(machine.events("message_sent")[-1]["text"], at(0.5)),
                   assistant(PROMISE, at(1)), turn_end(at(1)))
    machine.script(sent_ok())
    machine.run(7)
    machine.script()
    machine.run(8)
    check(f"a promise sent on a {opener} wait: nothing to do does not end the wait",
          not machine.events("wait_ended")
          and [event["step"] for event in machine.events("wait_step")] == ["nudge", "promise"],
          machine.events())
    machine.script(sent_ok())
    machine.run(16)
    machine.script()
    machine.run(32)
    check(f"a promise sent on a {opener} wait: the escalation, then the user is told",
          [event["step"] for event in machine.events("wait_step")]
          == ["nudge", "promise", "escalate", "tell_user"]
          and any("after a nudge and an escalation" in alert["title"] for alert in machine.alerts()),
          (machine.events("wait_step"), machine.alerts()))

ANNOUNCED = "I'm starting the PR 1633 work now."
machine = Machine()
machine.seat("alpha", [user("go"), assistant(ANNOUNCED), turn_end()])
machine.script({"answer": {"sentences": [{"index": 0, "backed": True, "reason": "a test runs"}]}})
machine.run(0)
calls = machine.claude_calls()
check("rule 2 judged backed: the judge has no tool, and rules 3 to 5 decide (rule 4: no wake)",
      len(calls) == 1 and calls[0]["argv"][calls[0]["argv"].index("--tools") + 1] == ""
      and "--allowedTools" not in calls[0]["argv"] and not machine.events("message_sent"), calls)
machine = Machine()
machine.seat("alpha", [user("go"), assistant(ANNOUNCED, when="2026-11-02T11:48:00Z"), turn_end()])
machine.script({"answer": {"sentences": [{"index": 0, "backed": False, "reason": "no call"}]}},
               sent_ok())
machine.run(0)
calls = machine.claude_calls()
check("rule 2 judged unbacked: a second headless agent-session sends the announced-action line",
      len(calls) == 2 and 'You said "I\'m starting the PR 1633 work now." 12 minutes ago and have '
      "not done it. Do it now, or tell the user why not." in calls[1]["prompt"], calls)
for case, answer in (("an index missing", {"sentences": []}),
                     ("backed not true or false", {"sentences": [{"index": 0, "backed": "yes",
                                                                  "reason": "r"}]})):
    machine = Machine()
    machine.seat("alpha", [user("go"), assistant(ANNOUNCED), turn_end()])
    machine.script({"answer": answer})
    code, _ = machine.run(0)
    check(f"rule 2, the judge's answer with {case}: a user-alert, exit 1, nothing sent",
          code == 1 and len(machine.alerts()) == 1 and not machine.events("message_sent"),
          (code, machine.alerts()))

# --- rule 1: a usage limit ------------------------------------------------------------------------
RESET_PASSED = int(START.timestamp()) - 60
machine = Machine()
machine.seat("alpha", [user("go"), assistant("working", when="2026-11-02T10:00:00Z"), user("more"),
                       usage_limit(RESET_PASSED)])
machine.task("alpha", "1")
machine.script(sent_ok())
machine.run(0)
calls = machine.claude_calls()
check("rule 1, the reset time passed: one wake with code's text",
      len(calls) == 1 and "The usage limit that stopped you has ended: its reset time has passed."
      in calls[0]["prompt"] and [event["step"] for event in machine.events("message_sent")]
      == ["limit_wake"], calls)
machine.script()
machine.run(3)
check("rule 1: no second wake for the same limit record", not machine.claude_calls(),
      machine.claude_calls())
machine.script({"answer": {"sent": False, "reason": "r"}})
machine.run(6)
check("rule 1: still idle 5 minutes after the wake, rules 2 to 5 decide (rule 5's judge)",
      len(machine.claude_calls()) == 1 and machine.events("judge_answer"), machine.events())

machine = Machine()
machine.seat("alpha", [user("go"), usage_limit(RESET_PASSED + 86400)])
machine.script()
machine.run(0)
check("rule 1, the reset time not passed: no wake, the limit's account recorded",
      not machine.claude_calls()
      and [event["account"] for event in machine.events("limit_seen")] == ["account-1"],
      machine.events())

# --- the account changes ---------------------------------------------------------------------------
machine = Machine()
machine.seat("alpha", [user("go"), usage_limit(RESET_PASSED + 86400)])
machine.seat("beta", DONE_TURN)
machine.script()
machine.run(0)
check("the first account seen is only recorded",
      not machine.claude_calls() and [event["account"] for event in machine.events("account_seen")]
      == ["account-1"], machine.events())
machine.claude_json.write_text("{}")
machine.run(1)
check("a missing account is not a change", not machine.claude_calls(), machine.claude_calls())
machine.account("account-2")
machine.script({"sends": [send_to("alpha"), send_to("beta")], "answer": {"sent": True, "reason": "r"}})
code, _ = machine.run(2)
calls = machine.claude_calls()
check("an account change: one headless agent-session sends the notice to every agent-seat",
      code == 0 and len(calls) == 1 and "alpha, beta" in calls[0]["prompt"]
      and "The claude.ai account logged in on ned-box changed at" in calls[0]["prompt"]
      and sorted(event["agent_seat"] for event in machine.events("message_sent")) == ["alpha", "beta"],
      (code, calls))
check("an account change: the notice is the wake of an agent-seat idle at a limit, no second one",
      [event["agent_seat"] for event in machine.events("limit_wake")] == ["alpha"]
      and len(calls) == 1, machine.events("limit_wake"))
machine.script()
machine.run(3)
check("the account change is noticed once", not machine.claude_calls(), machine.claude_calls())

machine = Machine()
machine.seat("alpha", [user("go"), usage_limit(RESET_PASSED + 86400)])
machine.script()
machine.run(0)
machine.claude_json.write_text("{not json")
code, _ = machine.run(1)
check("an unreadable ~/.claude.json is logged as a read failure, not a change",
      not machine.claude_calls() and machine.events("read_failure")
      and len(machine.events("account_seen")) == 1, machine.events())
code, _ = machine.run(4)
check("an unreadable ~/.claude.json still unreadable minutes later: one user-alert",
      len(machine.alerts()) == 1 and "cannot read" in machine.alerts()[0]["title"], machine.alerts())
machine.run(5)
check("a read failure is alerted once", len(machine.alerts()) == 1, machine.alerts())

machine = Machine()
machine.seat("alpha", [user("go"), usage_limit(RESET_PASSED + 86400)])
machine.script()
machine.run(0)
machine.account("account-2")
machine.script({"answer": {"sent": True, "reason": "r"}})
machine.run(1)
check("a notice the headless agent-session did not send: no second wake at the limit",
      len(machine.claude_calls()) == 1 and len(machine.events("limit_wake")) == 1, machine.events())
code, _ = machine.run(3)
check("a notice missing from a listed agent-seat's transcript: a user-alert, exit 1",
      code == 1 and len(machine.alerts()) == 1 and "account notice" in machine.alerts()[0]["title"],
      machine.alerts())

# --- headless agent-sessions that fail --------------------------------------------------------------
FAILURES = (
    ("exits nonzero", {"exit": 1}, "claude exited 1"),
    ("gives no result event", {"garbage": True}, "no result event"),
    ("reports an error", {"result": {"subtype": "error_during_execution", "is_error": True,
                                     "result": "boom"}}, "claude reported an error"),
    ("gives no JSON answer", {"result": {"subtype": "success", "is_error": False}},
     "no JSON answer"),
    ("sends to another entry", {"sends": [send_to("beta")], "answer": {"sent": True, "reason": "r"}},
     "sent to 'beta [abc123]'"),
    ("sends another text", {"sends": [send_to("alpha", "hello")],
                            "answer": {"sent": True, "reason": "r"}}, "a text other than"),
    ("has its send fail", {"sends": [send_to("alpha", is_error=True)],
                           "answer": {"sent": False, "reason": "r"}}, "no SendMessage to alpha"),
    ("runs past its time", {"sleep": 5, "answer": {"sent": True, "reason": "r"}}, "stopped after"),
    ("is killed by a signal", {"signal": True, "answer": {"sent": True, "reason": "r"}},
     "claude exited -15"),
    ("ends without success", {"result": {"subtype": "error_max_turns", "is_error": False,
                                         "structured_output": {"sent": True, "reason": "r"}}},
     "claude reported an error"),
    ("ends with a result of an unknown kind",
     {"result": {"subtype": "unknown_subtype", "is_error": False,
                 "structured_output": {"sent": True, "reason": "r"}}}, "claude reported an error"),
    ("reports an error on a result marked success",
     {"result": {"subtype": "success", "is_error": True,
                 "structured_output": {"sent": True, "reason": "r"}}}, "claude reported an error"),
)
# The error text keeps the end of stderr, the end of stdout, or the start of the result's text.
EXACT_FAILURES = (
    ("exits nonzero with a long stderr", {"exit": 1, "stderr": LONG_TEXT},
     f"claude exited 1: {LONG_TEXT[-500:]}"),
    ("gives a long output with no result event", {"garbage": LONG_TEXT},
     f"claude gave no result event: {(LONG_TEXT + chr(10))[-500:]!r}"),
    ("reports a long error", {"result": {"subtype": "error_during_execution", "is_error": True,
                                         "result": LONG_TEXT}},
     f"claude reported an error: {LONG_TEXT[:500]}"),
)
for case, answer, words in FAILURES + EXACT_FAILURES:
    machine = Machine()
    machine.seat("alpha", DONE_TURN)
    machine.handoff_put_off()
    machine.script(answer)
    code, output = machine.run(0, "--headless-timeout-seconds", "1")
    failed = machine.events("headless_failed")
    exact = (case, answer, words) in EXACT_FAILURES
    check(f"a sender that {case}: logged, a user-alert, exit 1, no delivery check pending",
          code == 1 and len(failed) == 1
          and (failed[0]["problem"] == words if exact else words in failed[0]["problem"])
          and len(machine.alerts()) == 1 and not machine.events("message_sent"),
          (code, output, failed, machine.alerts()))
    if case == "exits nonzero":
        machine.script({"exit": 1})
        machine.run(1)
        check("a failed send is not retried every minute: the wait goes on to its next step",
              not machine.claude_calls() and len(machine.alerts()) == 1, machine.claude_calls())

machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.handoff_put_off()
code, _ = machine.run(0, path_has_fake=False)
check("claude that cannot be started: a user-alert, exit 1",
      code == 1 and "could not start claude" in machine.events("headless_failed")[0]["problem"],
      machine.events("headless_failed"))

machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.task("alpha", "1")
machine.script({"answer": {"sent": True, "reason": "sent it"}})
code, _ = machine.run(0)
check("a judge that answers sent but made no send: a user-alert, exit 1, no wait",
      code == 1 and "no SendMessage call succeeded" in machine.events("headless_failed")[0]["problem"]
      and not machine.events("wait_step"), machine.events())
machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.task("alpha", "1")
machine.script({"sends": [send_to("beta", "hi")], "answer": {"sent": True, "reason": "r"}})
code, _ = machine.run(0)
check("a judge that sends to another entry: a user-alert, exit 1, no wait",
      code == 1 and not machine.events("wait_step") and len(machine.alerts()) == 1, machine.events())

# --- delivery while the agent-seat is busy ----------------------------------------------------------
machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.handoff_put_off()
machine.script(sent_ok())
machine.run(0)
machine.append("alpha", user("next", at(0.5)))
machine.script()
machine.run(2)
check("the message not yet in the transcript of a busy agent-seat: the delivery check waits",
      not machine.events("delivery_checked") and not machine.alerts(), machine.events())

machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.handoff_put_off()
machine.script(sent_ok())
machine.run(0)
machine.transcripts["alpha"].write_text("{not json\n" + json.dumps(turn_end()) + "\n")
machine.script()
code, _ = machine.run(2)
check("a transcript the delivery check cannot read: a read failure logged, the check left pending",
      not machine.events("delivery_checked") and not machine.alerts()
      and any("s-1.jsonl line 1" in event["error"] for event in machine.events("read_failure")),
      machine.events())

machine = Machine()
machine.seat("alpha", [user("go"), usage_limit(RESET_PASSED + 86400)])
machine.seat("beta", DONE_TURN)
machine.run(0)
machine.account("account-2")
machine.script({"sends": [send_to("alpha"), send_to("beta")], "answer": {"sent": True, "reason": "r"}})
machine.run(1)
machine.transcripts["alpha"].write_text("{not json\n" + json.dumps(turn_end()) + "\n")
machine.script()
machine.run(3)
check("an unreadable transcript at one delivery check does not stop the next agent-seat's check",
      [(event["agent_seat"], event["found"]) for event in machine.events("delivery_checked")]
      == [("beta", False)], machine.events("delivery_checked"))

machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.handoff_put_off()
machine.script(dict(sent_ok(), garbage="a line that is not JSON", garbage_then_result=True))
code, _ = machine.run(0)
check("a line of output that is not JSON, before the result: skipped, the send stands",
      code == 0 and not machine.events("headless_failed") and machine.events("message_sent"),
      machine.events())

machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.handoff_put_off()
machine.script({"sends": [send_to("alpha", "Your handoff was put off\n at")],
                "answer": {"sent": True, "reason": "r"}})
machine.run(0)
text = machine.claude_calls()[0]["prompt"].split("----------\n", 1)[1].rsplit("\n----------", 1)[0]
machine.script({"sends": [send_to("alpha", text.replace(" ", "\n", 3))],
                "answer": {"sent": True, "reason": "r"}})
machine.run(1, "--state-directory", str(machine.root / "state-2"), "--log-file",
            str(machine.root / "log-2.jsonl"))
check("a sender that reflows the lines of code's text: no failure",
      not [event for event in map(json.loads, (machine.root / "log-2.jsonl").read_text().splitlines())
           if event["event"] == "headless_failed"], (machine.root / "log-2.jsonl").read_text())

# --- read failures, the lock, and a failed invocation -----------------------------------------------
machine = Machine()
machine.seat("alpha", DONE_TURN)
(machine.handoffs / "alpha-supervisor-state.json").write_text("{not json")
code, _ = machine.run(0)
check("a read failure seen once: logged, no user-alert", len(machine.events("read_failure")) == 1
      and not machine.alerts(), machine.events())
code, _ = machine.run(3)
check("the same read failure minutes later: one user-alert, exit 1",
      code == 1 and len(machine.alerts()) == 1, (code, machine.alerts()))

machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.handoff_put_off()
machine.state.mkdir()
with (machine.state / "run.lock").open("w") as held:
    fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
    code, output = machine.run(0)
check("an earlier invocation still running: this one does nothing and exits 0",
      code == 0 and "still running" in output and not machine.claude_calls()
      and not machine.events(), (code, output))

machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.log.parent.mkdir(parents=True)
machine.log.write_text("{not json\n{}\n")
code, output = machine.run(0)
check("an unreadable log: a traceback, exit 1, and a user-alert",
      code == 1 and "IdleSweepLogLineNotUtf8Json" in output and len(machine.alerts()) == 1, (code, output))
machine.run(1)
check("the same failed invocation is alerted once", len(machine.alerts()) == 1, machine.alerts())
machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.log.parent.mkdir(parents=True)
machine.log.write_text('{"event": "account_seen", "account": "account-1", "at": "' + at(-5)
                       + '"}\n{"event": "acc')
code, output = machine.run(0)
check("a log whose last line was cut short: the line is skipped, exit 0", code == 0, output)
code, output = machine.run(1)
check("a log whose last line was cut short: later runs still read the log, exit 0",
      code == 0 and "IdleSweepLogLineNotUtf8Json" not in output, (code, output))
check("a log whose last line was cut short: the skipped line is dropped before the next event",
      '{"event": "acc' not in machine.log.read_text().splitlines()
      and machine.log.read_text().startswith('{"event": "account_seen", "account": "account-1"')
      and all(json.loads(line) for line in machine.log.read_text().splitlines()),
      machine.log.read_text())
machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.log.parent.mkdir(parents=True)
WHOLE_LAST_LINE = '{"event": "account_seen", "account": "account-1", "at": "' + at(-5) + '"}'
machine.log.write_text(WHOLE_LAST_LINE)
code, output = machine.run(0)
check("a log whose whole last line has no newline: the line is kept, and the next event follows it",
      code == 0 and machine.log.read_text().splitlines()[0] == WHOLE_LAST_LINE
      and all(json.loads(line) for line in machine.log.read_text().splitlines()),
      machine.log.read_text())
appended = {}
# With no account in the log, one run writes account_seen and then checked: two appends.
for name, text in (("empty", ""), ("cut short", '{"event": "acc')):
    machine = Machine()
    machine.seat("alpha", DONE_TURN)
    machine.log.parent.mkdir(parents=True)
    machine.log.write_text(text)
    machine.run(0)
    appended[name] = machine.log.read_text().splitlines()
check("a log whose last line was cut short: every event of the run is kept, not only its first",
      len(appended["empty"]) >= 2 and len(appended["cut short"]) == len(appended["empty"])
      and all(json.loads(line) for line in appended["cut short"]), appended)

# --- the steps of a wait, worked out apart from the rule 2 send ------------------------------------
machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.handoff_put_off()
machine.script(sent_ok())
machine.run(0)
machine.script(sent_ok())
machine.run(16)
machine.script()
machine.run(32)
(machine.handoffs / "s-1-handoff-deferred").unlink()
machine.append("alpha", user("more", at(40)), assistant(PROMISE, at(41)), turn_end(at(41)))
machine.script(sent_ok())
machine.run(47)
check("a promise after the user was told: the old wait ends and the promise message opens a new one",
      len(machine.claude_calls()) == 1
      and [event["why"] for event in machine.events("wait_ended")][-1:]
      == ["it spent tokens after the user was told"]
      and [event["step"] for event in machine.events("wait_step")]
      == ["nudge", "escalate", "tell_user", "nudge"], machine.events("wait_step"))
machine.script(sent_ok())
machine.run(63)
calls = machine.claude_calls()
check("a promise after the user was told: still idle 15 minutes later, the escalation is sent",
      len(calls) == 1 and "please check" in calls[0]["prompt"]
      and [event["step"] for event in machine.events("wait_step")][-2:] == ["nudge", "escalate"],
      (calls, machine.events("wait_step")))
machine.script()
machine.run(79)
check("a promise after the user was told: 15 minutes after that escalation, the user is told again",
      [event["step"] for event in machine.events("wait_step")][-3:]
      == ["nudge", "escalate", "tell_user"]
      and sum("after a nudge and an escalation" in alert["title"] for alert in machine.alerts()) == 2,
      (machine.events("wait_step"), machine.alerts()))

THIRD_PROMISE = "I'll push once the tests pass."
machine = Machine()
machine.seat("alpha", [user("go"), assistant(PROMISE), turn_end()])
machine.script(sent_ok())
machine.run(0)
machine.append("alpha", cross_session("You promised", at(0.5)), assistant(SECOND_PROMISE, at(1)),
               turn_end(at(1)))
machine.script(sent_ok())
machine.run(7)
machine.append("alpha", cross_session("You promised", at(7.5)), assistant(THIRD_PROMISE, at(8)),
               turn_end(at(8)))
machine.script(sent_ok(), sent_ok())
machine.run(16)
calls = machine.claude_calls()
check("a fresh promise at every run does not put off the escalation 15 minutes after the nudge",
      len(calls) == 2 and "please check" in calls[0]["prompt"] and THIRD_PROMISE in calls[1]["prompt"]
      and [event["step"] for event in machine.events("wait_step")] == ["nudge", "escalate"],
      (calls, machine.events("wait_step")))

# --- delivery counts only a record that shows the agent-seat received the message -------------------
for received, record_of in (
        (False, lambda text, when: {"type": "queue-operation", "operation": "enqueue",
                                    "timestamp": when, "content": text}),
        (True, lambda text, when: {"type": "attachment", "timestamp": when, "attachment": {
            "type": "queued_command", "prompt": f"<cross-session-message>\n{text}\n"}})):
    machine = Machine()
    machine.seat("alpha", DONE_TURN)
    machine.handoff_put_off()
    machine.script(sent_ok())
    machine.run(0)
    machine.append("alpha", record_of(machine.events("message_sent")[-1]["text"], at(0.2)))
    machine.script()
    code, _ = machine.run(2)
    kind = "a queued_command attachment" if received else "only Claude Code's enqueue record"
    check(f"the message in {kind}: delivery found {received}",
          [event["found"] for event in machine.events("delivery_checked")] == [received]
          and len(machine.alerts()) == (0 if received else 1), machine.events("delivery_checked"))

# --- what a headless agent-session may use -------------------------------------------------------------
machine = Machine()
machine.seat("alpha", [user("go"), assistant(ANNOUNCED, when="2026-11-02T11:48:00Z"), turn_end()])
machine.script({"answer": {"sentences": [{"index": 0, "backed": False, "reason": "no call"}]}},
               sent_ok())
machine.run(0)
calls = machine.claude_calls()
check("every headless agent-session loads no MCP server and asks no permission it was not given",
      len(calls) == 2 and all("--strict-mcp-config" in call["argv"]
                              and "--permission-mode" in call["argv"]
                              and call["argv"][call["argv"].index("--permission-mode") + 1]
                              == "dontAsk" for call in calls), calls)

# --- a rule 5 judge whose send failed ------------------------------------------------------------------
machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.task("alpha", "1")
machine.script({"sends": [send_to("alpha", "What's going on?", is_error=True)],
                "answer": {"sent": False, "reason": "the send failed"}})
code, _ = machine.run(0)
check("a rule 5 judge whose SendMessage failed, answering not sent: a user-alert, exit 1, no wait",
      code == 1
      and any("SendMessage" in event["problem"] for event in machine.events("headless_failed"))
      and len(machine.alerts()) == 1 and not machine.events("wait_step"), machine.events())

# --- each event carries the time it was written, not the time the run started ---------------------
machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.seat("beta", DONE_TURN)
machine.handoff_put_off()
machine.script(dict(sent_ok(), sleep=2.5), sent_ok("beta"))
machine.run(0)
nudges = {event["agent_seat"]: event["at"] for event in machine.events("wait_step")}
check("a nudge logged after an earlier headless agent-session carries the time it was logged",
      set(nudges) == {"alpha", "beta"} and max(datetime.fromisoformat(stamp.replace("Z", "+00:00"))
                                               for stamp in nudges.values())
      >= START + timedelta(seconds=2), nudges)

# --- a read failure that persists keeps the run failing ---------------------------------------------
machine = Machine()
machine.seat("alpha", DONE_TURN)
(machine.handoffs / "alpha-supervisor-state.json").write_text("{not json")
machine.run(0)
machine.run(3)
code, _ = machine.run(5)
check("a read failure still there after its user-alert: exit 1 again, no second user-alert",
      code == 1 and len(machine.alerts()) == 1, (code, machine.alerts()))

# --- a headless agent-session past its time is stopped with every process it started --------------
machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.handoff_put_off()
machine.script({"child": 30, "sleep": 30, "answer": {"sent": True, "reason": "r"}})
began = datetime.now(timezone.utc)
code, _ = machine.run(0, "--headless-timeout-seconds", "1")
took = (datetime.now(timezone.utc) - began).total_seconds()
check("a sender past its time whose child holds its output open: stopped in seconds, not 30",
      code == 1 and took < 15
      and any("stopped after" in event["problem"] for event in machine.events("headless_failed")),
      (code, took, machine.events("headless_failed")))

# --- an older open task that waits on something reaches the judge ---------------------------------
machine = Machine()
machine.seat("alpha", [user("go"), assistant(PROMISE), turn_end()])
machine.task("alpha", "6")
machine.task("alpha", "7")
# blockedBy, not a pull request prerequisite, so that no gh query is made.
older_task = machine.tasks / "nedschorus-alpha-tasks" / "7.json"
older_task.write_text(json.dumps(dict(json.loads(older_task.read_text()), blockedBy=["6"])))
# Judged backed, rule 5 follows for the open task 6, and its judge sends nothing.
machine.script({"answer": {"sentences": [{"index": 0, "backed": True, "reason": "task 7"}]}},
               {"answer": {"sent": False, "reason": "busy"}})
machine.run(0)
calls = machine.claude_calls()
check("a promise with an older open task held by blockedBy: the judge is handed that task",
      len(calls) == 2 and '"open_tasks_with_prerequisites_or_blocked_by": [ { "id": "7", "subject": '
      '"task 7", "prerequisites": [], "blockedBy": [ "6" ] } ]' in " ".join(calls[0]["prompt"].split())
      and not machine.events("message_sent"), calls)

# --- the next check reads from the time of the transcript read, not of the record --------------
# alpha's sender takes 2 s, so beta's check record is written 2 s after beta's transcript was read;
# a promise beta writes 1 s into the run must still be read on the next run.
machine = Machine()
machine.seat("alpha", [user("go"), assistant(PROMISE), turn_end()])
machine.seat("beta", [user("go"), assistant(PROMISE), turn_end()], session="s-2")
machine.script(dict(sent_ok(), sleep=2), sent_ok("beta"))
machine.run(0)
beta_checks = [event for event in machine.events("checked") if event["agent_seat"] == "beta"]
check("a check record keeps the time the transcript was read, apart from the time it was written",
      len(beta_checks) == 1 and beta_checks[0]["transcript_read_at"] == at(0)
      and beta_checks[0]["at"] > at(0), beta_checks)
machine.append("beta", user("more", at(1 / 60)), assistant(SECOND_PROMISE, at(1 / 60)),
               turn_end(at(1 / 60)))
machine.script(sent_ok("beta"), sent_ok("beta"))
machine.run(7)
check("a promise written between the transcript read and the check record is read on the next run",
      SECOND_PROMISE in [event["sentence"] for event in machine.events("sentence_checked")
                         if event["agent_seat"] == "beta"], machine.events())

# --- the delivery check measures from the send's start, not from the sender's end ------------------
# The sender runs 2 s, so its message_sent record is written 2 s after the send began. A received
# record 119 s before the start is inside the 120 s clock slack from the start, and outside it from
# the end: found only when the check measures from the start.
machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.handoff_put_off()
machine.script(dict(sent_ok(), sleep=2))
machine.run(0)
sent = machine.events("message_sent")
check("a send logs the time it started, apart from the time the record is written",
      len(sent) == 1 and sent[0].get("send_started_at") == at(0) and sent[0]["at"] > at(0), sent)
early = (START - timedelta(seconds=119)).isoformat().replace("+00:00", "Z")
machine.append("alpha", user(sent[0]["text"], early))
machine.script()
machine.run(2)
check("a sender that runs on after its send: the delivery check finds the message, no user-alert",
      [event["found"] for event in machine.events("delivery_checked")] == [True]
      and not machine.alerts(), (machine.events("delivery_checked"), machine.alerts()))

# --- a message_sent record with no send_started_at, as the log holds from older invocations ------
machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.handoff_put_off()
machine.script(sent_ok())
machine.run(0)
older = [{key: value for key, value in event.items() if key != "send_started_at"}
         for event in machine.events()]
machine.log.write_text("".join(json.dumps(event) + "\n" for event in older))
machine.append("alpha", user(machine.events("message_sent")[0]["text"], at(0)))
machine.script()
code, output = machine.run(2)
check("a pending send logged with no send_started_at: checked from its \"at\", no crash",
      code == 0 and [event["found"] for event in machine.events("delivery_checked")] == [True],
      (code, output, machine.events("delivery_checked")))

# --- a read failure that ended and came back is dated from its return ---------------------------
machine = Machine()
machine.seat("alpha", DONE_TURN)
state_file = machine.handoffs / "alpha-supervisor-state.json"
good_state = state_file.read_text()
state_file.write_text("{not json")
machine.run(0)
state_file.write_text(good_state)
machine.script()
machine.run(1)
check("a read failure not met again: its end is logged",
      [event["event"] for event in machine.events() if event["event"].startswith("read_failure")]
      == ["read_failure", "read_failure_ended"], machine.events())
machine.script()
machine.run(2)
check("a read failure already ended: a second clean run logs no second end",
      [event["event"] for event in machine.events() if event["event"].startswith("read_failure")]
      == ["read_failure", "read_failure_ended"], machine.events())
state_file.write_text("{not json")
code, _ = machine.run(10)
check("the failure back days later: logged anew, no user-alert at once",
      len(machine.events("read_failure")) == 2 and not machine.alerts(), machine.alerts())
code, _ = machine.run(13)
check("the failure back, minutes after its return: one user-alert",
      code == 1 and len(machine.alerts()) == 1, (code, machine.alerts()))

if failures:
    print(f"{len(failures)} case(s) failed")
    sys.exit(1)
print("all cases passed")
