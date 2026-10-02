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
from pathlib import Path

HOOK_SCRIPT = Path(__file__).with_name("agent-seat-due-task-raise-hook.py")

# Loaded in-process only for the cache boundary, which needs an exact clock;
# every other case runs the hook as a subprocess.
_hook_spec = importlib.util.spec_from_file_location("agent_seat_due_task_raise_hook",
                                                    HOOK_SCRIPT)
hook = importlib.util.module_from_spec(_hook_spec)
_hook_spec.loader.exec_module(hook)
TASK_LIST_ID = "nedschorus-test-seat-tasks"
PAST_DUE = "2020-01-01T00:00:00Z"
OTHER_PAST_DUE = "2021-06-01T12:00:00Z"
FUTURE_DUE = "2999-01-01T00:00:00Z"
STOP_PAYLOAD = json.dumps({
    "session_id": "test-session", "transcript_path": "/nonexistent.jsonl",
    "cwd": "/", "hook_event_name": "Stop", "stop_hook_active": False,
})
DEFER_LINE = ("If a task above cannot be acted on yet, give it a later "
              "metadata.due_utc, a new metadata.waits_on, or both, with TaskUpdate instead.")

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
        self.gh_responses.write_text(json.dumps(responses))

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


# --- due time passed raises, with the exact text -----------------------------
seat = Seat()
seat.task("7", metadata={"due_utc": PAST_DUE}, subject="Check the\nnightly run")
result = seat.run()
check("due time passed: exit 0", result.returncode == 0, result.returncode)
output = json.loads(result.stdout) if result.stdout.strip() else {}
check("due time passed: the Stop hook's JSON, no decision, no systemMessage",
      set(output) == {"hookSpecificOutput"}
      and output["hookSpecificOutput"].get("hookEventName") == "Stop",
      result.stdout)
expected_text = (f'Act on task 7 "Check the nightly run" now: its due time {PAST_DUE} '
                 f"has passed.\n{DEFER_LINE}")
check("due time passed: the exact text handed to the agent",
      context_of(result) == expected_text, repr(context_of(result)))
check("due time passed: no gh call for a task with no waits_on",
      seat.gh_calls() == [], seat.gh_calls())

# --- raised once, then silent ------------------------------------------------
second = seat.run()
check("raised once: the next stop is silent", silent(second), second)

# --- due time moved raises again ---------------------------------------------
seat.task("7", metadata={"due_utc": OTHER_PAST_DUE}, subject="Check the nightly run")
moved = seat.run()
check("due time moved to another passed time: raised again",
      context_of(moved) is not None and OTHER_PAST_DUE in context_of(moved), moved.stdout)
check("due time moved: then silent again", silent(seat.run()))

# --- not yet due --------------------------------------------------------------
seat = Seat()
seat.task("8", metadata={"due_utc": FUTURE_DUE})
check("not yet due: silent", silent(seat.run()))
check("not yet due: no state written", not seat.state_path.exists())

# --- due times written other ways -------------------------------------------
seat = Seat()
seat.task("9", metadata={"due_utc": "2020-01-01T00:00:00"})
seat.task("10", metadata={"due_utc": "2020-01-01T05:00:00+05:00"})
seat.task("11", metadata={"due_utc": "2020-01-01T00:00:00.5Z"})
seat.task("12", metadata={"due_utc": "next tuesday"})
text = context_of(seat.run()) or ""
check("a due time with no offset, with an offset, and with fractional seconds all raise",
      all(f"Act on task {task_id} " in text for task_id in ("9", "10", "11")), text)
check("an unreadable due time does not raise", "task 12 " not in text, text)

# --- in_progress raises; completed never does --------------------------------
seat = Seat()
seat.task("20", status="in_progress", metadata={"due_utc": PAST_DUE})
seat.task("21", status="completed", metadata={"due_utc": PAST_DUE})
text = context_of(seat.run()) or ""
check("in_progress task due: raised", "Act on task 20 " in text, text)
check("completed task due: never raised", "task 21 " not in text, text)

seat = Seat()
seat.task("22", status="completed", metadata={"due_utc": PAST_DUE,
                                               "waits_on": [{"pr_merged": 5}]})
seat.respond({"pr:5": {"state": "MERGED", "title": "T", "url": "https://x/5"}})
check("completed task with due and met waits_on: silent", silent(seat.run()))
check("completed task: gh never asked", seat.gh_calls() == [], seat.gh_calls())

# --- blockedBy ----------------------------------------------------------------
seat = Seat()
seat.task("30", metadata={"due_utc": PAST_DUE}, blocked_by=["31"])
seat.task("31", status="in_progress")
check("blockedBy incomplete: held, silent", silent(seat.run()))
check("blockedBy incomplete: nothing recorded as raised",
      not seat.state_path.exists()
      or "30" not in json.loads(seat.state_path.read_text()).get("raised", {}))
seat.task("31", status="completed")
text = context_of(seat.run()) or ""
check("blockedBy completed: raised", "Act on task 30 " in text, text)

seat = Seat()
seat.task("32", metadata={"due_utc": PAST_DUE}, blocked_by=["999"])
text = context_of(seat.run()) or ""
check("blockedBy naming a task with no file: not held", "Act on task 32 " in text, text)

seat = Seat()
seat.task("33", metadata={"due_utc": PAST_DUE}, blocked_by=["34"])
(seat.task_directory / "34.json").write_text("{ not json")
check("blockedBy naming an unreadable task file: held", silent(seat.run()))

seat = Seat()
seat.task("35", metadata={"due_utc": PAST_DUE, "waits_on": [{"pr_merged": 6}]},
          blocked_by=["36"])
seat.task("36")
seat.respond({"pr:6": {"state": "MERGED", "title": "T", "url": "https://x/6"}})
check("blockedBy incomplete: gh not asked for the held task",
      silent(seat.run()) and seat.gh_calls() == [], seat.gh_calls())

# --- waits_on -----------------------------------------------------------------
seat = Seat()
seat.task("40", metadata={"waits_on": [{"pr_merged": 101}, {"issue_closed": 202}]})
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
check("waits_on met: raised with each prerequisite cited by title and link",
      context_of(result) == expected_text, repr(context_of(result)))
calls = seat.gh_calls()
check("waits_on met: gh asked read-only view calls on the project repository",
      sorted(call["argv"] for call in calls) == [
          ["issue", "view", "202", "--repo", "nedschorus/nedschorus", "--json", "state,title,url"],
          ["pr", "view", "101", "--repo", "nedschorus/nedschorus", "--json", "state,title,url"]],
      calls)
check("waits_on met: GH_TOKEN removed before gh runs",
      calls and not any(call["gh_token_present"] for call in calls), calls)
check("waits_on met: raised once, then silent", silent(seat.run()))

seat = Seat()
seat.task("41", metadata={"waits_on": [{"pr_merged": 101}, {"issue_closed": 202}]})
seat.respond({"pr:101": {"state": "MERGED", "title": "A", "url": "https://x/101"},
              "issue:202": {"state": "OPEN", "title": "B", "url": "https://x/202"}})
check("waits_on partly met: silent", silent(seat.run()))

seat = Seat()
seat.task("42", metadata={"waits_on": [{"pr_merged": 103}]})
seat.respond({"pr:103": "fail"})
result = seat.run()
check("gh failing: silent", silent(result), result)
check("gh failing: it was asked", len(seat.gh_calls()) == 1, seat.gh_calls())

seat = Seat()
seat.task("43", metadata={"waits_on": [{"pr_merged": 104}]})
seat.respond({"pr:104": "garbage"})
check("gh answering unparsable output: silent", silent(seat.run()))

seat = Seat()
seat.task("44", metadata={"waits_on": [{"pr_merged": 105}]})
seat.respond({"pr:105": {"state": "MERGED", "title": "T", "url": "https://x/105"}})
broken_path = seat.home / "fake-bin" / "gh"
broken_path.unlink()
empty_bin = seat.home / "empty-bin"
empty_bin.mkdir()
environment = {**seat_session_environment(), "HOME": str(seat.home), "PATH": str(empty_bin),
               "CLAUDE_CODE_TASK_LIST_ID": TASK_LIST_ID}
result = subprocess.run([sys.executable, str(HOOK_SCRIPT)], input=STOP_PAYLOAD,
                        capture_output=True, text=True, env=environment, check=False)
check("gh not installed: silent", silent(result), result)

seat = Seat()
seat.task("45", metadata={"waits_on": []})
seat.task("46", metadata={"waits_on": [{"pr_merged": 107}, {"merged_by": "x"}]})
seat.task("47", metadata={"waits_on": [{"pr_merged": "107"}]})
seat.respond({"pr:107": {"state": "MERGED", "title": "T", "url": "https://x/107"}})
check("empty waits_on, an unknown condition, a non-number condition: never raise",
      silent(seat.run()), seat.gh_calls())

seat = Seat()
seat.task("48", metadata={"waits_on": [{"pr_merged": 108}]})
seat.respond({"pr:108": {"state": "MERGED"}})
text = context_of(seat.run()) or ""
check("waits_on met but gh gave no title: cited by number",
      'its prerequisites are met: PR 108 is merged.' in text, text)

# --- the five-minute cache -----------------------------------------------------
seat = Seat()
seat.task("50", metadata={"waits_on": [{"pr_merged": 110}]})
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
seat.task("51", metadata={"waits_on": [{"pr_merged": 111}]})
seat.respond({"pr:111": "fail"})
seat.run()
seat.run()
check("cache: a failed check also waits five minutes", len(seat.gh_calls()) == 1,
      seat.gh_calls())

seat = Seat()
seat.task("52", metadata={"waits_on": [{"pr_merged": 112}]})
seat.task("53", metadata={"waits_on": [{"pr_merged": 112}]})
seat.respond({"pr:112": {"state": "MERGED", "title": "T", "url": "https://x/112"}})
text = context_of(seat.run()) or ""
check("one condition named by two tasks: one gh call, both raised",
      len(seat.gh_calls()) == 1 and "task 52 " in text and "task 53 " in text,
      (text, seat.gh_calls()))

# --- prerequisite set changed raises again --------------------------------------
seat.task("52", metadata={"waits_on": [{"pr_merged": 112}, {"issue_closed": 113}]})
seat.respond({"pr:112": {"state": "MERGED", "title": "T", "url": "https://x/112"},
              "issue:113": {"state": "CLOSED", "title": "U", "url": "https://x/113"}})
text = context_of(seat.run()) or ""
check("waits_on changed and met: raised again", "Act on task 52 " in text
      and "task 53 " not in text, text)

# --- due and prerequisites in one line ---------------------------------------------
seat = Seat()
seat.task("54", metadata={"due_utc": PAST_DUE, "waits_on": [{"issue_closed": 114}]})
seat.respond({"issue:114": {"state": "CLOSED", "title": "U", "url": "https://x/114"}})
text = context_of(seat.run()) or ""
check("due and prerequisites both: one line naming both reasons",
      text.splitlines()[0:1] == [
          f'Act on task 54 "Subject of task 54" now: its due time {PAST_DUE} has passed, '
          'and its prerequisites are met: GHI "U" (https://x/114) is closed.'], text)

# --- malformed input ----------------------------------------------------------------
seat = Seat()
(seat.task_directory / "60.json").write_text("{ this is not json")
(seat.task_directory / "61.json").write_text(json.dumps(["a", "list"]))
(seat.task_directory / "62.json").write_text(json.dumps({"subject": "no id",
                                                          "status": "pending",
                                                          "metadata": {"due_utc": PAST_DUE}}))
seat.task("63", metadata="not a dict")
check("malformed task files alone: silent", silent(seat.run()))
seat.task("64", metadata={"due_utc": PAST_DUE})
text = context_of(seat.run()) or ""
check("malformed task files beside a due task: the due task still raised",
      text.startswith("Act on task 64 ") and text.count("Act on task") == 1, text)

seat = Seat()
seat.task("65", metadata={"due_utc": PAST_DUE})
for name, stdin_text in (("not JSON", "not json at all"), ("a JSON list", "[1, 2]"),
                         ("empty", "")):
    result = seat.run(stdin_text=stdin_text)
    check(f"malformed payload ({name}): silent", silent(result), result)
check("malformed payload: nothing recorded", not seat.state_path.exists())

seat = Seat()
seat.task("66", metadata={"due_utc": PAST_DUE})
check("no task list id in the environment: silent", silent(seat.run(list_id=None)))
check("a task list id that is a path, even to a real list: silent",
      silent(seat.run(list_id=f"../tasks/{TASK_LIST_ID}")))
check("a task list with no directory: silent",
      silent(seat.run(list_id="nedschorus-no-such-seat-tasks")))

# --- a headless child of an agent-seat is never raised ------------------------------
seat = Seat()
seat.task("68", metadata={"due_utc": PAST_DUE})
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
seat.task("67", metadata={"due_utc": PAST_DUE})
seat.state_path.parent.mkdir(parents=True)
seat.state_path.write_text("{ torn")
text = context_of(seat.run()) or ""
check("unparsable state file: read as empty, task raised", "Act on task 67 " in text, text)
check("unparsable state file: replaced, so the next stop is silent", silent(seat.run()))

# --- the record is written before anything is printed ------------------------------
seat = Seat()
seat.task("70", metadata={"due_utc": PAST_DUE})
seat.state_path.parent.parent.mkdir(parents=True)
seat.state_path.parent.write_text("a file where the state directory should be")
result = seat.run()
check("state cannot be written: silent, so no raise goes unrecorded", silent(result), result)

# --- task files are never written ------------------------------------------------
seat = Seat()
seat.task("80", metadata={"due_utc": PAST_DUE, "waits_on": [{"pr_merged": 120}]},
          blocked_by=["81"])
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
seat.task("90", metadata={"due_utc": PAST_DUE, "waits_on": [{"pr_merged": 130}]})
seat.respond({"pr:130": "fail"})
seat.run()
(seat.task_directory / "90.json").unlink()
seat.task("91", metadata={"due_utc": FUTURE_DUE})
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
