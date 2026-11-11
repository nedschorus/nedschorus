#!/usr/bin/env python3
"""The idle sweep's second build-slice: find each idle ned-box agent-seat with something to do, and
wake it with a cross-session message, judged by a headless agent-session where code cannot decide.

Design: docs/issues/940-tasks-raise-themselves-when-their-due-time-passes.md, § The idle sweep.
Cron runs this every minute on ned-box, from the entry in
nc-systems/general-tools/scheduled-jobs-on-each-machine.json.

Each invocation, under a lock that keeps two from overlapping:
1. Reads its log, the one record of what it has done, and derives from it each agent-seat's state:
   the last check, the open wait and its step, the sentences already checked, each usage-limit
   record seen and woken, the account last seen, and the messages whose delivery is not yet
   checked.
2. Takes slice 1's verdict for each agent-seat, by calling verdict_for_seat in
   scripts/agent-seat-idle-sweep-verdicts-print.py, which is the only reader of the transcripts,
   walk-minutes and task lists.
3. When `oauthAccount.accountUuid` in ~/.claude.json differs from the account last logged, sends
   every agent-seat with a running agent-session the account-change notice, through one headless
   agent-session; for an agent-seat idle at a usage limit, that notice is its limit wake.
4. Looks, a minute or more after each send, for the message in the agent-seat's transcript, once
   the agent-seat's turn has ended, and writes a user-alert when it is not there.
5. For each idle agent-seat, applies the verdict's rule: rule 1 wakes it once its limit has ended;
   rule 2 has unbacked promises and announced actions judged and named to it; rule 3 sends the
   handoff text; rule 4 ends a wait no rule 2 message was sent on; rule 5 has the judge
   decide whether to message it, and write the message. A message starts a wait, unless a wait is
   already open: 15 minutes later, if the agent-seat is idle, code sends the escalation, which
   quotes the message that opened the wait, and 15 minutes after that writes the user a
   user-alert, once. The minutes both state are counted from the agent-seat's last token spent,
   the start of its current idle stretch.

Every message to an agent-seat goes through Sweep.send_wake_message, which ends it with
DO_NOT_REPLY_SENTENCE: the headless agent-session that sends it has exited by the time the
agent-seat reads it, so a reply fails.

Headless agent-sessions: `claude -p --model sonnet` in an empty working directory under the state
directory. A sender is allowed only SendMessage, ListAgents and ToolSearch; the rule 2 and rule 5
judges get no tool and send nothing. Each answers JSON through --json-schema, and code reads a
sender's SendMessage calls from its stream-json output and checks each against the agent-seat and
the text code wrote. Each is stopped after 5 minutes.

What it does not handle: it runs only on ned-box and reads only ned-box's agent-seats. One
invocation runs its headless agent-sessions one after another, so a slow judge delays every other
agent-seat's step, and the lock makes the next minute's invocation skip, until it ends. A wait
does not end when the agent-seat only replies to a message in text; it ends when the agent-seat
makes a tool call after the nudge that opened the wait, has nothing to do (rule 4) and no rule 2
message was sent on the wait, stops at a usage limit (rule 1), starts a new agent-session, or
spends tokens after the user was told. So an agent-seat that answers each message with a tool
call and goes idle again is nudged again, and never escalated.

How it fails, and what the user sees: a headless agent-session that fails, is stopped, answers
JSON code cannot use, or sends to the wrong entry or the wrong text; a message missing from the
agent-seat's transcript; and a read failure slice 1 reports for the same agent-seat with the same
text at every run for 2 minutes or more, each become a user-alert, written once, and the invocation
exits 1; the 2 minutes are counted from the failure's first run and go on through an invocation the
lock made skip, since only a run that does not meet the failure ends them. A read failure seen once only, such as the last line of a transcript
Claude Code is still writing, is logged and not alerted; a run that does not meet it again logs its end, so that it
coming back later is dated from its return. Any other failure, such as an unwritable log, prints a
traceback, writes one user-alert per distinct error, and exits 1. A message step is logged before
its send, so a failed send is not retried every minute: the wait goes on to its next step.
The harm it can cause is an extra message to an agent-seat, which costs that agent-seat one turn.
"""

import argparse
import fcntl
import importlib.util
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _load(module_name, path):
    specification = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


_SCRIPTS = Path(__file__).resolve().parent
verdicts_print = _load("agent_seat_idle_sweep_verdicts_print",
                       _SCRIPTS / "agent-seat-idle-sweep-verdicts-print.py")
fields = verdicts_print.fields
user_alerts = _load("user_alerts_pending_and_claimed_files_write_claim_release_and_delete_common",
                    _SCRIPTS.parent / "nc-systems" / "general-tools"
                    / "user-alerts-pending-and-claimed-files-write-claim-release-and-delete-common.py")
headless_command_line = _load(
    "claude_code_headless_run_command_line_prefix_with_no_connectors_and_explicit_permission_mode_common",
    _SCRIPTS.parent / "nc-systems" / "general-tools"
    / "claude-code-headless-run-command-line-prefix-with-no-connectors-and-explicit-permission-mode-common.py")

LOG_FILE = (Path.home() / "nedschorus-logs" / "agent-seat-idle-sweep"
            / "agent-seat-idle-sweep-messages-sent-and-verdicts.jsonl")
STATE_DIRECTORY = (Path.home() / ".local" / "state" / "nedschorus"
                   / "agent-seat-idle-sweep-run-lock-and-headless-agent-session-empty-working-directory")
# The folder's name is the name the receiving agent-seat sees the message come from.
HEADLESS_WORKING_DIRECTORY_NAME = "agent-seat-idle-sweep"
RUN_FAILURES_ALERTED_FILE_NAME = "run-failures-alerted.txt"

WAIT_STEP_SECONDS = 15 * 60
JUDGE_ASK_AGAIN_SECONDS = 15 * 60
LIMIT_WAKE_GRACE_SECONDS = 5 * 60
DELIVERY_CHECK_AFTER_SECONDS = 60
# Claude Code stamps a record when it writes it, which may be a moment before the send returns.
DELIVERY_CLOCK_SLACK_SECONDS = 120
READ_FAILURE_ALERT_AFTER_SECONDS = 2 * 60
HEADLESS_TIMEOUT_SECONDS = 5 * 60
HEADLESS_MODEL = "sonnet"
SENDING_TOOLS = "SendMessage,ListAgents,ToolSearch"
JUDGED_TEXT_CHARACTERS = 4000

NUDGE, ESCALATE, TELL_USER = "nudge", "escalate", "tell_user"
# A wait step recording that the wait carries a rule 2 message, which rule 4 does not settle.
PROMISE = "promise"
LIMIT_WAKE, ACCOUNT_NOTICE = "limit_wake", "account_notice"

DO_NOT_REPLY_SENTENCE = "Do not reply to this message: its sender has exited, so a reply fails."
ESCALATION_TEXT = ("You've given this {minutes} minutes, please check; if not sure, hand off. At "
                   "{nudge_time} the idle sweep wrote this, which you have not acted on:\n\n"
                   "{quoted_nudge}")
LIMIT_WAKE_TEXT = ("The usage limit that stopped you has ended: {why}. Carry on with the work the "
                   "limit stopped.")
LIMIT_ENDED_BY_RESET = "its reset time has passed"
LIMIT_ENDED_BY_ACCOUNT = "the claude.ai account logged in on {machine} changed"
ACCOUNT_NOTICE_TEXT = (
    "The claude.ai account logged in on {machine} changed at {time}. Usage limits are now the new "
    "account's, so a limit message you saw before then, with its reset time, may no longer apply. "
    "Retry now any work a usage limit stopped, such as a subagent or a cold-read-cell; if the retry "
    "stops on a limit again, that limit is the new account's. A page you published to claude.ai "
    "under the earlier account, such as an approval-walk item page, may not open for the user; "
    "GitHub issue [A read-only web server on ned-box renders Markdown files as web pages on the "
    "LAN, for approval-walk item pages and other pages agents publish to claude.ai that only show "
    "text](https://github.com/nedschorus/nedschorus/issues/2175) covers serving such pages from "
    "ned-box.")
UNBACKED_SENTENCE_LINES = {
    fields.ANNOUNCED_ACTION: ("You said \"{sentence}\" {minutes} minutes ago and have not done it. "
                              "Do it now, or tell the user why not."),
    fields.PROMISE_AFTER_EVENT: ("You promised \"{sentence}\". Record it as a task whose "
                                 "prerequisites name the event, or tell the user you take the "
                                 "promise back."),
    fields.STANDING_RULE: ("You said \"{sentence}\". Back it with the hook or test that enforces it, "
                           "or a task to build one and a proposal to the user, or tell the user you "
                           "take it back."),
    fields.HOLD: ("You said \"{sentence}\". Record a task whose prerequisites name what releases the "
                  "hold, or tell the user you are no longer holding."),
}

SEND_ANSWER_SCHEMA = {"type": "object", "required": ["sent", "reason"],
                      "properties": {"sent": {"type": "boolean"}, "reason": {"type": "string"}}}
IDLE_JUDGE_ANSWER_SCHEMA = {
    "type": "object", "required": ["send", "message", "reason"],
    "properties": {"send": {"type": "boolean"}, "message": {"type": "string"},
                   "reason": {"type": "string"}}}
SENTENCES_ANSWER_SCHEMA = {
    "type": "object", "required": ["sentences"],
    "properties": {"sentences": {"type": "array", "items": {
        "type": "object", "required": ["index", "backed", "reason"],
        "properties": {"index": {"type": "integer"}, "backed": {"type": "boolean"},
                       "reason": {"type": "string"}}}}}}

FIND_THE_ENTRY = """\
Find the agent-seat's entry with ListAgents (load ListAgents and SendMessage with ToolSearch first \
if they are not loaded). Write only to the one entry whose name is the agent-seat's name, that is \
shown as interactive, and whose tmux pane is in the tmux session named after the agent-seat, as in \
"{seat} [9cbc4b] · interactive · tmux {seat}:@0.%0". Never write to a Remote Control entry, or to \
any other entry. In SendMessage's "to", give the name and the ref as ListAgents lists them, as in \
"{seat} [9cbc4b]". If there is no such entry, or more than one, send nothing."""

SENDER_PROMPT = """\
You deliver one message for the idle sweep, a program on ned-box that wakes idle agent-seats. You \
judge nothing: the program has decided the message is sent.

The agent-seat is {seat}. {find_the_entry}

Send it one message with SendMessage, whose "message" is the text between the two lines of dashes \
below, exactly as written, with nothing added or removed. Then answer: sent true if SendMessage \
succeeded, otherwise false, and reason, one sentence.
----------
{text}
----------"""

NOTICE_SENDER_PROMPT = """\
You deliver one notice for the idle sweep, a program on ned-box. You judge nothing: the program has \
decided the notice is sent.

Send it, with one SendMessage call for each, to each of these agent-seats: {seats}. For each \
agent-seat, {find_the_entry}

Each message is the text between the two lines of dashes below, exactly as written, with nothing \
added or removed. Then answer: sent true if every send succeeded, otherwise false, and reason, one \
sentence naming any agent-seat you could not send to.
----------
{text}
----------"""

IDLE_JUDGE_PROMPT = """\
You judge one idle agent-seat for the idle sweep, a program on ned-box. The agent-seat {seat} has \
spent no tokens for {idle_minutes} minutes, and its last turn has ended. Code could not settle the \
case: something may be left for it to do, or it may rightly be waiting. The facts code found are in \
the JSON below. An approval-walk item waiting on the user holds back only that walk, not the \
agent-seat's other work.

Judge whether the agent-seat could act now. If it could, write it one short message saying what you \
saw. Name each background command and subagent that has not finished or reported, \
with how long it has run, and ask whether it is taking longer than expected, such as "Your \
test-suite run started 25 minutes ago and has not finished. Is it taking longer than expected?". \
A subagent with stopped_at has stopped and reported: it is not running, and only the background \
commands it launched, under own_running_background_commands, still run. Say so, and name each of \
those commands with how long it has run, such as "Your subagent ae10c20d94ca876c9 reported 124 \
minutes ago, but background command bgyicuvln, which it started 131 minutes ago, has not \
finished. Is it still needed?". \
With nothing running, ask what is going on, such as "You said "I'm starting the PR 1633 work now" 6 \
minutes ago and have made no tool call since. What's going on?". If it could not act now, write \
no message. Send nothing yourself: the program sends the message.

Answer: send, whether the agent-seat should get a message; message, the message, or an empty string \
when send is false; and reason, one sentence on why, such as "a subagent started 3 minutes ago is \
still running".

{facts}"""

SENTENCES_JUDGE_PROMPT = """\
You judge sentences for the idle sweep, a program on ned-box. The agent-seat {seat} is idle, and \
messages that ended its turns hold the sentences below, each a promise or an announced action. For \
each sentence, judge whether it is backed, by these rules:

- An announced action, such as "Next I'm starting the pull request", is backed when a tool call in \
the same turn, before or after the sentence, or a later one does the action, or a background task \
it started is still running.
- A promise to act after an event, such as "I'll report when PR 927 merges", is backed by a task \
whose prerequisites or blockedBy name the event, so the idle check raises it.
- A standing rule, such as "from now on" or "Noted", is backed by the hook or test that enforces \
it, or by a task to build one together with a proposal to the user; a memory never backs it.
- A hold, such as "I'll hold", is backed by a task whose prerequisites name what releases the hold.

The tool calls the agent-seat made from the earliest sentence's turn on are in the JSON below, with \
the tasks they created or updated and the files they changed; so are its open tasks that have \
prerequisites or blockedBy, whenever they were created, and what is running. Send nothing. \
Answer, for every sentence by its index, backed true or false, and reason, one sentence.

{facts}"""


# --- The log, and the state derived from it ---

class IdleSweepLogLineNotUtf8Json(Exception):
    pass


class SweepLog:
    """The append-only JSONL log: each message sent, each verdict, each user-alert written."""

    def __init__(self, path):
        self.path = path
        self.events = []
        # An event written after a last line with no newline would join it into a line that, no
        # longer last, would stop every later read. A cut-short line the read skipped is dropped
        # by truncating to this size; a whole one the read accepted only gets its newline. Set at
        # the read, so that an append need not read the log again.
        self.truncate_to = None
        self.add_newline = False
        if path.exists():
            data = path.read_bytes()
            lines = data.split(b"\n")
            for number, raw in enumerate(lines, start=1):
                if not raw.strip():
                    continue
                try:
                    event = json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, ValueError) as error:
                    # A last line with no newline is one an invocation was stopped while writing.
                    if number == len(lines):
                        self.truncate_to = data.rfind(b"\n") + 1
                        continue
                    raise IdleSweepLogLineNotUtf8Json(
                        f"{path} line {number} is not UTF-8 JSON: {error}") from error
                if isinstance(event, dict):
                    self.events.append(event)
            self.add_newline = (self.truncate_to is None and bool(data)
                                and not data.endswith(b"\n"))

    def append(self, event, now):
        event = {"at": iso(now), **event}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.truncate_to is not None:
            os.truncate(self.path, self.truncate_to)
        elif self.add_newline:
            with self.path.open("ab") as stream:
                stream.write(b"\n")
        self.truncate_to, self.add_newline = None, False
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
        self.events.append(event)
        return event

    def of_seat(self, seat, *kinds):
        return [event for event in self.events
                if event.get("agent_seat") == seat and event.get("event") in kinds]

    def last_check(self, seat):
        checks = self.of_seat(seat, "checked")
        return checks[-1] if checks else None

    def open_wait(self, seat):
        wait = None
        for event in self.of_seat(seat, "wait_step", "wait_ended"):
            if event["event"] == "wait_ended":
                wait = None
            elif event["step"] == NUDGE:
                wait = {"session_id": event["session_id"], "first_idle_at": event["first_idle_at"],
                        NUDGE: event["at"], "nudge_text": event["text"]}
                if event.get("rule") == 2:
                    wait[PROMISE] = event["at"]
            elif wait is not None:
                wait[event["step"]] = event["at"]
        return wait

    def last_judge_answer(self, seat):
        answers = [event for event in self.of_seat(seat, "judge_answer") if event.get("rule") == 5]
        return answers[-1] if answers else None

    def checked_sentences(self, seat):
        return {(event["record_uuid"], event["sentence"])
                for event in self.of_seat(seat, "sentence_checked")}

    def limit_account(self, seat, record_uuid):
        """The account logged in when code first saw the limit record, the first one known."""
        accounts = [event.get("account") for event in self.of_seat(seat, "limit_seen")
                    if event["record_uuid"] == record_uuid]
        return next((account for account in accounts if account), None), bool(accounts)

    def limit_wakes(self, seat):
        return {event["record_uuid"]: event["at"] for event in self.of_seat(seat, "limit_wake")}

    def last_account(self):
        seen = [event for event in self.events if event.get("event") == "account_seen"]
        return seen[-1]["account"] if seen else None

    def deliveries_pending(self):
        checked = {event["message_id"] for event in self.events
                   if event.get("event") == "delivery_checked"}
        return [event for event in self.events
                if event.get("event") == "message_sent" and event["message_id"] not in checked]

    def read_failure_first_seen(self, seat, text):
        """When the failure's current run began: its latest read_failure, unless a
        read_failure_ended follows it."""
        first_seen = None
        for event in self.of_seat(seat, "read_failure", "read_failure_ended"):
            if event["error"] == text:
                first_seen = event["at"] if event["event"] == "read_failure" else None
        return first_seen

    def read_failures_open(self):
        open_failures = set()
        for event in self.events:
            if event.get("event") in ("read_failure", "read_failure_ended"):
                key = (event["agent_seat"], event["error"])
                if event["event"] == "read_failure":
                    open_failures.add(key)
                else:
                    open_failures.discard(key)
        return open_failures

    def alerted(self, key):
        return any(event.get("event") == "user_alert" and event.get("key") == key
                   for event in self.events)


def iso(moment):
    return verdicts_print.iso(moment)


def parse_time(stamp):
    return verdicts_print.parse_time(stamp)


def seconds_between(earlier, later):
    earlier = parse_time(earlier) if isinstance(earlier, str) else earlier
    return (later - earlier).total_seconds()


# --- Headless agent-sessions ---

class HeadlessOutcome:
    def __init__(self):
        self.error = None          # why the headless agent-session failed, or None
        self.answer = None         # its --json-schema answer
        self.sends = []            # [{"to", "message", "succeeded", "result"}]


def claude_binary():
    # Cron's PATH does not hold ~/.local/bin, where claude is installed.
    return shutil.which("claude") or str(Path.home() / ".local" / "bin" / "claude")


def run_headless(prompt, schema, tools, working_directory, timeout_seconds):
    """Run one headless agent-session and read its SendMessage calls and its answer."""
    outcome = HeadlessOutcome()
    command = headless_command_line.claude_code_headless_run_command_line_prefix_build(
        "dontAsk", program=claude_binary()) + [
        "--model", HEADLESS_MODEL, "--output-format", "stream-json", "--verbose",
        "--json-schema", json.dumps(schema), "--tools", tools]
    if tools:
        command += ["--allowedTools", tools]
    working_directory.mkdir(parents=True, exist_ok=True)
    try:
        process = subprocess.Popen(command, cwd=str(working_directory), stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                   start_new_session=True)
    except OSError as error:
        outcome.error = f"could not start claude: {error}"
        return outcome
    try:
        stdout, stderr = process.communicate(prompt, timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        stdout, stderr = process.communicate()
        outcome.error = f"stopped after {timeout_seconds} seconds"
    calls, result = {}, None
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if not isinstance(event, dict):
            continue
        if event.get("type") == "result":
            result = event
        content = (event.get("message") or {}).get("content")
        for block in content if isinstance(content, list) else []:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use" and block.get("name") == "SendMessage":
                tool_input = block.get("input") or {}
                calls[block.get("id")] = {"to": str(tool_input.get("to", "")),
                                          "message": str(tool_input.get("message", "")),
                                          "succeeded": False, "result": None}
            elif block.get("type") == "tool_result" and block.get("tool_use_id") in calls:
                call = calls[block["tool_use_id"]]
                call["succeeded"] = not block.get("is_error")
                call["result"] = str(block.get("content"))[:500]
    outcome.sends = list(calls.values())
    if outcome.error:
        return outcome
    if process.returncode != 0:
        outcome.error = f"claude exited {process.returncode}: {(stderr or stdout)[-500:].strip()}"
    elif result is None:
        outcome.error = f"claude gave no result event: {stdout[-500:]!r}"
    elif result.get("is_error") or result.get("subtype") != "success":
        outcome.error = f"claude reported an error: {str(result.get('result'))[:500]}"
    elif not isinstance(result.get("structured_output"), dict):
        outcome.error = "claude gave no JSON answer"
    else:
        outcome.answer = result["structured_output"]
    return outcome


def entry_seat(to):
    """The agent-seat's name in a SendMessage "to", which may carry " [ref]" after it."""
    return to.split(" [", 1)[0].strip()


def send_problems(outcome, seats, text):
    """What is wrong with a sender's sends: each must go to one of the agent-seats with the text."""
    problems = [f"sent to {send['to']!r}, which is not {', '.join(seats)}"
                for send in outcome.sends if entry_seat(send["to"]) not in seats]
    for send in outcome.sends:
        # Compared as the delivery check compares: a sender may reflow the lines of the text.
        if (entry_seat(send["to"]) in seats
                and " ".join(send["message"].split()) != " ".join(text.split())):
            problems.append(f"sent {entry_seat(send['to'])} a text other than the one code wrote")
    for seat in seats:
        if not any(send["succeeded"] and entry_seat(send["to"]) == seat for send in outcome.sends):
            problems.append(f"no SendMessage to {seat} succeeded")
    return problems


# --- One invocation ---

class Sweep:
    def __init__(self, log, now, paths, state_directory, timeout_seconds, machine):
        self.log = log
        self.now = now
        self.paths = paths
        self.working_directory = state_directory / HEADLESS_WORKING_DIRECTORY_NAME
        self.timeout_seconds = timeout_seconds
        self.machine = machine
        self.failed = False
        self.read_failures_this_run = set()
        self.started_monotonic = time.monotonic()

    def current(self):
        """The run's time plus the time the run has taken: headless agent-sessions run one after
        another, so a step logged late in a run must not carry the run's start. Whole seconds, so
        that a run that takes none logs the run's time itself."""
        return self.now + timedelta(seconds=int(time.monotonic() - self.started_monotonic))

    def record(self, event):
        return self.log.append(event, self.current())

    def alert(self, key, title, text, action, failure=True):
        """Write a user-alert once for each key, and log it."""
        self.failed = self.failed or failure
        if self.log.alerted(key):
            return None
        alert_id = user_alerts.user_alert_write_to_pending(title, text, action, now=self.current())
        self.record({"event": "user_alert", "key": key, "alert_id": alert_id, "title": title})
        print(f"user-alert {alert_id}: {title}", flush=True)
        return alert_id

    def headless_failed(self, seat, purpose, problem):
        self.failed = True
        self.record({"event": "headless_failed", "agent_seat": seat, "purpose": purpose,
                     "problem": problem})
        # One user-alert a day for each distinct failure, such as claude being logged out.
        self.alert(f"headless-failed:{seat}:{purpose}:{problem}:{self.now.date()}",
                   f"The idle sweep's headless agent-session for {seat} failed",
                   f"The idle sweep started a headless agent-session to {purpose} for the "
                   f"agent-seat {seat}, and it failed: {problem}",
                   "An agent on ned-box can read the idle sweep's log, "
                   f"{self.log.path}, and the cron output log, and check whether {seat} needs a "
                   "message; run `claude -p` by hand on ned-box to see whether claude is logged out.")

    def send_wake_message(self, seats, text):
        """The one way a message reaches an agent-seat: end the text with DO_NOT_REPLY_SENTENCE and
        have one headless agent-session send it to each of the seats. Returns the text as sent,
        the headless outcome and the time the send started."""
        text = f"{text}\n\n{DO_NOT_REPLY_SENTENCE}"
        if len(seats) == 1:
            prompt = SENDER_PROMPT.format(seat=seats[0], text=text,
                                          find_the_entry=FIND_THE_ENTRY.format(seat=seats[0]))
        else:
            prompt = NOTICE_SENDER_PROMPT.format(
                seats=", ".join(seats), text=text,
                find_the_entry=FIND_THE_ENTRY.format(seat="<agent-seat>"))
        started_at = self.current()
        outcome = run_headless(prompt, SEND_ANSWER_SCHEMA, SENDING_TOOLS, self.working_directory,
                               self.timeout_seconds)
        return text, outcome, started_at

    def send(self, seat, verdict, text, step):
        """Send code's text to one agent-seat; log the send for the delivery check."""
        text, outcome, started_at = self.send_wake_message([seat], text)
        problems = [outcome.error] if outcome.error else send_problems(outcome, [seat], text)
        if problems:
            self.headless_failed(seat, f"send its {step} message", "; ".join(problems))
            return False
        self.message_sent(seat, verdict, text, step, started_at)
        return True

    def message_sent(self, seat, verdict, text, step, started_at):
        # The delivery check compares transcript times with the send's start: a sender may run on
        # for minutes after its SendMessage, and the record is written when it ends.
        self.record({"event": "message_sent", "agent_seat": seat, "step": step, "text": text,
                     "send_started_at": iso(started_at),
                     "message_id": uuid.uuid4().hex, "session_id": verdict.get(fields.SESSION_ID),
                     "transcript_path": verdict.get(fields.TRANSCRIPT_PATH)})

    # --- The account ---

    def account_change(self, verdicts):
        try:
            account = verdicts_print.logged_in_account(self.paths.claude_json)
        except verdicts_print.ReadFailure as error:
            self.read_failure("the account check", str(error))
            return
        last = self.log.last_account()
        # A missing account, as in the middle of a switch, is not a change.
        if account is None or account == last:
            return
        self.record({"event": "account_seen", "account": account})
        if last is None:
            return
        seats = [seat for seat, verdict in verdicts.items()
                 if verdict.get(fields.SESSION_ID) and not verdict.get(fields.NOT_CHECKED)]
        text = ACCOUNT_NOTICE_TEXT.format(machine=self.machine, time=iso(self.now))
        self.record({"event": "account_notice", "old_account": last, "new_account": account,
                     "agent_seats": seats})
        if not seats:
            return
        text, outcome, started_at = self.send_wake_message(seats, text)
        if outcome.error:
            self.headless_failed(", ".join(seats), "send the account-change notice", outcome.error)
            return
        wrong = [problem for problem in send_problems(outcome, seats, text)
                 if not problem.startswith("no SendMessage")]
        if wrong:
            self.headless_failed(", ".join(seats), "send the account-change notice", "; ".join(wrong))
        # The delivery check looks in every listed agent-seat's transcript, sent to or not.
        for seat in seats:
            self.message_sent(seat, verdicts[seat], text, ACCOUNT_NOTICE, started_at)
            limit = verdicts[seat].get(fields.USAGE_LIMIT)
            if verdicts[seat].get(fields.RULE) == 1 and limit:
                self.record({"event": "limit_wake", "agent_seat": seat,
                             "record_uuid": limit["record_uuid"],
                             "why": "the account-change notice is its wake"})

    # --- Delivery ---

    def delivery_checks(self, verdicts):
        for sent in self.log.deliveries_pending():
            if seconds_between(sent["at"], self.now) < DELIVERY_CHECK_AFTER_SECONDS:
                continue
            seat = sent["agent_seat"]
            verdict = verdicts.get(seat, {})
            # A record written before the send's start was logged has only its "at", and stays
            # pending in the log until it is checked.
            send_started_at = sent.get("send_started_at", sent["at"])
            try:
                found = message_in_transcript(Path(sent["transcript_path"]), sent["text"],
                                              parse_time(send_started_at))
            except verdicts_print.ReadFailure as error:
                self.read_failure(seat, str(error))
                continue
            same_session = verdict.get(fields.SESSION_ID) == sent["session_id"]
            if not found and same_session and verdict.get(fields.TURN_ENDED) is False:
                continue  # the turn running at the send has not ended; it may yet read the message
            self.record({"event": "delivery_checked", "agent_seat": seat,
                         "message_id": sent["message_id"], "found": found})
            if not found:
                step = sent["step"].replace("_", " ")
                self.alert(f"delivery:{sent['message_id']}",
                           f"The idle sweep's {step} message did not reach {seat}",
                           f"At {sent['at']} the idle sweep sent {seat} this cross-session "
                           f"message, and its transcript {sent['transcript_path']} does not hold "
                           f"it: {sent['text']}",
                           f"An agent on ned-box can run ListAgents to see whether {seat} has more "
                           "than one entry, such as an offline Remote Control one, and send it the "
                           "message with SendMessage.")

    # --- Read failures ---

    def read_failure(self, seat, text):
        self.read_failures_this_run.add((seat, text))
        first_seen = self.log.read_failure_first_seen(seat, text)
        if first_seen is None:
            self.record({"event": "read_failure", "agent_seat": seat, "error": text})
            return
        if seconds_between(first_seen, self.now) >= READ_FAILURE_ALERT_AFTER_SECONDS:
            # Keyed by the text alone: two readers of one broken file, such as ~/.claude.json,
            # report it in the same words.
            self.alert(f"read-failure:{text}",
                       f"The idle sweep cannot read what it needs for {seat}",
                       f"Since {first_seen} the idle sweep has failed, each minute, to read: {text}",
                       "An agent on ned-box can open the file the failure names and repair it, or "
                       "tell the user what is wrong with it; until then the idle sweep does not "
                       f"check {seat}.")

    def read_failures_end(self):
        """A failure this invocation did not meet again has ended, so that one coming back later
        is dated from its return."""
        for seat, text in sorted(self.log.read_failures_open() - self.read_failures_this_run):
            self.record({"event": "read_failure_ended", "agent_seat": seat, "error": text})

    # --- One idle agent-seat ---

    def handle_seat(self, seat, verdict, transcript_read_at):
        session = verdict[fields.SESSION_ID]
        stretch = (verdict.get(fields.LAST_ACTIVITY) or {}).get("time")
        wait = self.log.open_wait(seat)
        if wait and wait["session_id"] != session:
            self.end_wait(seat, "a new agent-session")
            wait = None
        check = self.log.last_check(seat)
        if not (check and check["session_id"] == session and check["last_activity"] == stretch):
            self.record({"event": "checked", "agent_seat": seat, "session_id": session,
                         "transcript_read_at": iso(transcript_read_at),
                         "last_activity": stretch, "rule": verdict[fields.RULE],
                         "decision": verdict.get(fields.DECISION)})
        rule, text = verdict[fields.RULE], verdict.get(fields.TEXT)
        if rule == 1:
            if wait:
                self.end_wait(seat, "a usage limit")
            self.usage_limit(seat, verdict)
            return
        worked_at = verdict.get(fields.LAST_TOOL_CALL_AT)
        if wait and worked_at and parse_time(worked_at) > parse_time(wait[NUDGE]):
            self.end_wait(seat, "it made a tool call after the nudge")
            wait = None
        if wait and TELL_USER in wait and stretch and parse_time(stretch) > parse_time(wait[TELL_USER]):
            self.end_wait(seat, "it spent tokens after the user was told")
            wait = None
        promise_text = None
        if rule == 2:
            outcome, promise_text = self.sentences(seat, verdict)
            fallback = verdict.get(fields.IF_EVERY_SENTENCE_BACKED)
            if outcome == "all backed" and fallback is not None:
                rule, text = fallback[fields.RULE], fallback.get(fields.TEXT)
            elif not promise_text:
                rule = None
        # Nothing to do settles the open tasks a rule 3 or 5 message was about, but not a promise
        # a rule 2 message named, whatever message opened the wait it was sent on.
        if rule == 4 and wait and PROMISE not in wait:
            self.end_wait(seat, "nothing to do")
            wait = None
        if wait:
            self.due_step(seat, verdict, wait, stretch)
        if promise_text:
            # A promise given in answer to a message goes on the open wait, so that repeated
            # promises cannot put off its escalation and the user-alert.
            if not wait:
                self.start_wait(seat, verdict, stretch, promise_text, 2)
            elif PROMISE not in wait:
                self.record({"event": "wait_step", "agent_seat": seat, "step": PROMISE})
            self.send(seat, verdict, promise_text, NUDGE)
        elif not wait:
            self.nudge(seat, verdict, rule, text, stretch)

    def end_wait(self, seat, why):
        self.record({"event": "wait_ended", "agent_seat": seat, "why": why})

    def start_wait(self, seat, verdict, stretch, step_text, rule):
        self.record({"event": "wait_step", "agent_seat": seat, "step": NUDGE, "rule": rule,
                     "session_id": verdict[fields.SESSION_ID], "first_idle_at": stretch,
                     "text": step_text})

    def due_step(self, seat, verdict, wait, stretch):
        """The step of an open wait that is due: the escalation 15 minutes after the nudge, then
        the user-alert 15 minutes after the escalation; after that, none."""
        if TELL_USER in wait:
            return
        minutes = int(seconds_between(stretch or wait[NUDGE], self.now) // 60)
        if ESCALATE in wait:
            if seconds_between(wait[ESCALATE], self.now) >= WAIT_STEP_SECONDS:
                self.record({"event": "wait_step", "agent_seat": seat, "step": TELL_USER})
                self.alert(f"tell-user:{seat}:{wait[NUDGE]}",
                           f"{seat} has been idle {minutes} minutes after a nudge and an escalation",
                           f"The idle sweep found {seat} idle with something to do, messaged it "
                           f"at {wait[NUDGE]} and escalated at {wait[ESCALATE]}, and it is idle "
                           f"again. Its transcript is {verdict[fields.TRANSCRIPT_PATH]}. The idle "
                           "sweep sends it nothing more until it spends tokens and goes idle again.",
                           f"An agent on ned-box can read {seat}'s transcript and its tmux session "
                           f"{seat} to see why it stopped, and message it with SendMessage; the "
                           "user may want to look at it himself.", failure=False)
            return
        if seconds_between(wait[NUDGE], self.now) >= WAIT_STEP_SECONDS:
            text = ESCALATION_TEXT.format(
                minutes=minutes, nudge_time=parse_time(wait[NUDGE]).strftime("%Y-%m-%d %H:%MZ"),
                quoted_nudge="\n".join(f"> {line}" for line in wait["nudge_text"].split("\n")))
            self.record({"event": "wait_step", "agent_seat": seat, "step": ESCALATE, "text": text})
            self.send(seat, verdict, text, ESCALATE)

    def nudge(self, seat, verdict, rule, text, stretch):
        if rule == 3:
            self.start_wait(seat, verdict, stretch, text, 3)
            self.send(seat, verdict, text, NUDGE)
        elif rule == 5:
            self.judge_idle_seat(seat, verdict, stretch)

    def facts(self, seat, verdict):
        running = verdict.get(fields.RUNNING) or {}
        def with_minutes(items):
            own = fields.SUBAGENT_OWN_RUNNING_BACKGROUND_COMMANDS
            return [{**item, "minutes_running": int(seconds_between(item["started"], self.now) // 60)
                     if item.get("started") else None,
                     **({own: with_minutes(item[own])} if own in item else {})} for item in items]
        last_message = dict(verdict.get(fields.LAST_TURN_ENDING_MESSAGE) or {})
        if last_message.get("text"):
            last_message["text"] = last_message["text"][-JUDGED_TEXT_CHARACTERS:]
        return {"agent_seat": seat, "tmux_session": seat, "now": iso(self.now),
                "last_token_spent_at": (verdict.get(fields.LAST_ACTIVITY) or {}).get("time"),
                "last_turn_ending_message": last_message or None,
                "open_tasks_nothing_holds": verdict.get(fields.OPEN_TASKS_NOTHING_HOLDS),
                "handoff_deferral_marker_file": verdict.get(fields.HANDOFF_DEFERRED_MARKER),
                "approval_walk_items_waiting_on_the_user":
                    verdict.get(fields.APPROVAL_WALK_ITEMS_WAITING_ON_THE_USER),
                "running_subagents": with_minutes(running.get("subagents", [])),
                "running_background_commands": with_minutes(running.get("background_commands", []))}

    def judge_idle_seat(self, seat, verdict, stretch):
        answer = self.log.last_judge_answer(seat)
        if (answer and answer["session_id"] == verdict[fields.SESSION_ID]
                and answer["last_activity"] == stretch
                and seconds_between(answer["at"], self.now) < JUDGE_ASK_AGAIN_SECONDS):
            return
        facts = dict(self.facts(seat, verdict), step=NUDGE)
        idle_minutes = int(seconds_between(stretch, self.now) // 60) if stretch else None
        prompt = IDLE_JUDGE_PROMPT.format(seat=seat, idle_minutes=idle_minutes,
                                          facts=json.dumps(facts, indent=1, ensure_ascii=False))
        outcome = run_headless(prompt, IDLE_JUDGE_ANSWER_SCHEMA, "", self.working_directory,
                               self.timeout_seconds)
        problem = outcome.error or idle_judge_answer_problem(outcome.answer)
        answer = outcome.answer or {}
        self.record({"event": "judge_answer", "agent_seat": seat, "rule": 5,
                     "session_id": verdict[fields.SESSION_ID], "last_activity": stretch,
                     "send": not problem and answer["send"], "reason": answer.get("reason"),
                     "failed": bool(problem)})
        if problem:
            self.headless_failed(seat, "judge whether it could act now", problem)
            return
        if answer["send"]:
            self.start_wait(seat, verdict, stretch, answer["message"], 5)
            self.send(seat, verdict, answer["message"], NUDGE)

    def sentences(self, seat, verdict):
        """Rule 2: judge what code could not settle, and word one message naming every unbacked
        sentence. Returns ("unbacked", the message), ("failed", None) or ("all backed", None)."""
        checked = self.log.checked_sentences(seat)
        new = [item for item in verdict.get(fields.SENTENCES, [])
               if item["code_reading"] != fields.NOT_RAISED
               and (item["record_uuid"], item["sentence"]) not in checked]
        if not new:
            return "all backed", None
        judged = [item for item in new if item["code_reading"] == fields.JUDGE]
        backed = {}
        if judged:
            facts = dict(self.facts(seat, verdict),
                         sentences=[{"index": index, "time": item["time"], "kind": item["kind"],
                                     "sentence": item["sentence"]}
                                    for index, item in enumerate(judged)],
                         tool_calls_since_start_of_earliest_turn_with_sentence_to_judge=verdict.get(
                             fields.TOOL_CALLS_SINCE_START_OF_EARLIEST_TURN_WITH_SENTENCE_TO_JUDGE, []),
                         open_tasks_with_prerequisites_or_blocked_by=verdict.get(
                             fields.OPEN_TASKS_WITH_PREREQUISITES_OR_BLOCKED_BY, []))
            prompt = SENTENCES_JUDGE_PROMPT.format(
                seat=seat, facts=json.dumps(facts, indent=1, ensure_ascii=False))
            outcome = run_headless(prompt, SENTENCES_ANSWER_SCHEMA, "", self.working_directory,
                                   self.timeout_seconds)
            problem = outcome.error or sentence_answer_problem(outcome.answer, len(judged))
            for item in new:
                self.record({"event": "sentence_checked", "agent_seat": seat,
                             "record_uuid": item["record_uuid"], "sentence": item["sentence"]})
            if problem:
                self.headless_failed(seat, "judge whether its promises are backed", problem)
                return "failed", None
            for answer in outcome.answer["sentences"]:
                backed[answer["index"]] = answer["backed"]
            self.record({"event": "judge_answer", "agent_seat": seat, "rule": 2,
                         "answers": outcome.answer["sentences"]})
        else:
            for item in new:
                self.record({"event": "sentence_checked", "agent_seat": seat,
                             "record_uuid": item["record_uuid"], "sentence": item["sentence"]})
        unbacked = [item for item in new if item["code_reading"] == fields.UNBACKED]
        unbacked += [item for index, item in enumerate(judged) if not backed[index]]
        if not unbacked:
            return "all backed", None
        return "unbacked", "\n".join(UNBACKED_SENTENCE_LINES[item["kind"]].format(
            sentence=item["sentence"],
            minutes=int(seconds_between(item["time"], self.now) // 60) if item["time"] else "some")
            for item in unbacked)

    def usage_limit(self, seat, verdict):
        limit = verdict[fields.USAGE_LIMIT]
        record_uuid, account_now = limit["record_uuid"], limit["account_now_logged_in"]
        account, seen = self.log.limit_account(seat, record_uuid)
        if not seen or (account is None and account_now):
            self.record({"event": "limit_seen", "agent_seat": seat, "record_uuid": record_uuid,
                         "account": account_now})
            account = account or account_now
        if record_uuid in self.log.limit_wakes(seat):
            return
        if limit["reset_time_passed"]:
            why = LIMIT_ENDED_BY_RESET
        elif account and account_now and account_now != account:
            why = LIMIT_ENDED_BY_ACCOUNT.format(machine=self.machine)
        else:
            return
        text = LIMIT_WAKE_TEXT.format(why=why)
        self.record({"event": "limit_wake", "agent_seat": seat, "record_uuid": record_uuid,
                     "why": why})
        self.send(seat, verdict, text, LIMIT_WAKE)


def sentence_answer_problem(answer, count):
    indexes = sorted(item.get("index") for item in (answer or {}).get("sentences", [])
                     if isinstance(item, dict))
    if indexes != list(range(count)) or not all(
            isinstance(item.get("backed"), bool) for item in answer["sentences"]):
        return f"the judge's answer does not give backed true or false once for each of {count} " \
               f"sentences: {json.dumps(answer)[:500]}"
    return None


def idle_judge_answer_problem(answer):
    if not isinstance(answer.get("send"), bool) or not isinstance(answer.get("message"), str) or (
            answer["send"] and not answer["message"].strip()):
        return f"the judge's answer does not give send true or false, with a message when true: " \
               f"{json.dumps(answer)[:500]}"
    return None


def message_received(record):
    """Whether the record is one by which the agent-seat's model received a message: a user turn,
    or a message queued into a running turn. Claude Code's queue-operation record is written when
    a message is queued, before the model has it, and the message is lost if the agent-session
    ends first."""
    attachment = record.get("attachment")
    return record.get("type") == "user" or (
        record.get("type") == "attachment" and isinstance(attachment, dict)
        and attachment.get("type") == "queued_command")


def message_in_transcript(path, text, sent_at):
    """Whether a record by which the agent-seat received a message, written at or after the send,
    holds the text, compared with all runs of whitespace made one space."""
    needle = " ".join(text.split())
    for record in verdicts_print.transcript_records(path):
        if not message_received(record):
            continue
        moment = parse_time(record.get("timestamp"))
        if moment is None or (sent_at - moment).total_seconds() > DELIVERY_CLOCK_SLACK_SECONDS:
            continue
        if any(needle in " ".join(value.split()) for value in strings_in(record)):
            return True
    return False


def strings_in(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from strings_in(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings_in(item)


# --- The program ---

def sweep(arguments, now):
    paths = verdicts_print.Paths(arguments)
    log = SweepLog(Path(arguments.log_file).expanduser())
    machine = arguments.machine_name or socket.gethostname()
    run = Sweep(log, now, paths, Path(arguments.state_directory).expanduser(),
                arguments.headless_timeout_seconds, machine)
    seats = verdicts_print.agent_seats(paths.handoff_directory)
    checker = verdicts_print.due_task_hook.GitHubConditionChecker({}, now.timestamp())
    parser = verdicts_print.walk_finder.markdown_parser()
    verdicts, read_times = {}, {}
    for seat in seats:
        check = log.last_check(seat)
        skipped = {record_uuid for record_uuid, woken_at in log.limit_wakes(seat).items()
                   if seconds_between(woken_at, now) >= LIMIT_WAKE_GRACE_SECONDS}
        # Sentences only from the turns that ended since the last check of the same agent-session;
        # a new agent-session is read again with its last turn-ending message only. Since the read,
        # not the record: judge calls for other agent-seats run between the two, and a turn that
        # ends then must be read next time.
        since = parse_time(check["transcript_read_at"]) if check else None
        read_times[seat] = run.current()
        verdict = verdicts_print.verdict_for_seat(seat, paths, now, since, checker, parser, skipped)
        if since and verdict.get(fields.SESSION_ID) not in (None, check["session_id"]):
            verdict = verdicts_print.verdict_for_seat(seat, paths, now, None, checker, parser,
                                                      skipped)
        verdicts[seat] = verdict
    run.account_change(verdicts)
    run.delivery_checks(verdicts)
    for seat, verdict in verdicts.items():
        for error in verdict.get(fields.ERRORS, []):
            run.read_failure(seat, error)
        if verdict.get(fields.ERRORS) or not verdict.get(fields.IDLE) or verdict.get(fields.RULE) is None:
            continue
        run.handle_seat(seat, verdict, read_times[seat])
    run.read_failures_end()
    return 1 if run.failed else 0


def alert_run_failure(state_directory, error_text):
    """One user-alert for each distinct failure of a whole invocation, recorded in the state
    directory, since the failure may be the log itself."""
    alerted_file = state_directory / RUN_FAILURES_ALERTED_FILE_NAME
    alerted = alerted_file.read_text(encoding="utf-8").splitlines() if alerted_file.exists() else []
    if error_text in alerted:
        return
    user_alerts.user_alert_write_to_pending(
        "The idle sweep failed", f"The idle sweep, {Path(__file__).name}, failed: {error_text}",
        "An agent on ned-box can read the traceback in the cron output log "
        "~/.claude/agent-seat-idle-sweep-headless-judge-wake-messages-send-and-user-alerts-write.log "
        "and fix the cause; until then no idle agent-seat is woken.")
    with alerted_file.open("a", encoding="utf-8") as stream:
        stream.write(error_text + "\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--now", default=None, help="ISO time to act at, for tests")
    parser.add_argument("--log-file", default=str(LOG_FILE))
    parser.add_argument("--state-directory", default=str(STATE_DIRECTORY))
    parser.add_argument("--headless-timeout-seconds", type=float, default=HEADLESS_TIMEOUT_SECONDS)
    parser.add_argument("--machine-name", default=None, help="the machine named in messages")
    parser.add_argument("--handoff-directory", default="~/.claude/handoffs")
    parser.add_argument("--agents-root", default="~/agents")
    parser.add_argument("--projects-root", default="~/.claude/projects")
    parser.add_argument("--tasks-root", default="~/.claude/tasks")
    parser.add_argument("--claude-json", default="~/.claude.json")
    arguments = parser.parse_args(argv)
    now = parse_time(arguments.now) if arguments.now else datetime.now(timezone.utc)
    if now is None:
        parser.error("--now is not an ISO time")
    state_directory = Path(arguments.state_directory).expanduser()
    state_directory.mkdir(parents=True, exist_ok=True)
    with (state_directory / "run.lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(f"{iso(now)} an earlier invocation is still running; this one does nothing",
                  flush=True)
            return 0
        try:
            return sweep(arguments, now)
        except Exception as error:
            alert_run_failure(state_directory, f"{type(error).__name__}: {error}")
            raise


if __name__ == "__main__":
    sys.exit(main())
