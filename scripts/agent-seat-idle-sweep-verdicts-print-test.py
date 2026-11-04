#!/usr/bin/env python3
"""Cases for scripts/agent-seat-idle-sweep-verdicts-print.py.

Every case runs the program as a subprocess against folders this suite made: a handoff directory,
an agents root, a projects root, a tasks root and a ~/.claude.json, never the real ones. `gh` is a
stand-in placed first on PATH that answers from a file the case writes. Each case fixes the time
with --now, so the 5-minute idle test does not depend on the clock.
"""

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROGRAM = Path(__file__).with_name("agent-seat-idle-sweep-verdicts-print.py")
_fields_specification = importlib.util.spec_from_file_location(
    "agent_seat_idle_sweep_verdict_fields_common",
    Path(__file__).with_name("agent-seat-idle-sweep-verdict-fields-common.py"))
fields = importlib.util.module_from_spec(_fields_specification)
_fields_specification.loader.exec_module(fields)
NOW = "2026-11-02T12:00:00Z"
LONG_AGO = "2026-11-02T11:50:00Z"
GH_STAND_IN = """#!{python}
import json, os, sys
responses = json.load(open(os.environ["FAKE_GH_RESPONSES"]))
answer = responses.get(sys.argv[1] + ":" + sys.argv[3], "fail")
if answer == "fail":
    sys.stderr.write("gh stand-in: failing on purpose\\n")
    sys.exit(1)
print(json.dumps(answer))
"""

failures = []
SUITE_ROOT = Path(tempfile.mkdtemp(prefix="agent-seat-idle-sweep-verdicts-print-test-"))


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def assistant(text=None, at=LONG_AGO, tokens=100, tool=None, uuid=None):
    content = []
    if text is not None:
        content.append({"type": "text", "text": text})
    if tool is not None:
        content.append({"type": "tool_use", "id": "t", "name": tool[0], "input": tool[1]})
    return {"type": "assistant", "timestamp": at, "uuid": uuid or f"u-{at}-{text}",
            "message": {"model": "claude-opus-5-5", "content": content,
                        "usage": {"input_tokens": tokens, "output_tokens": tokens}}}


def user(text, at=LONG_AGO, tool_result=None):
    record = {"type": "user", "timestamp": at, "message": {"role": "user", "content": text}}
    if tool_result is not None:
        record["toolUseResult"] = tool_result
    return record


def turn_end(at=LONG_AGO):
    return {"type": "system", "subtype": "turn_duration", "timestamp": at}


def usage_limit(resets_at, at=LONG_AGO):
    return {"type": "assistant", "timestamp": at, "uuid": "limit-record",
            "apiError": "usage_limit_reached", "quotaLimits": {"resetsAt": resets_at},
            "message": {"model": "<synthetic>", "content": [
                {"type": "text", "text": "You've hit your session limit"}],
                "usage": {"input_tokens": 0, "output_tokens": 0}}}


class Machine:
    """The folders one run reads, holding any number of agent-seats."""

    def __init__(self):
        self.root = Path(tempfile.mkdtemp(dir=str(SUITE_ROOT)))
        self.handoffs = self.root / "handoffs"
        self.agents = self.root / "agents"
        self.projects = self.root / "projects"
        self.tasks = self.root / "tasks"
        for folder in (self.handoffs, self.agents, self.projects, self.tasks):
            folder.mkdir()
        self.claude_json = self.root / "claude.json"
        self.claude_json.write_text(json.dumps({"oauthAccount": {"accountUuid": "account-1"}}))
        self.bin = self.root / "bin"
        self.bin.mkdir()
        gh = self.bin / "gh"
        gh.write_text(GH_STAND_IN.format(python=sys.executable))
        gh.chmod(0o755)
        self.gh_responses = self.root / "gh.json"
        self.gh_responses.write_text("{}")

    def seat(self, name, records=(), session="s-1", state=None, raw_tail=b""):
        (self.agents / name).mkdir(exist_ok=True)
        state = state if state is not None else {"launched_session_id": session}
        (self.handoffs / f"{name}-supervisor-state.json").write_text(json.dumps(state))
        # Claude Code's own rule for naming a project folder after a working directory.
        project = self.projects / re.sub(r"[^a-zA-Z0-9]", "-", str((self.agents / name).resolve()))
        project.mkdir(exist_ok=True)
        transcript = project / f"{session}.jsonl"
        if records is not None:
            transcript.write_bytes(b"".join(json.dumps(r).encode() + b"\n" for r in records)
                                   + raw_tail)
        return project, transcript

    def task(self, seat, task_id, status="pending", metadata=None, blocked_by=()):
        directory = self.tasks / f"nedschorus-{seat}-tasks"
        directory.mkdir(exist_ok=True)
        task = {"id": task_id, "subject": f"task {task_id}", "status": status,
                "blocks": [], "blockedBy": list(blocked_by)}
        if metadata:
            task["metadata"] = metadata
        (directory / f"{task_id}.json").write_text(json.dumps(task))

    def walk_minutes(self, seat, text, name="w-minutes.md"):
        directory = self.agents / seat / "docs" / "walk"
        directory.mkdir(parents=True, exist_ok=True)
        (directory / name).write_bytes(text if isinstance(text, bytes) else text.encode())

    def run(self, *extra):
        environment = dict(os.environ)
        environment["PATH"] = f"{self.bin}{os.pathsep}{environment['PATH']}"
        environment["FAKE_GH_RESPONSES"] = str(self.gh_responses)
        completed = subprocess.run(
            [sys.executable, str(PROGRAM), "--now", NOW, "--handoff-directory", str(self.handoffs),
             "--agents-root", str(self.agents), "--projects-root", str(self.projects),
             "--tasks-root", str(self.tasks), "--claude-json", str(self.claude_json), *extra],
            capture_output=True, text=True, env=environment, check=False)
        verdicts = {}
        for line in completed.stdout.splitlines():
            verdict = json.loads(line)
            verdicts[verdict["agent_seat"]] = verdict
            # Every printed verdict, in every case, must keep to the fields module.
            problems = fields.verdict_field_problems(verdict)
            if problems:
                failures.append(f"verdict fields of {verdict.get('agent_seat')}")
                print(f"FAIL  verdict fields: {problems} in {verdict}")
        return completed.returncode, verdicts, completed.stderr


ANNOUNCED = "I'm starting the PR 1633 work now."
IDLE_TURN = [user("go"), assistant(ANNOUNCED), turn_end()]

# --- rule 2: an announced action goes to the judge, with what slice 2 reads -----------------
machine = Machine()
_, transcript = machine.seat("alpha", IDLE_TURN)
code, verdicts, error = machine.run()
alpha = verdicts.get("alpha", {})
check("announced action: exit 0", code == 0, (code, error))
check("announced action: idle, rule 2, judge",
      alpha.get("idle") is True and alpha.get("rule") == 2 and alpha.get("decision") == "judge",
      alpha)
check("announced action: the sentence and its kind",
      [(s["sentence"], s["kind"], s["code_reading"]) for s in alpha.get("sentences", [])]
      == [(ANNOUNCED, "announced_action", "judge")], alpha.get("sentences"))
check("announced action: session id, transcript path, last activity and its source",
      alpha.get("session_id") == "s-1" and alpha.get("transcript_path") == str(transcript)
      and alpha.get("last_activity") == {"time": LONG_AGO, "source": str(transcript)}, alpha)
check("announced action: rules 3 to 5 also decided, for when the judge finds it backed",
      alpha.get("if_every_sentence_backed") == {"rule": 4, "decision": "no_wake"}, alpha)

# --- rule 2: a promise after an event, unbacked, then backed by a task with prerequisites ---
PROMISE = "I'll report when PR 927 merges."
machine = Machine()
machine.seat("alpha", [user("go"), assistant(PROMISE), turn_end()])
_, verdicts, _ = machine.run()
check("promise with no task: code finds it unbacked",
      verdicts["alpha"].get("decision") == "send_unbacked"
      and verdicts["alpha"]["sentences"][0]["kind"] == "promise_after_event", verdicts["alpha"])
machine = Machine()
machine.seat("alpha", [user("go"), assistant(PROMISE),
                       assistant(tool=("TaskCreate", {"subject": "report",
                                                      "metadata": {"prerequisites": [
                                                          {"pr_merged": 927}]}})),
                       turn_end()])
_, verdicts, _ = machine.run()
check("promise with a task carrying prerequisites: the judge decides whether it names the event",
      verdicts["alpha"]["sentences"][0]["code_reading"] == "judge"
      and verdicts["alpha"].get("decision") == "judge", verdicts["alpha"])
machine = Machine()
machine.seat("alpha", [user("go"), assistant("I'll hold."),
                       assistant(tool=("TaskUpdate", {"taskId": "3", "addBlockedBy": ["2"]})),
                       turn_end()])
_, verdicts, _ = machine.run()
check("a hold backed by addBlockedBy goes to the judge",
      [(s["kind"], s["code_reading"]) for s in verdicts["alpha"]["sentences"]]
      == [("hold", "judge")], verdicts["alpha"])
machine = Machine()
machine.seat("alpha", [user("a", at="2026-11-02T11:30:00Z"),
                       assistant(tool=("TaskCreate", {"metadata": {"prerequisites": [
                           {"pr_merged": 927}]}}), at="2026-11-02T11:35:00Z"),
                       turn_end(at="2026-11-02T11:36:00Z"), user("go", at="2026-11-02T11:40:00Z"),
                       assistant(PROMISE), turn_end()])
_, verdicts, _ = machine.run()
check("a task created in an earlier turn does not back the promise",
      verdicts["alpha"]["sentences"][0]["code_reading"] == "unbacked", verdicts["alpha"])
machine = Machine()
machine.seat("alpha", [user("go", at="2026-11-02T11:49:00Z"),
                       assistant(tool=("TaskCreate", {"metadata": {"prerequisites": [
                           {"pr_merged": 927}]}}), at="2026-11-02T11:49:30Z"),
                       user("", at="2026-11-02T11:49:31Z", tool_result={"task": {"id": "1"}}),
                       assistant(PROMISE), turn_end()])
_, verdicts, _ = machine.run()
check("a task created earlier in the promise's own turn backs it, so the judge decides",
      verdicts["alpha"]["sentences"][0]["code_reading"] == "judge"
      and verdicts["alpha"]["decision"] == "judge", verdicts["alpha"])


machine = Machine()
machine.seat("alpha", [user("a", at="2026-11-02T11:30:00Z"),
                       assistant("Ok.", at="2026-11-02T11:30:00Z"),
                       turn_end(at="2026-11-02T11:31:00Z"),
                       user("go", at="2026-11-02T11:49:00Z"),
                       assistant(tool=("TaskCreate", {"metadata": {"prerequisites": [
                           {"pr_merged": 927}]}}), at="2026-11-02T11:49:30Z"),
                       assistant(PROMISE), turn_end()])
_, verdicts, _ = machine.run()
check("a task created earlier in the promise's later turn backs it",
      verdicts["alpha"]["sentences"][0]["code_reading"] == "judge"
      and verdicts["alpha"]["decision"] == "judge", verdicts["alpha"])

for interruption in ("[Request interrupted by user]",
                     "[Request interrupted by user for tool use]\n"):
    machine = Machine()
    interrupted = user([{"type": "text", "text": interruption}], at="2026-11-02T11:36:00Z")
    machine.seat("alpha", [user("a", at="2026-11-02T11:30:00Z"),
                           assistant(tool=("TaskCreate", {"metadata": {"prerequisites": [
                               {"pr_merged": 927}]}}), at="2026-11-02T11:35:00Z"),
                           interrupted, user("new prompt", at="2026-11-02T11:49:00Z"),
                           assistant(PROMISE), turn_end()])
    _, verdicts, _ = machine.run()
    check(f"a task from a turn ended by {interruption!r} does not back the next turn's promise",
          verdicts["alpha"]["sentences"][0]["code_reading"] == "unbacked"
          and verdicts["alpha"]["decision"] == "send_unbacked", verdicts["alpha"])

for feedback in ("Stop hook feedback: finish the work.",
                 "Base directory for this skill: /skills/report"):
    for after_text in (False, True):
        machine = Machine()
        meta = {**user(feedback, at="2026-11-02T11:49:45Z"), "isMeta": True}
        records = [user("go", at="2026-11-02T11:49:00Z"),
                   assistant(tool=("TaskCreate", {"metadata": {"prerequisites": [
                       {"pr_merged": 927}]}}), at="2026-11-02T11:49:30Z")]
        records += ([assistant(PROMISE), meta] if after_text else [meta, assistant(PROMISE)])
        machine.seat("alpha", records + [turn_end()])
        code, verdicts, error = machine.run()
        check(f"mid-turn {feedback!r}, after text={after_text}: the task backs the promise",
              code == 0 and verdicts["alpha"]["decision"] == "judge"
              and verdicts["alpha"]["sentences"][0]["code_reading"] == "judge",
              (code, verdicts, error))

# --- sentences that are not raised; rules 3 to 5 then decide --------------------------------
for sentence, kind in (("Say the word and I'll merge it.", "conditional_on_user"),
                       ("I'll push it once you approve, your call.", "conditional_on_user")):
    machine = Machine()
    machine.seat("alpha", [user("go"), assistant(sentence), turn_end()])
    _, verdicts, _ = machine.run()
    check(f"not raised: {sentence!r}",
          [(s["kind"], s["code_reading"]) for s in verdicts["alpha"]["sentences"]]
          == [(kind, "not_raised")] and verdicts["alpha"].get("rule") == 4, verdicts["alpha"])
machine = Machine()
machine.seat("alpha", [user("go"), assistant("I'll merge it without pushing the tag."), turn_end()])
_, verdicts, _ = machine.run()
check("a negative sentence is not raised, and rules 3 to 5 decide",
      [(s["kind"], s["code_reading"]) for s in verdicts["alpha"]["sentences"]]
      == [("negative", "not_raised")] and verdicts["alpha"].get("rule") == 4, verdicts["alpha"])
machine = Machine()
machine.seat("alpha", [user("go"),
                       assistant("Here is the diff.\n```\n-old\n+new\n```\nI'll push it now."),
                       turn_end()])
_, verdicts, _ = machine.run()
check("a sentence after a closed code block is still read",
      [s["sentence"] for s in verdicts["alpha"]["sentences"]] == ["I'll push it now."]
      and verdicts["alpha"].get("rule") == 2, verdicts["alpha"])
machine = Machine()
machine.seat("alpha", [user("go"), assistant("Noted. From now on I check the size first."),
                       turn_end()])
_, verdicts, _ = machine.run()
check("a standing rule goes to the judge",
      ("standing_rule", "judge") in [(s["kind"], s["code_reading"])
                                     for s in verdicts["alpha"]["sentences"]], verdicts["alpha"])
machine = Machine()
machine.seat("alpha", [user("go"), assistant("Done; the tests pass.\n```\nI'll push now\n```"),
                       turn_end()])
_, verdicts, _ = machine.run()
check("a code block is not the agent's sentence",
      verdicts["alpha"]["sentences"] == [] and verdicts["alpha"]["rule"] == 4, verdicts["alpha"])

# --- only the last turn-ending message, unless --turn-ending-messages-since widens it -------
machine = Machine()
machine.seat("alpha", [user("a", at="2026-11-02T11:30:00Z"),
                       assistant(ANNOUNCED, at="2026-11-02T11:30:00Z"),
                       turn_end(at="2026-11-02T11:30:00Z"), user("b"), assistant("Done."),
                       turn_end()])
_, verdicts, _ = machine.run()
check("by default only the last turn-ending message is checked",
      verdicts["alpha"]["sentences"] == [], verdicts["alpha"])
_, verdicts, _ = machine.run("--turn-ending-messages-since", "2026-11-02T11:00:00Z")
check("--turn-ending-messages-since checks the earlier one too",
      [s["sentence"] for s in verdicts["alpha"]["sentences"]] == [ANNOUNCED], verdicts["alpha"])

# --- not idle -------------------------------------------------------------------------------
machine = Machine()
machine.seat("alpha", [user("go"), assistant(ANNOUNCED, at="2026-11-02T11:58:00Z"),
                       turn_end(at="2026-11-02T11:58:00Z")])
_, verdicts, _ = machine.run()
check("a token spent 2 minutes ago: not idle",
      verdicts["alpha"]["idle"] is False and verdicts["alpha"]["rule"] is None
      and verdicts["alpha"]["not_idle_because"] == ["a token was spent less than 5 minutes ago"],
      verdicts["alpha"])
machine = Machine()
machine.seat("alpha", [user("go"), assistant(ANNOUNCED), turn_end(), user("another prompt")])
_, verdicts, _ = machine.run()
check("a prompt after the turn ended: the turn has not ended",
      verdicts["alpha"]["idle"] is False
      and verdicts["alpha"]["not_idle_because"] == ["its last turn has not ended"],
      verdicts["alpha"])
project, _ = machine.seat("beta", IDLE_TURN)
subagents = project / "s-1" / "subagents"
subagents.mkdir(parents=True)
(subagents / "agent-x.jsonl").write_text(
    json.dumps(assistant("working", at="2026-11-02T11:59:00Z")) + "\n")
_, verdicts, _ = machine.run("--agent-seat", "beta")
check("a subagent spent a token a minute ago: not idle, and the source is the subagent's file",
      verdicts["beta"]["idle"] is False and verdicts["beta"]["last_activity"]
      == {"time": "2026-11-02T11:59:00Z", "source": str(subagents / "agent-x.jsonl")}
      and set(verdicts) == {"beta"}, verdicts)

# --- approval-walk items --------------------------------------------------------------------
machine = Machine()
machine.seat("alpha", IDLE_TURN)
machine.walk_minutes("alpha", "#next_to_present item 1 of 3\nnotes\n#next_to_present item 2 of 3\n")
_, verdicts, _ = machine.run()
check("a walk item waiting: not idle",
      verdicts["alpha"]["idle"] is False and verdicts["alpha"]["walk_items_waiting"][0]
      ["next_to_present"] == "item 2 of 3", verdicts["alpha"])
machine.walk_minutes("alpha", "#next_to_present item 2 of 3\n#approval_walk_paused later\n")
_, verdicts, _ = machine.run()
check("a paused walk has no item waiting", verdicts["alpha"]["idle"] is True, verdicts["alpha"])
machine.walk_minutes("alpha", "#next_to_present item 3 of 3\n#next_to_present none, closed\n")
_, verdicts, _ = machine.run()
check("a closed walk has no item waiting", verdicts["alpha"]["idle"] is True, verdicts["alpha"])
for minutes_text, what in (
        ("#next_to_present item 3 of 3\n#next_to_present closed\n", "closed by the short form"),
        ("#next_to_present item 2 of 9 #approval_walk_paused later\n", "paused on the marker's line"),
        ("#next_to_present none, closed\nThe line `#next_to_present item 1 of 2` was earlier.\n",
         "a marker inside a code span is not read")):
    machine.walk_minutes("alpha", minutes_text)
    _, verdicts, _ = machine.run()
    check(f"no walk item waiting: {what}",
          verdicts["alpha"]["idle"] is True and verdicts["alpha"]["walk_items_waiting"] == [],
          verdicts["alpha"])

# --- rule 1: a usage limit -------------------------------------------------------------------
machine = Machine()
machine.seat("alpha", [user("go"), assistant("working", at="2026-11-02T10:00:00Z"),
                       user("more"), usage_limit(1793620800 - 60)])
_, verdicts, _ = machine.run()
limit = verdicts["alpha"].get("usage_limit", {})
check("usage limit: rule 1, with the reset time passed and the account logged in",
      verdicts["alpha"].get("rule") == 1 and verdicts["alpha"].get("decision") == "session_limit"
      and limit.get("reset_time_passed") is True and limit.get("account_now_logged_in")
      == "account-1" and limit.get("record_uuid") == "limit-record", verdicts["alpha"])
machine.seat("alpha", [user("go"), usage_limit(1793620800 + 3600)])
_, verdicts, _ = machine.run()
check("usage limit not yet reset", verdicts["alpha"]["usage_limit"]["reset_time_passed"] is False,
      verdicts["alpha"])
machine.claude_json.unlink()
code, verdicts, _ = machine.run()
check("usage limit with no ~/.claude.json: rule 1, no account logged in, exit 0",
      code == 0 and verdicts["alpha"]["rule"] == 1
      and verdicts["alpha"]["usage_limit"]["account_now_logged_in"] is None, verdicts)
machine.claude_json.write_text("{not json")
code, verdicts, _ = machine.run()
check("usage limit with an unreadable ~/.claude.json: an error and exit 1",
      code == 1 and verdicts["alpha"]["rule"] is None and verdicts["alpha"]["errors"], verdicts)

# --- rule 3: a handoff put off, nothing running ----------------------------------------------
machine = Machine()
machine.seat("alpha", [user("go"), assistant("Done."), turn_end()])
marker = machine.handoffs / "s-1-handoff-deferred"
marker.write_text("")
os.utime(marker, (1793615400, 1793615400))
_, verdicts, _ = machine.run()
check("handoff put off and nothing running: rule 3 with code's text",
      verdicts["alpha"].get("rule") == 3 and verdicts["alpha"].get("text")
      == "Your handoff was put off at 2026-11-02T10:30:00Z and nothing is running now. "
         "Is now a good time to hand off?", verdicts["alpha"])

# --- what is running, and rule 5 -------------------------------------------------------------
machine = Machine()
machine.seat("alpha", [user("go"),
                       user("", at="2026-11-02T11:20:00Z",
                            tool_result={"status": "async_launched", "agentId": "agent-1"}),
                       user("", at="2026-11-02T11:25:00Z",
                            tool_result={"backgroundTaskId": "bash-1"}),
                       assistant("Waiting on both."), turn_end()])
_, verdicts, _ = machine.run()
check("a subagent and a background command running, each with its start: rule 5",
      verdicts["alpha"]["running"] == {
          "subagents": [{"id": "agent-1", "started": "2026-11-02T11:20:00Z"}],
          "background_commands": [{"id": "bash-1", "started": "2026-11-02T11:25:00Z"}]}
      and verdicts["alpha"]["rule"] == 5, verdicts["alpha"])
machine.seat("alpha", [user("go"),
                       user("", tool_result={"status": "async_launched", "agentId": "agent-1"}),
                       user("<task-notification><task-id>agent-1</task-id><status>completed"
                            "</status><result>done</result></task-notification>"),
                       assistant("Done."), turn_end()])
_, verdicts, _ = machine.run()
check("a subagent whose final report came is not running",
      verdicts["alpha"]["running"]["subagents"] == [] and verdicts["alpha"]["rule"] == 4,
      verdicts["alpha"])

# --- rule 4 against rule 5: open tasks and their prerequisites -------------------------------
machine = Machine()
machine.seat("alpha", [user("go"), assistant("Done."), turn_end()])
machine.task("alpha", "1", status="completed")
machine.task("alpha", "2", blocked_by=["3"])
machine.task("alpha", "3", metadata={"prerequisites": [{"pr_merged": 50}]})
machine.gh_responses.write_text(json.dumps({"pr:50": {"state": "OPEN"}}))
_, verdicts, _ = machine.run()
check("open tasks all held: rule 4, no wake",
      verdicts["alpha"]["rule"] == 4 and verdicts["alpha"]["open_tasks_nothing_holds"] == [],
      verdicts["alpha"])
machine.gh_responses.write_text(json.dumps({"pr:50": {"state": "MERGED"}}))
_, verdicts, _ = machine.run()
check("a task whose prerequisite is met: rule 5, and the task is named",
      verdicts["alpha"]["rule"] == 5
      and verdicts["alpha"]["open_tasks_nothing_holds"] == [{"id": "3", "subject": "task 3"}],
      verdicts["alpha"])
machine.gh_responses.write_text("{}")
machine.seat("beta", [user("go"), assistant("Done."), turn_end()])
code, verdicts, _ = machine.run()
check("gh fails: the agent-seat carries the error, the other is still reported, exit 1",
      code == 1 and verdicts["alpha"]["rule"] is None
      and "GitHub could not say" in verdicts["alpha"]["errors"][0]
      and verdicts["beta"]["rule"] == 4, verdicts)
machine = Machine()
for seat in ("alpha", "beta"):
    machine.seat(seat, [user("go"), assistant("Done."), turn_end()])
    machine.task(seat, "1", metadata={"prerequisites": [{"pr_merged": 50}]})
machine.gh_responses.write_text("{}")
code, verdicts, _ = machine.run()
check("two agent-seats share one prerequisite gh fails on: both carry the error, though the "
      "second reads the failed answer from the cache",
      code == 1 and all(verdicts[seat]["rule"] is None
                        and "GitHub could not say whether pr_merged 50" in verdicts[seat]["errors"][0]
                        for seat in ("alpha", "beta")), verdicts)

# --- read failures and what is not a failure -------------------------------------------------
machine = Machine()
_, transcript = machine.seat("alpha", IDLE_TURN, raw_tail=b'{"type": "assist')
code, verdicts, _ = machine.run()
check("a last line still being written is skipped", code == 0
      and verdicts["alpha"]["rule"] == 2, verdicts["alpha"])
transcript.write_bytes(b"not json\n" + transcript.read_bytes())
code, verdicts, _ = machine.run()
check("a line that is not JSON before the end: an error and exit 1",
      code == 1 and "line 1 is not UTF-8 JSON" in verdicts["alpha"]["errors"][0], verdicts)
machine = Machine()
machine.seat("alpha", IDLE_TURN,
             raw_tail=b'{"type":"user","toolUseResult":{"status":"async_launched","agentId":"ag')
machine.seat("beta", IDLE_TURN)
code, verdicts, _ = machine.run()
check("a last line still being written that records a launch: an error for that agent-seat, "
      "the other still reported, exit 1",
      code == 1 and verdicts["alpha"]["rule"] is None
      and "still being written" in verdicts["alpha"]["errors"][0]
      and verdicts["beta"]["rule"] == 2, verdicts)
machine = Machine()
machine.seat("alpha", IDLE_TURN)
machine.walk_minutes("alpha", b"#next_to_present item 1 of 2\n\xff\n")
code, verdicts, _ = machine.run()
check("walk-minutes that are not UTF-8: an error and exit 1",
      code == 1 and verdicts["alpha"]["errors"], verdicts)
machine = Machine()
machine.seat("alpha", records=None)
code, verdicts, _ = machine.run()
check("no transcript yet: not checked, exit 0",
      code == 0 and verdicts["alpha"]["not_checked"]
      == "the agent-session's transcript does not exist", verdicts)
machine.seat("beta", IDLE_TURN, state={"session_id": "s-1", "agent_exit_code": 0})
code, verdicts, _ = machine.run("--agent-seat", "beta")
check("an exited agent-session, named under the old key: not checked",
      code == 0 and verdicts["beta"]["session_id"] == "s-1"
      and verdicts["beta"]["not_checked"] == "its agent-session has exited", verdicts)
(machine.handoffs / "gamma-supervisor-state.json").write_text("{")
code, verdicts, _ = machine.run("--agent-seat", "gamma")
check("an unreadable supervisor state file: an error and exit 1",
      code == 1 and verdicts["gamma"]["errors"], verdicts)
(machine.handoffs / "gamma-supervisor-state.json").write_text("[]")
code, verdicts, _ = machine.run("--agent-seat", "gamma")
check("a supervisor state file that holds no JSON object: an error and exit 1",
      code == 1 and "holds JSON that is not an object" in verdicts["gamma"]["errors"][0], verdicts)

# --- more read failures, and lines a reader must step over ----------------------------------
machine = Machine()
_, transcript = machine.seat("alpha", records=None)
transcript.mkdir()
code, verdicts, _ = machine.run()
check("a transcript that cannot be read: an error and exit 1",
      code == 1 and "could not be read" in verdicts["alpha"]["errors"][0], verdicts)
machine = Machine()
_, transcript = machine.seat("alpha", [user("go"), assistant("Done. " + ANNOUNCED), turn_end()])
transcript.write_bytes(b"\n[1, 2]\n" + transcript.read_bytes())
code, verdicts, _ = machine.run()
check("a blank line and a JSON line that is no object are stepped over, and a sentence after "
      "one the lists miss is still found",
      code == 0 and [s["sentence"] for s in verdicts["alpha"]["sentences"]] == [ANNOUNCED],
      verdicts["alpha"])
machine.seat("beta", IDLE_TURN, session="s-2", state={"launched_session_id": ""})
code, verdicts, _ = machine.run("--agent-seat", "beta")
check("a supervisor that launched no agent-session: not checked",
      code == 0 and verdicts["beta"]["not_checked"]
      == "its handoff-supervisor has launched no agent-session", verdicts)
code, _, error = machine.run("--now", "soon")
check("--now that is not an ISO time: a usage error", code == 2 and "--now" in error, error)
code, _, error = machine.run("--turn-ending-messages-since", "soon")
check("--turn-ending-messages-since that is not an ISO time: a usage error",
      code == 2 and "--turn-ending-messages-since" in error, error)
machine = Machine()
machine.seat("alpha", [user("go"), assistant("Done."), turn_end()])
machine.task("alpha", "1", metadata={"prerequisites": [{"pr_merged": "fifty"}]})
machine.task("alpha", "2", metadata={"prerequisites": [{"pr_merged": 50}]})
machine.task("alpha", "3")
machine.gh_responses.write_text(json.dumps({"pr:50": {"state": "OPEN"}}))
_, verdicts, _ = machine.run()
check("tasks with unreadable or unmet prerequisites are held, and the next free task is still found",
      verdicts["alpha"]["open_tasks_nothing_holds"] == [{"id": "3", "subject": "task 3"}],
      verdicts["alpha"])
machine.task("alpha", "3", status="completed")
machine.task("alpha", "4", metadata={"prerequisites": [{"pr_merged": 51}, {"pr_merged": 52}]})
code, verdicts, _ = machine.run()
check("two failed gh calls: the error names the first",
      code == 1 and "pr_merged 51" in verdicts["alpha"]["errors"][0], verdicts["alpha"])
machine = Machine()
project, _ = machine.seat("alpha", IDLE_TURN)
subagents = project / "s-1" / "subagents"
subagents.mkdir(parents=True)
(subagents / "agent-a.jsonl").write_text(
    json.dumps(assistant("newer", at="2026-11-02T11:59:00Z")) + "\n"
    + json.dumps(assistant("older", at="2026-11-02T11:40:00Z")) + "\n")
(subagents / "agent-b.jsonl").write_text(
    json.dumps(assistant("oldest", at="2026-11-02T11:30:00Z")) + "\n")
_, verdicts, _ = machine.run()
check("the newest spend across subagent transcripts, whatever their order, is the last activity",
      verdicts["alpha"]["last_activity"] == {"time": "2026-11-02T11:59:00Z",
                                             "source": str(subagents / "agent-a.jsonl")},
      verdicts["alpha"])

# --- the task list is read as the due-task hook reads it ------------------------------------
machine = Machine()
machine.seat("alpha", [user("go"), assistant("Done."), turn_end()])
machine.task("alpha", "1", metadata={"waits_on": [{"pr_merged": 50}]})
machine.gh_responses.write_text(json.dumps({"pr:50": {"state": "OPEN"}}))
code, verdicts, _ = machine.run()
check("a task still under the old waits_on key, unmet, is held: rule 4, no wake",
      code == 0 and verdicts["alpha"]["rule"] == 4, verdicts["alpha"])
(machine.tasks / "nedschorus-alpha-tasks" / "2.json").write_text("{not json")
code, verdicts, _ = machine.run()
check("a task file that will not read: an error and exit 1, not rule 4",
      code == 1 and verdicts["alpha"]["rule"] is None
      and "2.json could not be read as a task" in verdicts["alpha"]["errors"][0]
      and "then run this program again" in verdicts["alpha"]["errors"][0], verdicts["alpha"])
machine = Machine()
machine.seat("alpha", [user("go"), assistant("Done."), turn_end()])
machine.seat("beta", [user("go"), assistant("Done."), turn_end()])
machine.task("alpha", "1", metadata={"prerequisites": [{"pr_merged": 51}]})
machine.task("beta", "1", metadata={"prerequisites": [{"pr_merged": 50}]})
machine.gh_responses.write_text(json.dumps({"pr:50": {"state": "MERGED"}}))
code, verdicts, _ = machine.run("--agent-seat", "alpha", "--agent-seat", "beta")
check("one agent-seat's gh failure is not reported for the next agent-seat",
      code == 1 and "pr_merged 51" in verdicts["alpha"]["errors"][0]
      and verdicts["beta"]["errors"] == [] and verdicts["beta"]["rule"] == 5, verdicts)

# --- rule 2 settled by code reads no task list ---------------------------------------------
machine = Machine()
machine.seat("alpha", [user("go"), assistant(PROMISE), turn_end()])
machine.task("alpha", "1", metadata={"prerequisites": [{"pr_merged": 51}]})
code, verdicts, _ = machine.run()
check("an unbacked promise is sent although a task's gh query would fail",
      code == 0 and verdicts["alpha"]["decision"] == "send_unbacked"
      and "if_every_sentence_backed" not in verdicts["alpha"], (code, verdicts["alpha"]))
machine = Machine()
machine.seat("alpha", [user("go"), assistant(PROMISE + " " + ANNOUNCED), turn_end()])
machine.task("alpha", "1", metadata={"prerequisites": [{"pr_merged": 51}]})
code, verdicts, _ = machine.run()
check("an unbacked promise beside a sentence for the judge: rule 2, no task list read",
      code == 0 and verdicts["alpha"]["rule"] == 2 and verdicts["alpha"]["decision"] == "judge"
      and "if_every_sentence_backed" not in verdicts["alpha"], (code, verdicts["alpha"]))

# --- the turn start keeps its fraction of a second -----------------------------------------
machine = Machine()
machine.seat("alpha", [user("a", at="2026-11-02T11:48:00Z"),
                       assistant(tool=("TaskCreate", {"metadata": {"prerequisites": [
                           {"pr_merged": 927}]}}), at="2026-11-02T11:49:00.200Z"),
                       turn_end(at="2026-11-02T11:49:00.300Z"),
                       user("go", at="2026-11-02T11:49:00.500Z"), assistant(PROMISE), turn_end()])
_, verdicts, _ = machine.run()
check("a task the previous turn made in the same second as the next prompt does not back it",
      verdicts["alpha"]["sentences"][0]["code_reading"] == "unbacked", verdicts["alpha"])

# --- the fields module finds what departs from it -------------------------------------------
good = {"agent_seat": "a", "session_id": None, "transcript_path": None, "checked_at": NOW,
        "errors": [], "rule": 4, "decision": "no_wake"}
check("the fields module passes a verdict that keeps to it",
      fields.verdict_field_problems(good) == [])
for broken, expected in (
        ({**good, "extra": 1}, "field extra is not a verdict field"),
        ({key: value for key, value in good.items() if key != "errors"}, "field errors is missing"),
        ({**good, "decision": "judge"}, "decision 'judge' is not one rule 4 gives"),
        ({**good, "rule": None}, "a decision is given with no rule"),
        ({**good, "rule": 2, "decision": "judge",
          "if_every_sentence_backed": {"rule": 1, "decision": "session_limit"}},
         "if_every_sentence_backed is not a decision of rules 3 to 5"),
        ({**good, "rule": 1, "decision": "session_limit", "usage_limit": {"resets_at": 1}},
         "usage_limit fields are ['resets_at']"),
        ({**good, "sentences": [{"sentence": "x"}]}, "a sentence's fields are ['sentence']"),
        ({**good, "sentences": [{"record_uuid": "u", "time": NOW, "sentence": "x",
                                 "kind": "boast", "code_reading": "judge"}]},
         "a sentence has kind 'boast'"),
        ("not an object", "the verdict is not a JSON object")):
    problems = fields.verdict_field_problems(broken)
    check(f"the fields module finds: {expected}",
          any(problem.startswith(expected) for problem in problems), problems)

shutil.rmtree(SUITE_ROOT, ignore_errors=True)
print()
if failures:
    print(f"{len(failures)} FAILED: {failures}")
    sys.exit(1)
print("all cases passed")
