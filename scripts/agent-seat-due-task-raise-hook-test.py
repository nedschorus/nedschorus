#!/usr/bin/env python3
"""Cases for the Stop hook that raises an agent-seat's due tasks.

Every case runs the hook as a subprocess, its real stdin-to-stdout path,
under a HOME this suite made, so the task list it reads and the state file it
writes are this suite's and never the real ~/.claude/tasks or
~/.local/state/claude. `gh` is a stand-in placed first on PATH: it answers
from a file the case writes, and logs every call, with whether GH_TOKEN
reached it, so a case can count calls. No case touches the network.

The exit code is asserted on every case: a Stop hook that exits 2 blocks the
turn from ending, so "always 0" is a property, not a detail.
"""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HOOK_SCRIPT = Path(__file__).with_name("agent-seat-due-task-raise-hook.py")

# Loaded in-process only for the cache boundary, which needs an exact clock;
# every other case runs the hook as a subprocess.
_hook_spec = importlib.util.spec_from_file_location("agent_seat_due_task_raise_hook",
                                                    HOOK_SCRIPT)
hook = importlib.util.module_from_spec(_hook_spec)
_hook_spec.loader.exec_module(hook)
TASK_LIST_ID = "nedschorus-test-seat-tasks"
MERGED_PR = 900
MET = {"prerequisites": [{"pr_merged": MERGED_PR}]}
STOP_PAYLOAD = json.dumps({
    "session_id": "test-session", "transcript_path": "/nonexistent.jsonl",
    "cwd": "/", "hook_event_name": "Stop", "stop_hook_active": False,
})
DEFER_LINE = ("If a task above cannot be acted on yet, record what it now waits on with "
              "TaskUpdate instead: a pull request or a GHI in a new metadata.prerequisites, "
              "or a task with addBlockedBy.")
WAITS_ON_CHANGE = ("metadata.waits_on is the old name of metadata.prerequisites: set "
                   "metadata.prerequisites to the same list, unless metadata.prerequisites "
                   "already holds what the task waits on, then set metadata.waits_on to null")
DUE_UTC_CHANGE = ("metadata.due_utc held a due time, which no hook reads any more: set "
                  "metadata.due_utc to null, and if the task waits on a pull request or a GHI, "
                  "record it in metadata.prerequisites, or on a task, with addBlockedBy")


def old_keys_text(task_id, subject, *changes):
    return (f'Task {task_id} "{subject}" still carries an old metadata key; change it with '
            f"TaskUpdate: {'; and '.join(changes)}.")

GH_STAND_IN = """#!{python}
import json, os, sys, time
with open(os.environ["FAKE_GH_LOG"], "a") as log:
    log.write(json.dumps({{"argv": sys.argv[1:],
                          "gh_token_present": "GH_TOKEN" in os.environ}}) + "\\n")
try:
    with open(os.environ["FAKE_GH_RESPONSES"]) as handle:
        responses = json.load(handle)
except FileNotFoundError:
    responses = {{}}
key = sys.argv[1] + ":" + sys.argv[3]
answer = responses.get(key, "fail")
if answer == "fail":
    sys.stderr.write("gh stand-in: failing on purpose\\n")
    sys.exit(1)
if answer == "garbage":
    print("not json")
    sys.exit(0)
print(json.dumps(answer))
"""

failures = []
SUITE_ROOT = Path(tempfile.mkdtemp(prefix="agent-seat-due-task-raise-test-"))


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def seat_session_environment():
    """This process's environment as an agent-seat's own attended session
    gives it to a Stop hook: attended, and no caller owning the session."""
    environment = dict(os.environ)
    environment["CLAUDE_CODE_SESSION_ATTENDED"] = "1"
    environment.pop("NEDSCHORUS_SESSION_REINCARNATION_OWNED_BY_CALLER", None)
    return environment


class Seat:
    """A HOME holding one task list, a gh stand-in, and its response file."""

    def __init__(self):
        self.home = Path(tempfile.mkdtemp(dir=str(SUITE_ROOT)))
        self.task_directory = self.home / ".claude" / "tasks" / TASK_LIST_ID
        self.task_directory.mkdir(parents=True)
        (self.task_directory / ".lock").write_text("")
        self.bin_directory = self.home / "fake-bin"
        self.bin_directory.mkdir()
        gh = self.bin_directory / "gh"
        gh.write_text(GH_STAND_IN.format(python=sys.executable))
        gh.chmod(0o755)
        self.gh_log = self.home / "gh-calls.log"
        self.gh_responses = self.home / "gh-responses.json"
        self.responses = {f"pr:{MERGED_PR}": {"state": "MERGED", "title": "Merged",
                                                "url": f"https://x/{MERGED_PR}"}}
        self.respond({})
        self.state_path = (self.home / ".local" / "state" / "claude"
                           / "agent-seat-due-task-raise-state" / f"{TASK_LIST_ID}.json")

    def task(self, task_id, status="pending", metadata=None, blocked_by=(),
             subject=None):
        task = {
            "id": task_id,
            "subject": subject if subject is not None else f"Subject of task {task_id}",
            "description": "a description",
            "activeForm": "Doing it",
            "status": status,
            "blocks": [],
            "blockedBy": list(blocked_by),
        }
        if metadata is not None:
            task["metadata"] = metadata
        (self.task_directory / f"{task_id}.json").write_text(json.dumps(task, indent=2))

    def respond(self, responses):
        """Add to, or replace, the answers the gh stand-in gives; pr:900 is merged."""
        self.responses.update(responses)
        self.gh_responses.write_text(json.dumps(self.responses))

    def gh_calls(self):
        if not self.gh_log.exists():
            return []
        return [json.loads(line) for line in self.gh_log.read_text().splitlines()]

    def run(self, stdin_text=STOP_PAYLOAD, list_id=TASK_LIST_ID, environment_changes=None):
        """Run the hook as an agent-seat's own attended session would, unless
        `environment_changes` says otherwise (a value of None removes the
        variable). The session signals are set rather than inherited, because
        this suite may itself run under a headless `claude -p`."""
        environment = {
            **seat_session_environment(),
            "HOME": str(self.home),
            "PATH": f"{self.bin_directory}{os.pathsep}{os.environ.get('PATH', '')}",
            "FAKE_GH_LOG": str(self.gh_log),
            "FAKE_GH_RESPONSES": str(self.gh_responses),
            "GH_TOKEN": "a-token-the-hook-must-remove",
        }
        if list_id is None:
            environment.pop("CLAUDE_CODE_TASK_LIST_ID", None)
        else:
            environment["CLAUDE_CODE_TASK_LIST_ID"] = list_id
        for name, value in (environment_changes or {}).items():
            if value is None:
                environment.pop(name, None)
            else:
                environment[name] = value
        return subprocess.run(
            [sys.executable, str(HOOK_SCRIPT)], input=stdin_text,
            capture_output=True, text=True, env=environment, check=False, timeout=60)


def context_of(result):
    """The additionalContext the hook emitted, or None when it printed nothing."""
    if not result.stdout.strip():
        return None
    payload = json.loads(result.stdout)
    return payload["hookSpecificOutput"]["additionalContext"]


def silent(result):
    return result.returncode == 0 and result.stdout == "" and result.stderr == ""


def reported(result, fault_words):
    """A fault: exit 1, no raise on stdout, one stderr line naming the hook and the fault."""
    lines = result.stderr.splitlines()
    return (result.returncode == 1 and result.stdout == "" and len(lines) == 1
            and lines[0].startswith("agent-seat-due-task-raise-hook: ")
            and fault_words in lines[0])




# --- prerequisites met raises, with the exact text ------------------------------
seat = Seat()
seat.task("7", metadata=MET, subject="Check the\nnightly run")
result = seat.run()
check("prerequisites met: exit 0", result.returncode == 0, result.returncode)
output = json.loads(result.stdout) if result.stdout.strip() else {}
check("prerequisites met: the Stop hook's JSON, no decision, no systemMessage",
      set(output) == {"hookSpecificOutput"}
      and output["hookSpecificOutput"].get("hookEventName") == "Stop",
      result.stdout)
expected_text = (f'Act on task 7 "Check the nightly run" now: its prerequisites are met: '
                 f'PR "Merged" (https://x/{MERGED_PR}) is merged.\n{DEFER_LINE}')
check("prerequisites met: the exact text handed to the agent",
      context_of(result) == expected_text, repr(context_of(result)))

# --- raised once, then silent ------------------------------------------------
second = seat.run()
check("raised once: the next stop is silent", silent(second), second)

# --- silent while the agent answers a Stop hook, raised at the next stop -----
answering_seat = Seat()
answering_seat.task("12", metadata=MET)
answering = answering_seat.run(json.dumps({**json.loads(STOP_PAYLOAD), "stop_hook_active": True}))
check("stop_hook_active: silent while the agent answers a Stop hook", silent(answering), answering)
check("stop_hook_active: no state written, so the raise is not lost",
      not answering_seat.state_path.exists())
later = answering_seat.run()
check("stop_hook_active: the next ordinary stop raises the task",
      context_of(later) is not None and "task 12" in context_of(later), later.stdout)

# --- not yet met --------------------------------------------------------------
seat = Seat()
seat.task("8", metadata={"prerequisites": [{"pr_merged": 901}]})
seat.respond({"pr:901": {"state": "OPEN", "title": "T", "url": "https://x/901"}})
check("prerequisites not met: silent", silent(seat.run()))
check("prerequisites not met: nothing recorded as raised",
      json.loads(seat.state_path.read_text())["raised"] == {})

# --- in_progress raises; completed never does --------------------------------
seat = Seat()
seat.task("20", status="in_progress", metadata=MET)
seat.task("21", status="completed", metadata=MET)
text = context_of(seat.run()) or ""
check("in_progress task met: raised", "Act on task 20 " in text, text)
check("completed task met: never raised", "task 21 " not in text, text)

seat = Seat()
seat.task("22", status="completed", metadata={"prerequisites": [{"pr_merged": 5}],
                                               "due_utc": "2020-01-01T00:00:00Z"})
seat.respond({"pr:5": {"state": "MERGED", "title": "T", "url": "https://x/5"}})
check("completed task with met prerequisites and an old key: silent", silent(seat.run()))
check("completed task: gh never asked", seat.gh_calls() == [], seat.gh_calls())

# --- blockedBy ----------------------------------------------------------------
seat = Seat()
seat.task("30", metadata=MET, blocked_by=["31"])
seat.task("31", status="in_progress")
check("blockedBy incomplete: held, silent", silent(seat.run()))
check("blockedBy incomplete: nothing recorded as raised",
      not seat.state_path.exists()
      or "30" not in json.loads(seat.state_path.read_text()).get("raised", {}))
seat.task("31", status="completed")
text = context_of(seat.run()) or ""
check("blockedBy completed: raised", "Act on task 30 " in text, text)

seat = Seat()
seat.task("32", metadata=MET, blocked_by=["999"])
text = context_of(seat.run()) or ""
check("blockedBy naming a task with no file: not held", "Act on task 32 " in text, text)

seat = Seat()
seat.task("33", metadata=MET, blocked_by=["34"])
(seat.task_directory / "34.json").write_text("{ not json")
check("blockedBy naming an unreadable task file: held", silent(seat.run()))

seat = Seat()
seat.task("35", metadata={"prerequisites": [{"pr_merged": 6}]}, blocked_by=["36"])
seat.task("36")
seat.respond({"pr:6": {"state": "MERGED", "title": "T", "url": "https://x/6"}})
check("blockedBy incomplete: gh not asked for the held task",
      silent(seat.run()) and seat.gh_calls() == [], seat.gh_calls())

# --- blockedBy alone: raised once its blockers all complete -------------------
seat = Seat()
seat.task("50", blocked_by=["52", "51"], subject="Ship after both")
seat.task("51", status="completed")
seat.task("52", status="in_progress")
check("blockedBy alone, one blocker still open: silent", silent(seat.run()))
seat.task("52", status="completed")
result = seat.run()
check("blockedBy alone, every blocker completed: the exact text handed to the agent",
      context_of(result) == ('Act on task 50 "Ship after both" now: the tasks it waited on '
                             f"are completed: task 51, task 52.\n{DEFER_LINE}"),
      repr(context_of(result)))
check("blockedBy alone: no gh call", seat.gh_calls() == [], seat.gh_calls())
check("blockedBy alone: the raise is recorded by its blocker list",
      json.loads(seat.state_path.read_text())["raised"]["50"] == {"blocked_by": ["51", "52"]},
      seat.state_path.read_text() if seat.state_path.exists() else "no state file")
check("blockedBy alone: raised once, then silent", silent(seat.run()))
seat.task("53", status="completed")
seat.task("50", blocked_by=["51", "52", "53"], subject="Ship after both")
text = context_of(seat.run()) or ""
check("blockedBy alone: a changed blocker list raises again", "Act on task 50 " in text, text)
check("blockedBy alone: then silent again", silent(seat.run()))

seat = Seat()
seat.task("54", metadata={}, blocked_by=["55"])
seat.task("55", status="completed")
text = context_of(seat.run()) or ""
check("blockedBy alone with an empty metadata object: raised", "Act on task 54 " in text, text)

seat = Seat()
seat.task("56", blocked_by=["998"])
check("blockedBy alone naming a deleted task: freed but not raised", silent(seat.run()))

seat = Seat()
seat.task("57", blocked_by=["58", "998"])
seat.task("58", status="completed")
check("blockedBy alone, one blocker completed and one deleted: not raised", silent(seat.run()))

seat = Seat()
seat.task("61", metadata={"prerequisites": [{"pr_merged": 7}]}, blocked_by=["62"])
seat.task("62", status="completed")
seat.respond({"pr:7": {"state": "OPEN", "title": "T", "url": "https://x/7"}})
check("blockers completed but prerequisites not met: silent", silent(seat.run()))

seat = Seat()
seat.task("63")
check("a task with no metadata and no blockedBy: silent", silent(seat.run()))
check("a task with no metadata and no blockedBy: no state written",
      not seat.state_path.exists())

# --- prerequisites ------------------------------------------------------------
seat = Seat()
seat.task("40", metadata={"prerequisites": [{"pr_merged": 101}, {"issue_closed": 202}]})
seat.respond({
    "pr:101": {"state": "MERGED", "title": "Add the\nthing", "url": "https://github.com/nedschorus/nedschorus/pull/101"},
    "issue:202": {"state": "CLOSED", "title": "The bug", "url": "https://github.com/nedschorus/nedschorus/issues/202"},
})
result = seat.run()
expected_text = (
    'Act on task 40 "Subject of task 40" now: its prerequisites are met: '
    'PR "Add the thing" (https://github.com/nedschorus/nedschorus/pull/101) is merged; '
    'GHI "The bug" (https://github.com/nedschorus/nedschorus/issues/202) is closed.'
    f"\n{DEFER_LINE}")
check("prerequisites met: raised with each prerequisite cited by title and link",
      context_of(result) == expected_text, repr(context_of(result)))
calls = seat.gh_calls()
check("prerequisites met: gh asked read-only view calls on the project repository",
      sorted(call["argv"] for call in calls) == [
          ["issue", "view", "202", "--repo", "nedschorus/nedschorus", "--json", "state,title,url"],
          ["pr", "view", "101", "--repo", "nedschorus/nedschorus", "--json", "state,title,url"]],
      calls)
check("prerequisites met: GH_TOKEN removed before gh runs",
      calls and not any(call["gh_token_present"] for call in calls), calls)
check("prerequisites met: raised once, then silent", silent(seat.run()))

seat = Seat()
seat.task("41", metadata={"prerequisites": [{"pr_merged": 101}, {"issue_closed": 202}]})
seat.respond({"pr:101": {"state": "MERGED", "title": "A", "url": "https://x/101"},
              "issue:202": {"state": "OPEN", "title": "B", "url": "https://x/202"}})
check("prerequisites partly met: silent", silent(seat.run()))

seat = Seat()
seat.task("42", metadata={"prerequisites": [{"pr_merged": 103}]})
seat.respond({"pr:103": "fail"})
result = seat.run()
GH_COMMAND_103 = "`gh pr view 103 --repo nedschorus/nedschorus --json state,title,url`"
GH_FAILURE_103 = ("This hook could not ask GitHub whether PR 103 is merged, so no task "
                  f"waiting on it was raised: {GH_COMMAND_103} exited 1: gh stand-in: "
                  "failing on purpose. It asks again at the first stop at least 5 minutes "
                  "from now.")
check("gh failing: reported on stderr with gh's command and error, exit 1, nothing raised",
      reported(result, GH_FAILURE_103), result)
check("gh failing: it was asked", len(seat.gh_calls()) == 1, seat.gh_calls())
check("gh failing: the next stop within five minutes is silent and does not ask again",
      silent(seat.run()) and len(seat.gh_calls()) == 1, seat.gh_calls())

seat = Seat()
seat.task("40", metadata=MET, subject="Met anyway")
seat.task("42", metadata={"prerequisites": [{"pr_merged": 103}]})
seat.respond({"pr:103": "fail"})
result = seat.run()
text = context_of(result) or ""
check("gh failing at a stop that raises a task: exit 0, the raise, then the gh failure "
      "line for the agent",
      result.returncode == 0 and text.startswith('Act on task 40 "Met anyway" now')
      and text.splitlines()[-1].startswith(
          "This hook could not ask GitHub whether PR 103 is merged, so no task waiting on it "
          f"was raised: {GH_COMMAND_103} exited 1")
      and "Act on task 42" not in text, (result, text))

seat = Seat()
seat.task("43", metadata={"prerequisites": [{"pr_merged": 104}]})
seat.respond({"pr:104": "garbage"})
check("gh answering unparsable output: reported, exit 1",
      reported(seat.run(), "`gh pr view 104 --repo nedschorus/nedschorus --json "
                           "state,title,url` exited 0 without printing a JSON object"))

seat = Seat()
seat.task("44", metadata={"prerequisites": [{"pr_merged": 105}]})
seat.respond({"pr:105": {"state": "MERGED", "title": "T", "url": "https://x/105"}})
broken_path = seat.home / "fake-bin" / "gh"
broken_path.unlink()
empty_bin = seat.home / "empty-bin"
empty_bin.mkdir()
environment = {**seat_session_environment(), "HOME": str(seat.home), "PATH": str(empty_bin),
               "CLAUDE_CODE_TASK_LIST_ID": TASK_LIST_ID}
result = subprocess.run([sys.executable, str(HOOK_SCRIPT)], input=STOP_PAYLOAD,
                        capture_output=True, text=True, env=environment, check=False)
check("gh not installed: reported, exit 1",
      reported(result, "`gh pr view 105 --repo nedschorus/nedschorus --json state,title,url` "
                       "could not be run: "), result)

real_subprocess_run = hook.subprocess.run


def timing_out_run(command, timeout=None, **keywords):
    raise subprocess.TimeoutExpired(command, timeout)


hook.subprocess.run = timing_out_run
try:
    timed_out = hook.GitHubConditionChecker.ask_gh("issue_closed", 9, 8)
finally:
    hook.subprocess.run = real_subprocess_run
check("gh timing out is a gh failure naming the command and its time limit, not an answer",
      timed_out == {"gh_failure": "`gh issue view 9 --repo nedschorus/nedschorus --json "
                                  "state,title,url` did not answer within 8 seconds"},
      timed_out)

seat = Seat()
seat.task("45", metadata={"prerequisites": []})
seat.task("46", metadata={"prerequisites": [{"pr_merged": 107}, {"merged_by": "x"}]})
seat.task("47", metadata={"prerequisites": [{"pr_merged": "107"}]})
seat.respond({"pr:107": {"state": "MERGED", "title": "T", "url": "https://x/107"}})
check("empty prerequisites, an unknown condition, a non-number condition: never raise",
      silent(seat.run()), seat.gh_calls())

seat = Seat()
seat.task("48", metadata={"prerequisites": [{"pr_merged": 108}]})
seat.respond({"pr:108": {"state": "MERGED"}})
text = context_of(seat.run()) or ""
check("prerequisites met but gh gave no title: cited by number",
      'its prerequisites are met: PR 108 is merged.' in text, text)

seat = Seat()
seat.task("49", metadata={"prerequisites": [{"pr_merged": 109}]})
seat.state_path.parent.mkdir(parents=True)
seat.state_path.write_text(json.dumps({"raised": {}, "checks": {
    "pr_merged:109": {"met": 1, "checked_at_epoch": time.time()}}}))
check("a cached answer whose met is 1, not true: not met, so not raised",
      silent(seat.run()) and seat.gh_calls() == [], seat.gh_calls())

# --- the five-minute cache -----------------------------------------------------
seat = Seat()
seat.task("50", metadata={"prerequisites": [{"pr_merged": 110}]})
seat.respond({"pr:110": {"state": "OPEN", "title": "T", "url": "https://x/110"}})
check("cache: first stop, unmet, silent", silent(seat.run()))
check("cache: first stop asked gh once", len(seat.gh_calls()) == 1, seat.gh_calls())
seat.respond({"pr:110": {"state": "MERGED", "title": "T", "url": "https://x/110"}})
check("cache: a stop within five minutes is silent though the PR merged",
      silent(seat.run()))
check("cache: a stop within five minutes does not ask gh",
      len(seat.gh_calls()) == 1, seat.gh_calls())
state = json.loads(seat.state_path.read_text())
state["checks"]["pr_merged:110"]["checked_at_epoch"] -= 290
seat.state_path.write_text(json.dumps(state))
check("cache: 290 seconds old still holds", silent(seat.run()) and len(seat.gh_calls()) == 1,
      seat.gh_calls())
state = json.loads(seat.state_path.read_text())
state["checks"]["pr_merged:110"]["checked_at_epoch"] -= 15
seat.state_path.write_text(json.dumps(state))
text = context_of(seat.run()) or ""
check("cache: older than five minutes, gh is asked again and the task raised",
      "Act on task 50 " in text and len(seat.gh_calls()) == 2, (text, seat.gh_calls()))
seat.run()
check("cache: a raised task's prerequisites are never asked again",
      len(seat.gh_calls()) == 2, seat.gh_calls())


class CountingChecker(hook.GitHubConditionChecker):
    """The hook's checker with gh replaced by a counter, for exact clock values."""
    asked = []

    @staticmethod
    def ask_gh(kind, number, timeout_seconds):
        CountingChecker.asked.append((kind, number))
        return {"met": False}


cached_answer = {"met": False, "checked_at_epoch": 1000.0}
checker = CountingChecker({"pr_merged:1": cached_answer}, 1000.0 + 299.999)
check("cache boundary: 299.999 seconds old is answered from the cache",
      checker.answer("pr_merged", 1) is cached_answer and CountingChecker.asked == [],
      CountingChecker.asked)
checker = CountingChecker({"pr_merged:1": dict(cached_answer)}, 1000.0 + 300)
checker.answer("pr_merged", 1)
check("cache boundary: 300 seconds old asks gh",
      CountingChecker.asked == [("pr_merged", 1)], CountingChecker.asked)

seat = Seat()
seat.task("51", metadata={"prerequisites": [{"pr_merged": 111}]})
seat.respond({"pr:111": "fail"})
seat.run()
seat.run()
check("cache: a failed check also waits five minutes", len(seat.gh_calls()) == 1,
      seat.gh_calls())

seat = Seat()
seat.task("52", metadata={"prerequisites": [{"pr_merged": 112}]})
seat.task("53", metadata={"prerequisites": [{"pr_merged": 112}]})
seat.respond({"pr:112": {"state": "MERGED", "title": "T", "url": "https://x/112"}})
text = context_of(seat.run()) or ""
check("one condition named by two tasks: one gh call, both raised",
      len(seat.gh_calls()) == 1 and "task 52 " in text and "task 53 " in text,
      (text, seat.gh_calls()))

# --- prerequisite set changed raises again --------------------------------------
seat.task("52", metadata={"prerequisites": [{"pr_merged": 112}, {"issue_closed": 113}]})
seat.respond({"issue:113": {"state": "CLOSED", "title": "U", "url": "https://x/113"}})
text = context_of(seat.run()) or ""
check("prerequisites changed and met: raised again", "Act on task 52 " in text
      and "task 53 " not in text, text)

# --- a task raised for its prerequisites, then given a blocker ------------------
seat = Seat()
seat.task("110", metadata=MET, subject="Wait again")
check("raised for prerequisites", "Act on task 110 " in (context_of(seat.run()) or ""))
seat.task("110", metadata=MET, blocked_by=["111"], subject="Wait again")
seat.task("111", status="in_progress")
check("given a blocker after the raise: held, silent", silent(seat.run()))
seat.task("111", status="completed")
result = seat.run()
check("the blocker completed: raised for it, with the exact text",
      context_of(result) == ('Act on task 110 "Wait again" now: the tasks it waited on are '
                             f"completed: task 111.\n{DEFER_LINE}"), repr(context_of(result)))
check("the blocker completed: raised once, then silent", silent(seat.run()))

seat = Seat()
seat.task("112", metadata=MET, blocked_by=["113"])
seat.task("113", status="completed")
text = context_of(seat.run()) or ""
check("prerequisites met and blockers already completed: raised once, for the prerequisites",
      "Act on task 112 " in text and "its prerequisites are met" in text
      and "the tasks it waited on" not in text, text)
check("prerequisites met and blockers already completed: then silent", silent(seat.run()))

seat = Seat()
seat.task("114", metadata={"prerequisites": [{"pr_merged": 902}]}, blocked_by=["115"])
seat.task("115", status="completed")
seat.respond({"pr:902": {"state": "OPEN", "title": "T", "url": "https://x/902"}})
check("prerequisites not yet met, blockers completed: silent", silent(seat.run()))

seat = Seat()
seat.task("116", metadata={"prerequisites": []}, blocked_by=["117"])
seat.task("117", status="completed")
check("unreadable prerequisites, blockers completed: never raised", silent(seat.run()))

# --- the old keys: waits_on still read, both named until changed -----------------
seat = Seat()
seat.task("100", metadata={"waits_on": [{"pr_merged": MERGED_PR}]}, subject="Old list")
result = seat.run()
check("waits_on alone and met: raised, then the line naming the old key, exact text",
      result.returncode == 0 and context_of(result) == (
          f'Act on task 100 "Old list" now: its prerequisites are met: PR "Merged" '
          f"(https://x/{MERGED_PR}) is merged.\n{DEFER_LINE}\n"
          + old_keys_text("100", "Old list", WAITS_ON_CHANGE)),
      repr(context_of(result)))
check("waits_on alone: raised and named once, then silent", silent(seat.run()))
check("waits_on alone: recorded under the new key",
      "prerequisites" in json.loads(seat.state_path.read_text())["raised"]["100"]
      and "waits_on" not in json.loads(seat.state_path.read_text())["raised"]["100"],
      seat.state_path.read_text())
seat.task("100", metadata={"prerequisites": [{"pr_merged": MERGED_PR}]}, subject="Old list")
check("the list moved to prerequisites unchanged: silent", silent(seat.run()))
check("the list moved: the old-key record is cleared",
      "old_keys" not in json.loads(seat.state_path.read_text())["raised"]["100"],
      seat.state_path.read_text())

seat = Seat()
seat.state_path.parent.mkdir(parents=True)
seat.state_path.write_text(json.dumps({"raised": {"101": {
    "waits_on": hook.canonical_prerequisites([{"pr_merged": MERGED_PR}])}}, "checks": {}}))
seat.task("101", metadata={"prerequisites": [{"pr_merged": MERGED_PR}]})
check("a raise recorded under waits_on counts for the same list under prerequisites: silent",
      silent(seat.run()) and seat.gh_calls() == [], seat.gh_calls())

seat = Seat()
seat.task("102", metadata={"prerequisites": [{"pr_merged": 301}],
                           "waits_on": [{"pr_merged": MERGED_PR}]}, subject="Both lists")
seat.respond({"pr:301": {"state": "OPEN", "title": "T", "url": "https://x/301"}})
result = seat.run()
check("prerequisites and waits_on both: prerequisites decides, waits_on is only named",
      result.returncode == 0
      and context_of(result) == old_keys_text("102", "Both lists", WAITS_ON_CHANGE)
      and [call["argv"][2] for call in seat.gh_calls()] == ["301"],
      (repr(context_of(result)), seat.gh_calls()))

seat = Seat()
seat.task("103", metadata={"due_utc": "2020-01-01T00:00:00Z"}, subject="Old due time")
result = seat.run()
check("due_utc alone: named with the exact text, exit 0, no raise and no defer line",
      result.returncode == 0 and result.stderr == ""
      and context_of(result) == old_keys_text("103", "Old due time", DUE_UTC_CHANGE),
      (repr(context_of(result)), result.stderr))
check("due_utc alone: named once, then silent", silent(seat.run()))
seat.task("103", metadata={"due_utc": "2021-01-01T00:00:00Z"}, subject="Old due time")
check("due_utc changed: named again",
      context_of(seat.run()) == old_keys_text("103", "Old due time", DUE_UTC_CHANGE))
seat.task("103", metadata={}, subject="Old due time")
check("due_utc removed: silent", silent(seat.run()))
check("due_utc removed: no record left for the task",
      "103" not in json.loads(seat.state_path.read_text())["raised"],
      seat.state_path.read_text())

seat = Seat()
seat.task("104", metadata={"due_utc": "2020-01-01T00:00:00Z", "waits_on": [{"pr_merged": 302}]},
          subject="Both old keys", blocked_by=["105"])
seat.task("105", status="in_progress")
result = seat.run()
check("both old keys, held by blockedBy: named in one line, gh not asked",
      context_of(result) == old_keys_text("104", "Both old keys", WAITS_ON_CHANGE, DUE_UTC_CHANGE)
      and seat.gh_calls() == [], (repr(context_of(result)), seat.gh_calls()))

seat = Seat()
seat.task("106", metadata={"due_utc": "2020-01-01T00:00:00Z"}, subject="Old due time")
seat.task("42", metadata={"prerequisites": [{"pr_merged": 103}]})
seat.respond({"pr:103": "fail"})
result = seat.run()
check("an old key named and gh failing, nothing raised: exit 0, the name, then the gh failure",
      result.returncode == 0 and context_of(result) == (
          old_keys_text("106", "Old due time", DUE_UTC_CHANGE) + "\n" + GH_FAILURE_103
          + " If gh's error says PR 103 does not exist, correct the metadata.prerequisites "
          "that names it with TaskUpdate. If it says gh is not logged in or its credentials "
          "are bad, ask the user to run `gh auth login` on this machine."),
      (repr(context_of(result)), result.stderr))

seat = Seat()
seat.task("107", metadata={"due_utc": "2020-01-01T00:00:00Z"})
seat.state_path.parent.parent.mkdir(parents=True)
seat.state_path.parent.write_text("a file where the state directory should be")
result = seat.run()
check("state cannot be written with an old key to name: reported, saying it went unnamed",
      reported(result, "no task was due at this stop, so none went unraised, and 1 task(s) "
                       "still carrying an old key were not named; that stop names them"),
      result)

# --- malformed input ----------------------------------------------------------------
seat = Seat()
(seat.task_directory / "60.json").write_text("{ this is not json")
(seat.task_directory / "61.json").write_text(json.dumps(["a", "list"]))
(seat.task_directory / "62.json").write_text(json.dumps({"subject": "no id",
                                                          "status": "pending",
                                                          "metadata": MET}))
seat.task("63", metadata="not a dict")
check("malformed task files alone: silent", silent(seat.run()))
seat.task("64", metadata=MET)
text = context_of(seat.run()) or ""
check("malformed task files beside a due task: the due task still raised",
      text.startswith("Act on task 64 ") and text.count("Act on task") == 1, text)

seat = Seat()
seat.task("65", metadata=MET)
for name, stdin_text, fault_words in (
        ("not JSON", "not json at all", "no task was checked at this stop"),
        ("a JSON list", "[1, 2]", "JSON, but not an object, so no task was checked"),
        ("empty", "", "JSONDecodeError")):
    result = seat.run(stdin_text=stdin_text)
    check(f"malformed payload ({name}): reported on stderr, exit 1, no raise",
          reported(result, fault_words), result)
check("malformed payload: nothing recorded", not seat.state_path.exists())

seat = Seat()
seat.task("66", metadata=MET)
check("no task list id in the environment: silent", silent(seat.run(list_id=None)))
check("a task list id that is a path, even to a real list: silent",
      silent(seat.run(list_id=f"../tasks/{TASK_LIST_ID}")))
check("a task list with no directory: silent",
      silent(seat.run(list_id="nedschorus-no-such-seat-tasks")))

# --- a headless child of an agent-seat is never raised ------------------------------
seat = Seat()
seat.task("68", metadata=MET)
result = seat.run(environment_changes={"CLAUDE_CODE_SESSION_ATTENDED": "0"})
check("unattended session (a claude -p child): silent", silent(result), result)
result = seat.run(environment_changes={
    "NEDSCHORUS_SESSION_REINCARNATION_OWNED_BY_CALLER": "scripts/ghi-info-ask.py"})
check("session whose caller owns its reincarnation: silent", silent(result), result)
check("silenced sessions record nothing, so the seat's own session still raises the task",
      not seat.state_path.exists(), seat.state_path)
text = context_of(seat.run(environment_changes={"CLAUDE_CODE_SESSION_ATTENDED": None})) or ""
check("attended variable missing: the task is raised", "Act on task 68 " in text, text)
check("the attended session after them: silent, the task already raised", silent(seat.run()))

seat = Seat()
seat.task("67", metadata=MET)
seat.state_path.parent.mkdir(parents=True)
seat.state_path.write_text("{ torn")
text = context_of(seat.run()) or ""
check("unparsable state file: read as empty, task raised", "Act on task 67 " in text, text)
check("unparsable state file: replaced, so the next stop is silent", silent(seat.run()))

# --- the record is written before anything is printed ------------------------------
seat = Seat()
seat.task("70", metadata=MET)
seat.state_path.parent.parent.mkdir(parents=True)
seat.state_path.parent.write_text("a file where the state directory should be")
result = seat.run()
check("state cannot be written: reported on stderr, exit 1, and no raise goes unrecorded",
      reported(result, "could not be written, and so 1 due task(s) were not raised at this "
                       "stop; the first stop after the state file can be written raises them")
      and "no task was checked" not in result.stderr
      and "old key" not in result.stderr, result)
seat.state_path.parent.unlink()
text = context_of(seat.run()) or ""
check("state writable again: the task the failed write left unraised is raised",
      text.startswith("Act on task 70 "), text)

seat = Seat()
seat.task("71", metadata={"prerequisites": [{"pr_merged": 140}]})
seat.respond({"pr:140": "fail"})
seat.state_path.parent.parent.mkdir(parents=True)
seat.state_path.parent.write_text("a file where the state directory should be")
result = seat.run()
check("state cannot be written with nothing due: reported, saying no task went unraised",
      reported(result, "could not be written, and no task was due at this stop, so none "
                       "went unraised. Make ")
      and "were not raised" not in result.stderr
      and "no task was checked" not in result.stderr, result)

# --- task files are never written ------------------------------------------------
seat = Seat()
seat.task("80", metadata={"prerequisites": [{"pr_merged": 120}],
                          "due_utc": "2020-01-01T00:00:00Z"}, blocked_by=["81"])
seat.task("81", status="completed")
seat.respond({"pr:120": {"state": "MERGED", "title": "T", "url": "https://x/120"}})
before = {path.name: path.read_bytes() for path in seat.task_directory.iterdir()}
seat.run()
seat.run()
after = {path.name: path.read_bytes() for path in seat.task_directory.iterdir()}
check("task files byte-identical and none added after runs", before == after,
      sorted(set(before) ^ set(after)))
check("the state file is outside the task directory",
      seat.state_path.exists() and seat.task_directory not in seat.state_path.parents)

# --- state is pruned ------------------------------------------------------------------
seat = Seat()
seat.task("90", metadata={"prerequisites": [{"pr_merged": 130}]})
seat.task("89", metadata=MET)
seat.respond({"pr:130": "fail"})
seat.run()
(seat.task_directory / "90.json").unlink()
(seat.task_directory / "89.json").unlink()
seat.task("91")
seat.run()
state = json.loads(seat.state_path.read_text())
check("state pruned of deleted tasks and conditions no open task names",
      state["raised"] == {} and state["checks"] == {}, state)

shutil.rmtree(SUITE_ROOT, ignore_errors=True)
print()
if failures:
    print(f"{len(failures)} FAILED: {failures}")
    sys.exit(1)
print("all cases passed")
